"""A2 runtime（paired-runtime-v1）：把 paired 配對評估分派到 Windows spawn worker，輸出 internal-run-package。
- 協調父程序只做驗證、凍結、派工與合併，絕不執行 play_game，也絕不改任何程序（含自己）的優先權。
- 每個 spawn worker 的 initializer 把「自己」設為 IDLE_PRIORITY_CLASS 並查驗；每個 pair 開打前、打完後再查驗。
  任何 worker 設定失敗 → 在派出任何 pair 之前 fail closed（RuntimeSetupError，零場）。
- 派工單位＝一個 pair（opponent_id, block_id）：worker 對該任務呼叫 paired.run_paired，兩個 half 在同一 worker 依序執行；
  結果只有「完整 pair」或「failures」，父程序不接受半個 pair。輸出依 seed plan 順序 × opponent 輸入順序排序。
- worker 數只由參數決定（1..16 的 int），不讀環境變數。
- hash seed：父程序在 pool 存續期間暫設本行程 os.environ['PYTHONHASHSEED']='0'（spawn 子程序繼承），結束後還原；
  不動系統或使用者層級環境設定。worker 端以 sys.flags.hash_randomization==0 查驗。
- 凍結：CFG（值）、已載入 MANUAL／NAME_CHOICE 的值 hash、manual 開關環境值、執行原始碼 hash、相關卡資料 hash、牌表指紋；
  worker 重算比對，不一致 fail closed。
本模組只用標準庫與 paired／sim2；不讀任何牌表或私人 JSON，只讀 paired.EXECUTION_SOURCES 與本檔原始碼。"""
import concurrent.futures as cf
import contextlib, copy, ctypes, datetime, hashlib, json, multiprocessing, os, platform, sys, threading
from concurrent.futures.process import BrokenProcessPool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paired
import sim2

RUNTIME_VERSION = 'paired-runtime-v1'
IDENTITY_VERSION = 'paired-runtime-identity-v1'
PACKAGE_KIND = 'internal-run-package'
IDLE_PRIORITY_CLASS = 0x40
MAX_WORKERS = 16
HASH_SEED = '0'
SIM2_ENGINE_REF = 'sim2:play_game'
RUNTIME_SOURCE = 'deck_health/paired_runtime.py'
SOURCES = tuple(paired.EXECUTION_SOURCES) + (RUNTIME_SOURCE,)
SOURCES_ALGORITHM = ('sha256 依路徑排序串接：len(path)\\0 path \\0 len(bytes)\\0 bytes（與 paired.manifest 相同），'
                     '範圍＝paired.EXECUTION_SOURCES＋deck_health/paired_runtime.py')
# manual_cards.py 讀取的全部開關（paired.MANUAL_ENV_KEYS 漏了 INARI／CHAMP／P04，這裡補齊；測試會掃原始碼防漂移）
MANUAL_ENV_KEYS_FULL = ('DH_PENDING', 'DH_INARI', 'DH_INARI2', 'DH_INARI3', 'DH_CHAMP', 'DH_P04', 'DH_MIXED') + \
    tuple(f'DH_BATCH{i}' for i in range(1, 9))
CARDS_USED_ALGORITHM = ('cards-used-v1：sha256(UTF-8 canonical JSON of {card_no: U[card_no]}，card_no 取 candidate∪baseline∪所有 opponent 牌表；'
                        'json.dumps sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False)')
CARDS_INPUT_ALGORITHM = 'cards-input-v1：同 cards-used-v1 的 canonical JSON 與 sha256，套用到呼叫端傳入的完整 U'
CARDS_NOTE = '兩者都是記憶體中 U 的 canonical JSON hash，不是 cards_data.js 檔案的 hash；封存需要的卡庫檔案 hash 由呼叫端另行計算與記錄'
BARRIER_TIMEOUT = 120
NOT_DELIVERED = ['pair_timeout', 'retry', 'cross_opponent_pooling', 'non_windows', 'git_status', 'archive_assembly']
PAIRING = dict(scheme=paired.SCHEME, metric=paired.METRIC, delta_definition='mean-of-pair-differences',
               se_delta_definition='sample-sd-of-pair-differences/sqrt(N)')
FRAG_KEYS = {'design', 'seeds', 'pairing', 'pair_results', 'pairs'}
RUN_KEYS = {'plan', 'opponents', 'status', 'usable', 'expected_pairs', 'completed_pairs', 'pair_results', 'failures'}
PAIR_KEYS = {'pair_id', 'opponent_id', 'opponent_fingerprint', 'seed', 'candidate', 'baseline'}
FAILURE_KEYS = {'opponent_id', 'block_id', 'seed', 'side', 'reason'}


class RuntimeSetupError(Exception):
    """worker 設定／凍結查驗失敗：沒有任何 pair 被派出。"""


class ContractError(Exception):
    """結論片段或 package 不符合契約。"""


# ---- canonical JSON ----

def _canon(o):
    try:
        return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as e:
        raise ValueError(f'無法序列化為 canonical JSON：{e}') from None


def _sha(o):
    return hashlib.sha256(_canon(o).encode('utf-8')).hexdigest()


# ---- 輸入驗證 ----

def _check_workers(w):
    if type(w) is not int or not 1 <= w <= MAX_WORKERS:
        raise ValueError(f'workers 必須是 1～{MAX_WORKERS} 的 int（不接受 bool／非整數）：{w!r}')
    return w


def engine_ref(fn):
    """模組層級、可由名稱找回的函式 → 'module:qualname'（spawn 需要能 pickle）。"""
    mod, qn = getattr(fn, '__module__', None), getattr(fn, '__qualname__', None)
    if not callable(fn) or not isinstance(mod, str) or not isinstance(qn, str) or '<' in qn or '.' in qn \
            or getattr(sys.modules.get(mod), qn, None) is not fn:
        raise ValueError(f'必須是可由模組名稱找回的模組層級函式：{fn!r}')
    return f'{mod}:{qn}'


def _check_inputs(U, candidate, baseline, opponents, plan, experiment_id):
    paired._ident(experiment_id, 'experiment_id')
    plan = paired.check_plan(plan)
    if plan != paired.seed_plan(experiment_id, [p['block_id'] for p in plan]):
        raise ValueError('plan 必須由 paired.seed_plan(experiment_id, block_ids) 產生')
    if not isinstance(opponents, (list, tuple)) or not opponents or any(not isinstance(o, dict) or 'deck' not in o for o in opponents):
        raise ValueError('opponents 必須是非空的 {opponent_id, deck} 串列')
    ids = [o.get('opponent_id') for o in opponents]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('opponent_id 必須是不重複的非空字串')
    for d in [candidate, baseline] + [o['deck'] for o in opponents]:
        paired.check_deck(U, d)
    return plan, ids


# ---- 原始碼與卡資料 hash ----

def _read_runtime_source(path):
    if path != RUNTIME_SOURCE:
        raise ValueError(f'只讀本檔原始碼：{path}')
    with open(os.path.abspath(__file__), 'rb') as f:
        return f.read()


def _read(path):
    return _read_runtime_source(path) if path == RUNTIME_SOURCE else paired._read_source(path)


def source_hashes():
    sha, h = {}, hashlib.sha256()
    for p in sorted(SOURCES):
        b, pb = _read(p), p.encode('utf-8')
        sha[p] = hashlib.sha256(b).hexdigest()
        h.update(b'%d\0' % len(pb)); h.update(pb); h.update(b'\0%d\0' % len(b)); h.update(b)
    return dict(scope='execution-source-files+runtime', algorithm=SOURCES_ALGORITHM, sha256=sha, combined_sha256=h.hexdigest())


def _used_nos(candidate, baseline, opponents):
    return sorted(set(candidate) | set(baseline) | {n for o in opponents for n in o['deck']})


def cards_hashes(U, candidate, baseline, opponents):
    nos = _used_nos(candidate, baseline, opponents)
    return dict(used=dict(algorithm=CARDS_USED_ALGORITHM, sha256=_sha({n: U[n] for n in nos}), card_count=len(nos)),
                input=dict(algorithm=CARDS_INPUT_ALGORITHM, sha256=_sha(U), card_count=len(U)), note=CARDS_NOTE)


def _manual_env():
    return {k: os.environ.get(k) for k in MANUAL_ENV_KEYS_FULL}


# ---- 凍結與 identity ----

def _freeze(U, candidate, baseline, opponents, plan, experiment_id, play_game, idle_impl=None):
    plan, ids = _check_inputs(U, candidate, baseline, opponents, plan, experiment_id)
    ref = engine_ref(play_game)
    if idle_impl is not None:
        engine_ref(idle_impl)
    cfg = copy.deepcopy(sim2.CFG)
    nos = _used_nos(candidate, baseline, opponents)
    cards = cards_hashes(U, candidate, baseline, opponents)
    fp = paired.deck_fingerprint
    identity = dict(
        identity_version=IDENTITY_VERSION, runtime_version=RUNTIME_VERSION, experiment_id=experiment_id,
        seed_derivation=paired.SEED_DERIVATION_VERSION, plan=plan, scheme=paired.SCHEME, seats=dict(paired.SEATS),
        card_order_policy=paired.CARD_ORDER_POLICY, metric=copy.deepcopy(paired.METRIC),
        decks=dict(fingerprint_version=paired.FINGERPRINT_VERSION, candidate=fp(candidate), baseline=fp(baseline),
                   opponents=[dict(opponent_id=o['opponent_id'], fingerprint=fp(o['deck'])) for o in opponents]),
        cfg=cfg, cfg_sha256=_sha(cfg), manual_skills_hash=paired.manual_skills_hash(), manual_env=_manual_env(),
        sources=source_hashes(), cards_used=dict(algorithm=CARDS_USED_ALGORITHM, sha256=cards['used']['sha256']),
        engine_ref=ref, hash_seed=HASH_SEED,
        python=dict(implementation=platform.python_implementation(), version=platform.python_version()))
    return dict(identity=identity, identity_sha256=_sha(identity), cards=cards,
                U_sub={n: copy.deepcopy(U[n]) for n in nos},
                decks=dict(candidate=dict(candidate), baseline=dict(baseline),
                           opponents=[dict(opponent_id=o['opponent_id'], deck=dict(o['deck'])) for o in opponents]),
                play_game=play_game, idle_impl=idle_impl)


def identity_for(U, candidate, baseline, opponents, plan, *, experiment_id, play_game=None):
    return _freeze(U, candidate, baseline, opponents, plan, experiment_id, play_game or sim2.play_game)['identity']


def _verify(fz):
    """以目前行程狀態重算凍結值；回傳不一致項目（空＝一致）。只讀 allowlist 原始碼，不執行引擎。"""
    idt, bad = fz['identity'], []
    try:
        cfg_ok = _sha(sim2.CFG) == idt['cfg_sha256']
    except ValueError:
        cfg_ok = False
    if not cfg_ok: bad.append('cfg')
    if paired.manual_skills_hash() != idt['manual_skills_hash']: bad.append('manual_skills_hash')
    if _manual_env() != idt['manual_env']: bad.append('manual_env')
    src = source_hashes()
    if src['combined_sha256'] != idt['sources']['combined_sha256'] or src['sha256'] != idt['sources']['sha256']: bad.append('sources')
    try:
        cards_ok = _sha(fz['U_sub']) == idt['cards_used']['sha256']
    except ValueError:
        cards_ok = False
    if not cards_ok: bad.append('cards_used')
    d, fp = fz['decks'], paired.deck_fingerprint
    if [fp(d['candidate']), fp(d['baseline'])] + [fp(o['deck']) for o in d['opponents']] != \
            [idt['decks']['candidate'], idt['decks']['baseline']] + [o['fingerprint'] for o in idt['decks']['opponents']]:
        bad.append('fingerprints')
    try:
        ref_ok = engine_ref(fz['play_game']) == idt['engine_ref']
    except ValueError:
        ref_ok = False
    if not ref_ok: bad.append('engine_ref')
    return bad


# ---- 優先權（只作用於呼叫者自身行程；父程序拒絕設定）----

def _kernel32():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.GetCurrentProcess.restype = ctypes.c_void_p; k.GetCurrentProcess.argtypes = []
    k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]; k.SetPriorityClass.restype = ctypes.c_int
    k.GetPriorityClass.argtypes = [ctypes.c_void_p]; k.GetPriorityClass.restype = ctypes.c_uint32
    return k


def _current_priority(kernel32=None):
    """唯讀：目前行程的 priority class（非 Windows 回傳 None）。"""
    if kernel32 is None:
        if sys.platform != 'win32':
            return None
        kernel32 = _kernel32()
    return int(kernel32.GetPriorityClass(kernel32.GetCurrentProcess()))


def _ensure_idle(kernel32=None, *, in_worker=None):
    """把「目前行程」（GetCurrentProcess 偽 handle）設為 IDLE 並查驗；只允許在 spawn worker 內呼叫。"""
    if in_worker is None:
        in_worker = multiprocessing.parent_process() is not None
    if not in_worker:
        raise RuntimeError('拒絕在協調父程序設定優先權：只在 spawn worker 內設定 IDLE')
    if kernel32 is None:
        if sys.platform != 'win32':
            raise RuntimeError('IDLE 優先權只支援 Windows')
        kernel32 = _kernel32()
    h = kernel32.GetCurrentProcess()
    if not kernel32.SetPriorityClass(h, IDLE_PRIORITY_CLASS):
        raise OSError(ctypes.get_last_error(), 'SetPriorityClass(IDLE) 失敗')
    got = kernel32.GetPriorityClass(h)
    if got != IDLE_PRIORITY_CLASS:
        raise RuntimeError(f'查驗失敗：priority class={got:#x}，不是 IDLE')
    return got


# ---- worker 端 ----

_STATE = {}


def _init(fz, barrier):
    """spawn worker initializer：不丟例外（交由 probe 回報，父程序在派出任何 pair 前 fail closed）。"""
    _STATE.clear()
    _STATE.update(fz=fz, barrier=barrier, error=None)
    try:
        if multiprocessing.parent_process() is None:
            raise RuntimeError('initializer 只能在 spawn worker 執行')
        (fz['idle_impl'] or _ensure_idle)()
        if _current_priority() != IDLE_PRIORITY_CLASS:
            raise RuntimeError('not_idle')
        if sys.flags.hash_randomization != 0 or os.environ.get('PYTHONHASHSEED') != HASH_SEED:
            raise RuntimeError('hash_seed：worker 的 hash 隨機化未關閉（父程序是否以 -E／-I 啟動？）')
        sim2.CFG.clear(); sim2.CFG.update(copy.deepcopy(fz['identity']['cfg']))
        bad = _verify(fz)
        if bad:
            raise RuntimeError('frozen_mismatch:' + ','.join(bad))
    except BaseException as e:
        _STATE['error'] = f'{type(e).__name__}: {e}'


def _probe():
    st = _STATE
    try:
        st['barrier'].wait(BARRIER_TIMEOUT)   # 逼每個 worker 各領一個 probe
    except threading.BrokenBarrierError:
        return dict(pid=os.getpid(), error='barrier_broken')
    return dict(pid=os.getpid(), error=st.get('error'), priority=_current_priority(),
                hash_randomization=sys.flags.hash_randomization, hash_probe=hash('haikyuu-deck-health/hash-probe'),
                identity_sha256=_sha(st['fz']['identity']) if st.get('fz') else None)


def _state_drift():
    idt, bad = _STATE['fz']['identity'], []
    if _current_priority() != IDLE_PRIORITY_CLASS: bad.append('not_idle')
    try:
        if _sha(sim2.CFG) != idt['cfg_sha256']: bad.append('cfg')
    except ValueError:
        bad.append('cfg')
    if paired.manual_skills_hash() != idt['manual_skills_hash']: bad.append('manual')
    return bad


def _pair_task(oid, block_id, seed):
    st, meta = _STATE, dict(pid=os.getpid())
    if not st.get('fz') or st.get('error'):
        return dict(refused='setup_error', meta=meta)
    pre = _state_drift()
    if pre:
        return dict(refused='state_drift:' + ','.join(pre), meta=meta)
    fz, n = st['fz'], [0]
    pg = fz['play_game']
    opp = next(o for o in fz['decks']['opponents'] if o['opponent_id'] == oid)

    def counted(cardsA, cardsB, rng):
        n[0] += 1
        return pg(cardsA, cardsB, rng)

    r = paired.run_paired(fz['U_sub'], fz['decks']['candidate'], fz['decks']['baseline'], [opp],
                          [dict(block_id=block_id, seed=seed)], play_game=counted)
    post = _state_drift()
    meta.update(priority=_current_priority(), games=n[0])
    return dict(run=r, post_drift=post, meta=meta)


# ---- 父程序：派工與合併 ----

@contextlib.contextmanager
def _hash_seed_env():
    """只暫改本行程的 os.environ（spawn 子程序繼承），離開時還原原值或移除。"""
    old = os.environ.get('PYTHONHASHSEED')
    os.environ['PYTHONHASHSEED'] = HASH_SEED
    try:
        yield
    finally:
        if old is None:
            os.environ.pop('PYTHONHASHSEED', None)
        else:
            os.environ['PYTHONHASHSEED'] = old


def _collect_probes(ex, n, identity_sha):
    try:
        fs = [ex.submit(_probe) for _ in range(n)]
    except Exception as e:
        raise RuntimeSetupError(f'probe submit 失敗（未派出任何 pair）：{type(e).__name__}') from None
    done, _ = cf.wait(fs, timeout=BARRIER_TIMEOUT + 60)
    errors, probes = [], []
    for f in fs:
        if f not in done:
            errors.append('probe_timeout'); continue
        e = f.exception()
        if e is not None:
            errors.append(f'probe_exception:{type(e).__name__}'); continue
        p = f.result(); probes.append(p)
        if p.get('error'): errors.append(p['error'])
        elif p['priority'] != IDLE_PRIORITY_CLASS: errors.append('not_idle')
        elif p['hash_randomization'] != 0: errors.append('hash_seed')
        elif p['identity_sha256'] != identity_sha: errors.append('identity_mismatch')
    if not errors:
        pids = {p['pid'] for p in probes}
        if len(pids) != n or os.getpid() in pids: errors.append('distinct_workers')
        if len({p['hash_probe'] for p in probes}) != 1: errors.append('hash_probe_mismatch')
    if errors:
        raise RuntimeSetupError('worker 設定失敗（未派出任何 pair）：' + '; '.join(sorted(set(errors))))
    return probes


def _side_ok(s):
    return isinstance(s, dict) and set(s) == {'outcome', 'metric_value'} and s['outcome'] in ('win', 'loss') \
        and type(s['metric_value']) is int and s['metric_value'] == paired.METRIC['value_map'][s['outcome']]


def _task_run_verdict(r, oid, b, seed, fp):
    """worker 回傳的單任務 run：'pair'／'failed'／None（形狀不合 → 整個 pair 拒收）。"""
    if not isinstance(r, dict) or set(r) != RUN_KEYS or r['plan'] != [dict(block_id=b, seed=seed)] \
            or r['opponents'] != [dict(opponent_id=oid, fingerprint=fp)] or r['expected_pairs'] != 1 \
            or not isinstance(r['pair_results'], list) or not isinstance(r['failures'], list):
        return None
    pr, fl = r['pair_results'], r['failures']
    if not fl and len(pr) == 1 and r['status'] == 'complete' and r['usable'] is True and r['completed_pairs'] == 1:
        p = pr[0]
        want = dict(pair_id=json.dumps([b, oid], ensure_ascii=False, separators=(',', ':')), opponent_id=oid,
                    opponent_fingerprint=fp, seed=seed)
        if isinstance(p, dict) and set(p) == PAIR_KEYS and all(p[k] == v for k, v in want.items()) \
                and type(p['seed']) is int and _side_ok(p['candidate']) and _side_ok(p['baseline']):
            return 'pair'
        return None
    if fl and pr == [] and r['status'] == 'incomplete' and r['usable'] is False and r['completed_pairs'] == 0 \
            and all(isinstance(f, dict) and set(f) == FAILURE_KEYS and f['opponent_id'] == oid and f['block_id'] == b
                    and f['seed'] == seed and f['side'] in ('candidate', 'baseline') and isinstance(f['reason'], str) for f in fl):
        return 'failed'
    return None


def _merge(plan, ids, fps, ready_pids, outcomes):
    blocks = [p['block_id'] for p in plan]
    seed_of = {p['block_id']: p['seed'] for p in plan}
    done, failures, task_workers, games = {}, [], [], 0
    for b in blocks:
        for oid in ids:
            o, seed, reason, pid = outcomes.get((oid, b)), seed_of[b], None, None
            if o is None or isinstance(o, BrokenProcessPool):
                reason = 'worker_lost'
            elif isinstance(o, BaseException):
                reason = 'worker_exception:' + type(o).__name__
            elif not isinstance(o, dict) or not isinstance(o.get('meta'), dict):
                reason = 'malformed_worker_result'
            elif o.get('refused'):
                reason = o['refused'] if isinstance(o['refused'], str) else 'malformed_worker_result'
                pid = o['meta'].get('pid') if o['meta'].get('pid') in ready_pids else None
            else:
                meta = o['meta']
                if meta.get('pid') not in ready_pids:
                    reason = 'malformed_worker_result'
                else:
                    pid = meta['pid']
                    games += meta.get('games', 0) if type(meta.get('games')) is int else 0
                    v = _task_run_verdict(o.get('run'), oid, b, seed, fps[oid])
                    if meta.get('priority') != IDLE_PRIORITY_CLASS:
                        reason = 'not_idle'
                    elif o.get('post_drift'):
                        reason = 'state_drift:' + ','.join(map(str, o['post_drift']))
                    elif v == 'pair':
                        done[(oid, b)] = o['run']['pair_results'][0]
                    elif v == 'failed':
                        failures.extend(dict(f) for f in o['run']['failures'])
                    else:
                        reason = 'malformed_worker_result'
            if reason:
                failures.append(dict(opponent_id=oid, block_id=b, seed=seed, side='pair', reason=reason))
            task_workers.append([b, oid, pid])
    pair_results = [done[(oid, b)] for b in blocks for oid in ids if (oid, b) in done]
    failures.sort(key=lambda f: (blocks.index(f['block_id']), ids.index(f['opponent_id']), f['side']))
    expected = len(blocks) * len(ids)
    ok = not failures and len(pair_results) == expected
    run = dict(plan=[dict(p) for p in plan], opponents=[dict(opponent_id=i, fingerprint=fps[i]) for i in ids],
               status='complete' if ok else 'incomplete', usable=ok, expected_pairs=expected,
               completed_pairs=len(pair_results), pair_results=pair_results, failures=failures)
    return dict(run=run, task_workers=task_workers, games_played=games)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def execute(U, candidate, baseline, opponents, plan, *, experiment_id, workers, play_game=None, schedule=None, _idle_impl=None,
            _executor_factory=None):
    """回傳 internal-run-package（非正式封存、非公開發布包）。_idle_impl／_executor_factory 只供測試注入失敗路徑。"""
    w = _check_workers(workers)
    pg = play_game if play_game is not None else sim2.play_game
    fz = _freeze(U, candidate, baseline, opponents, plan, experiment_id, pg, _idle_impl)
    idt = fz['identity']
    plan, ids = idt['plan'], [o['opponent_id'] for o in opponents]
    tasks = [(oid, p['block_id']) for p in plan for oid in ids]
    if schedule is None:
        schedule = tasks
    else:
        schedule = [tuple(t) if isinstance(t, (list, tuple)) else t for t in schedule]
        if len(schedule) != len(tasks) or sorted(map(repr, schedule)) != sorted(map(repr, tasks)):
            raise ValueError('schedule 必須是 (opponent_id, block_id) 任務的排列')
    if sys.platform != 'win32':
        raise RuntimeSetupError('只支援 Windows spawn＋IDLE')
    seed_of = {p['block_id']: p['seed'] for p in plan}
    fps = {o['opponent_id']: o['fingerprint'] for o in idt['decks']['opponents']}
    eff = min(w, len(tasks))
    ctx = multiprocessing.get_context('spawn')
    started, outcomes = _now(), {}
    with _hash_seed_env():
        barrier = ctx.Barrier(eff)
        ex = (_executor_factory or cf.ProcessPoolExecutor)(max_workers=eff, mp_context=ctx, initializer=_init, initargs=(fz, barrier))
        try:
            probes = _collect_probes(ex, eff, fz['identity_sha256'])
            # 逐一 submit：中途失敗（例如 BrokenProcessPool）時保留已送出的 futures 照常收集；
            # 失敗的那個任務記 submit_failed:<型別>，其後全部記 not_dispatched，最後由 _merge 補成完整 coverage 的 incomplete run。
            futs, submit_error = {}, None
            for i, (oid, b) in enumerate(schedule):
                try:
                    futs[ex.submit(_pair_task, oid, b, seed_of[b])] = (oid, b)
                except Exception as e:
                    submit_error = type(e).__name__
                    outcomes[(oid, b)] = dict(refused='submit_failed:' + submit_error, meta={})
                    for t in schedule[i + 1:]:
                        outcomes[t] = dict(refused='not_dispatched', meta={})
                    break
            cf.wait(futs)
            for f, t in futs.items():
                e = f.exception()
                outcomes[t] = e if e is not None else f.result()
        finally:
            ex.shutdown(wait=True, cancel_futures=True)
    pids = sorted(p['pid'] for p in probes)
    m = _merge(plan, ids, fps, set(pids), outcomes)
    by_worker = {str(p): dict(tasks=0) for p in pids}
    for _, _, pid in m['task_workers']:
        if pid is not None: by_worker[str(pid)]['tasks'] += 1
    execution = dict(start_method='spawn', workers_requested=w, workers_effective=eff, worker_pids=pids,
                     worker_priorities=sorted({p['priority'] for p in probes}), hash_seed=HASH_SEED,
                     hash_probe_consistent=len({p['hash_probe'] for p in probes}) == 1,
                     schedule=[list(t) for t in schedule], submitted_tasks=len(futs), submit_error=submit_error,
                     task_workers=m['task_workers'], tasks_by_worker=by_worker,
                     games_played=m['games_played'], started_at=started, finished_at=_now(),
                     python_flags=dict(isolated=sys.flags.isolated, ignore_environment=sys.flags.ignore_environment))
    return dict(kind=PACKAGE_KIND, is_archive=False, is_public_release=False, sensitivity='internal-restricted',
                do_not_publish=True, runtime_version=RUNTIME_VERSION, identity=idt, identity_sha256=fz['identity_sha256'],
                cards=fz['cards'], run=m['run'], execution=execution, not_delivered=list(NOT_DELIVERED))


# ---- 結論 adapter 與契約驗證 ----

def _fail(msg):
    raise ContractError(msg)


def _check_package(pkg, require_sim2):
    if not isinstance(pkg, dict) or pkg.get('kind') != PACKAGE_KIND or pkg.get('is_archive') is not False \
            or pkg.get('is_public_release') is not False or pkg.get('do_not_publish') is not True:
        _fail('不是 internal-run-package')
    idt = pkg['identity']
    if pkg.get('identity_sha256') != _sha(idt): _fail('identity_sha256 不符')
    if require_sim2 and idt.get('engine_ref') != SIM2_ENGINE_REF: _fail(f"engine_ref 不是 {SIM2_ENGINE_REF}：{idt.get('engine_ref')}")
    run = pkg['run']
    if run.get('plan') != idt['plan']: _fail('run.plan 與 identity 不符')
    if run.get('opponents') != idt['decks']['opponents']: _fail('run.opponents 與 identity 指紋不符')
    if run.get('status') == 'complete' and pkg['execution'].get('games_played') != 2 * run.get('completed_pairs', -1):
        _fail('execution.games_played 與完成 pair 數不符')


def validate_fragment(frag, pkg, *, require_sim2=True):
    """程式契約：頂層欄位、seeds、pairing、逐 pair 形狀／順序／指紋／metric、彙總可重算、與 run 一致。"""
    _check_package(pkg, require_sim2)
    idt = pkg['identity']
    plan, opps = idt['plan'], idt['decks']['opponents']
    if not isinstance(frag, dict) or set(frag) != FRAG_KEYS: _fail('頂層欄位不符')
    if frag['design'] != 'paired': _fail('design 必須是 paired')
    if frag['seeds'] != [p['seed'] for p in plan]: _fail('seeds 與 plan 不符')
    if frag['pairing'] != PAIRING: _fail('pairing 定義不符')
    pr = frag['pair_results']
    order = [(p['block_id'], p['seed'], o['opponent_id'], o['fingerprint']) for p in plan for o in opps]
    if not isinstance(pr, list) or len(pr) != len(order): _fail('pair_results 數量不符')
    for r, (b, seed, oid, fp) in zip(pr, order):
        if not isinstance(r, dict) or set(r) != PAIR_KEYS: _fail('pair_results 欄位不符')
        if r['pair_id'] != json.dumps([b, oid], ensure_ascii=False, separators=(',', ':')) or r['opponent_id'] != oid \
                or r['opponent_fingerprint'] != fp or type(r['seed']) is not int or r['seed'] != seed:
            _fail(f'pair_results 順序／識別不符：{r.get("pair_id")!r}')
        if not _side_ok(r['candidate']) or not _side_ok(r['baseline']): _fail('outcome／metric_value 不符')
    if len({r['pair_id'] for r in pr}) != len(pr): _fail('pair_id 重複')
    if pr != pkg['run']['pair_results']: _fail('pair_results 不是該 run 的產出')
    want = [paired.aggregate(o['opponent_id'], o['fingerprint'], [r for r in pr if r['opponent_id'] == o['opponent_id']]) for o in opps]
    if frag['pairs'] != want: _fail('pairs 彙總無法由 pair_results 重算')
    for a in frag['pairs']:
        if (a['delta'] is None) != (a['se_delta'] is None) or (a['n'] < 2) != (a['delta'] is None):
            _fail('delta／se_delta 的 null 規則不符')


def fragment(pkg, *, require_sim2=True):
    """internal-run-package → 封存結論的配對欄位。incomplete 由 paired.conclusion_fragment 拒絕（IncompleteRun）。"""
    _check_package(pkg, require_sim2)
    frag = paired.conclusion_fragment(pkg['run'])
    validate_fragment(frag, pkg, require_sim2=require_sim2)
    return frag
