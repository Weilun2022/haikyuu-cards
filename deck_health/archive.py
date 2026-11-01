"""研究封存組裝器（第一版，synthetic-only）：internal-run-package → deck-health-research-archive。
- 純函式：不讀 disk 牌表／卡庫／私人 JSON、不呼叫 git／subprocess、不碰網路、不取現在時間（computed_at＝execution.finished_at）。
- 來源只有：runtime package（paired_runtime.execute 的回傳）、呼叫端顯式提供的合成 U、牌表、角色對應、meta 與 evidence。
- 輸出 provenance profile 固定 synthetic-runtime-snapshot-v1、mode=synthetic-only、formal_eligible=false；
  assert_formal_ready 對本 profile 永遠拒收，改 data_origin 也不會變正式。
- 三種身份分開：牌表指紋（deck-fingerprint-v1，SHA-1）、runtime U 記憶體 canonical hash（cards-used／cards-input）、
  卡庫檔案 bytes 的 SHA-256（只在呼叫端交 bytes 時由本模組自算；缺 bytes 一律哨兵，不拿 U hash 冒充）。
- engine.commit 固定哨兵；呼叫端給的 commit 只記成 provenance.execution_commit（caller-asserted）。
- identity／package／fragment hash 只表示組裝當下 Python canonical JSON 自洽，不是簽章、也不證明執行真實性。"""
import copy, hashlib, json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paired
import paired_runtime as rt

PROFILE = 'synthetic-runtime-snapshot-v1'
MODE = 'synthetic-only'
ASSEMBLER_VERSION = 'paired-archive-v1'
ARCHIVE_KIND = 'deck-health-research-archive'
SCHEMA_VERSION = 1
COMMIT_SENTINEL = 'synthetic:execution-commit-unrecorded'
CARDS_FILE_SENTINEL = 'synthetic:file-evidence-unavailable'
CARDS_FILE_ALGORITHM = 'sha256-of-caller-bytes'
SCHOOL_TAGS_SOURCE = 'synthetic'
SYNTHETIC_PREFIX = 'synthetic-'
DIRTY_SCOPE = paired.SOURCE_SCOPE   # 'execution-source-files'
TRUST = dict(hashes='self-consistent-at-assembly-not-signature', results='package-reported',
             execution='package-reported', overall='synthetic-unverified')
META_KEYS = {'release_id', 'research_version', 'conclusion_id', 'job_id'}
EVIDENCE_KEYS = {'execution_commit', 'source_status', 'cards_file'}
ARCHIVE_KEYS = {'kind', 'schema_version', 'release_id', 'research_version', 'data_origin', 'computed_at', 'sensitivity',
                'do_not_publish', 'engine', 'cards_data', 'decks', 'conclusions', 'provenance'}
CONCLUSION_KEYS = {'id', 'release_id', 'deck_id', 'design', 'job_id', 'seeds', 'result_files', 'pairs', 'baseline_deck',
                   'pairing', 'pair_results'}
HEX40 = re.compile(r'^[0-9a-f]{40}$')
LABEL = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
TOL = 1e-12


class ArchiveAssemblyError(rt.ContractError):
    def __init__(self, code, msg):
        super().__init__(f'{code}: {msg}')
        self.code = code


def _fail(code, msg):
    raise ArchiveAssemblyError(code, msg)


def _str(x):
    return isinstance(x, str) and x.strip() != ''


# ---- package：identity／CFG／seed plan／版本／execution／片段 ----

def _package(pkg, require_sim2):
    """回傳 fragment；所有 package 層拒收都在這裡。"""
    if not isinstance(pkg, dict) or pkg.get('kind') != rt.PACKAGE_KIND or not isinstance(pkg.get('identity'), dict):
        _fail('not_package', '不是 internal-run-package')
    idt = pkg['identity']
    try:
        same = pkg.get('identity_sha256') == rt._sha(idt)
    except ValueError:
        same = False
    if not same: _fail('identity_hash', 'identity_sha256 與 identity 重算不符')
    if pkg.get('runtime_version') != rt.RUNTIME_VERSION or idt.get('runtime_version') != rt.RUNTIME_VERSION \
            or idt.get('identity_version') != rt.IDENTITY_VERSION or pkg.get('not_delivered') != rt.NOT_DELIVERED \
            or idt.get('seed_derivation') != paired.SEED_DERIVATION_VERSION \
            or idt.get('decks', {}).get('fingerprint_version') != paired.FINGERPRINT_VERSION:
        _fail('mixed_version', 'runtime／identity／seed／指紋版本或 not_delivered 與本組裝器不符')
    try:
        cfg_ok = idt.get('cfg_sha256') == rt._sha(idt.get('cfg'))
    except ValueError:
        cfg_ok = False
    if not cfg_ok: _fail('cfg_hash', 'cfg_sha256 與 identity.cfg 重算不符')
    try:
        plan_ok = idt['plan'] == paired.seed_plan(idt['experiment_id'], [p['block_id'] for p in idt['plan']])
    except (ValueError, KeyError, TypeError):
        plan_ok = False
    if not plan_ok: _fail('seed_plan', 'plan 不是由 experiment_id 依 paired-seed-v1 推導')
    try:
        frag = rt.fragment(pkg, require_sim2=require_sim2)
    except paired.IncompleteRun as e:
        _fail('incomplete', str(e))
    except (rt.ContractError, KeyError, TypeError) as e:
        _fail('contract', f'{type(e).__name__}: {e}')
    ex = pkg.get('execution')
    if not isinstance(ex, dict) or set(ex) != _EXEC_KEYS or ex.get('hash_probe_consistent') is not True \
            or ex.get('worker_priorities') != [rt.IDLE_PRIORITY_CLASS] or ex.get('submit_error') is not None \
            or ex.get('hash_seed') != rt.HASH_SEED or ex.get('start_method') != 'spawn' \
            or ex.get('games_played') != 2 * pkg['run']['completed_pairs'] or not _str(ex.get('finished_at')):
        _fail('execution_inconsistent', 'execution 與完整 run 不一致（hash probe／IDLE／submit／場數／時間）')
    _check_stats(frag)
    return frag


_EXEC_KEYS = {'start_method', 'workers_requested', 'workers_effective', 'worker_pids', 'worker_priorities', 'hash_seed',
              'hash_probe_consistent', 'schedule', 'submitted_tasks', 'submit_error', 'task_workers', 'tasks_by_worker',
              'games_played', 'started_at', 'finished_at', 'python_flags'}


def recompute_pairs(pair_results, opponents):
    """逐 pair → 逐對手彙總（獨立重算，不呼叫 paired.aggregate）：兩側計數、plug-in SE、delta＝差的平均、se_delta＝樣本 SD/√N。"""
    out = []
    for o in opponents:
        rows = [r for r in pair_results if r['opponent_id'] == o['opponent_id']]
        n = len(rows)
        if n == 0: _fail('conclusion_mismatch', f"對手 {o['opponent_id']} 沒有 pair")
        cw = sum(1 for r in rows if r['candidate']['outcome'] == 'win')
        bw = sum(1 for r in rows if r['baseline']['outcome'] == 'win')
        p = cw / n
        d = [r['candidate']['metric_value'] - r['baseline']['metric_value'] for r in rows]
        delta = se_delta = None
        if n >= 2:
            delta = sum(d) / n
            se_delta = math.sqrt(sum((x - delta) ** 2 for x in d) / (n - 1)) / math.sqrt(n)
        out.append(dict(opponent_id=o['opponent_id'], opponent_fingerprint=o['fingerprint'], wins=cw, losses=n - cw, draws=0,
                        n=n, win_rate=p, se=math.sqrt(p * (1 - p) / n), delta=delta, se_delta=se_delta,
                        baseline=dict(wins=bw, losses=n - bw, draws=0)))
    return out


def _close(a, b):
    if a is None or b is None: return a is b
    return isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isfinite(a) and abs(a - b) <= TOL


def _same_pairs(got, want):
    if not isinstance(got, list) or len(got) != len(want): return False
    for g, w in zip(got, want):
        if not isinstance(g, dict) or set(g) != set(w): return False
        for k, v in w.items():
            if k in ('win_rate', 'se', 'delta', 'se_delta'):
                if not _close(g[k], v): return False
            elif g[k] != v or type(g[k]) is not type(v):
                return False
    return True


def _check_stats(frag):
    want = recompute_pairs(frag['pair_results'], [dict(opponent_id=p['opponent_id'], fingerprint=p['opponent_fingerprint'])
                                                  for p in frag['pairs']])
    if not _same_pairs(frag['pairs'], want): _fail('contract', '彙總無法由逐 pair 獨立重算')
    for a in frag['pairs']:
        if a['delta'] is not None and not -1 <= a['delta'] <= 1: _fail('contract', 'delta 超出 −1..1')


# ---- 呼叫端輸入：meta、evidence、牌表、角色 ----

def _meta(meta):
    if not isinstance(meta, dict) or set(meta) != META_KEYS or not all(_str(meta[k]) for k in META_KEYS):
        _fail('bad_meta', f'meta 只接受非空字串 {sorted(META_KEYS)}（不收 notes／flags／cfg）')
    for k in ('release_id', 'research_version'):
        if not meta[k].startswith(SYNTHETIC_PREFIX): _fail('not_synthetic', f'{k} 必須以 {SYNTHETIC_PREFIX} 開頭')
    return dict(meta)


def _evidence(evidence, U, pkg):
    ev = {} if evidence is None else evidence
    if not isinstance(ev, dict) or not set(ev) <= EVIDENCE_KEYS: _fail('bad_evidence', f'evidence 只接受 {sorted(EVIDENCE_KEYS)}')
    c = ev.get('execution_commit')
    if c is None:
        commit = dict(status='absent', value=None)
    elif isinstance(c, str) and HEX40.match(c):
        commit = dict(status='caller-asserted', value=c)
    else:
        _fail('bad_evidence', 'execution_commit 必須是 40 位小寫十六進位（只記為 caller assertion）')
    s = ev.get('source_status')
    if s is None:
        dirty = dict(scope=DIRTY_SCOPE, status='not-recorded', paths=None)
    elif isinstance(s, dict) and s and all(k in paired.EXECUTION_SOURCES and _str(v) for k, v in s.items()):
        dirty = dict(scope=DIRTY_SCOPE, status='caller-asserted', paths=dict(sorted(s.items())))
    else:
        _fail('bad_evidence', 'source_status 只能列 execution-source-files 內的路徑與非空狀態字串')
    f = ev.get('cards_file')
    if f is None:
        return commit, dirty, dict(status='absent', algorithm=None, sha256=None, byte_length=None, label=None, linkage='none'), \
            CARDS_FILE_SENTINEL
    if not isinstance(f, dict) or not {'label', 'bytes'} <= set(f) <= {'label', 'bytes', 'derivation'}:
        _fail('bad_evidence', 'cards_file 需為 {label, bytes[, derivation]}')
    b = f['bytes']
    if isinstance(b, str): _fail('hex_without_bytes', '只收原始 bytes，自行宣告的 hash 字串不算檔案證據')
    if not isinstance(b, (bytes, bytearray)): _fail('bad_evidence', 'cards_file.bytes 必須是 bytes')
    if not isinstance(f['label'], str) or not LABEL.match(f['label']): _fail('bad_evidence', 'label 只能是不含路徑的檔名')
    der = f.get('derivation')
    if der is None:
        linkage = 'unlinked'
    elif der == 'synthetic-json-utf8':
        try:
            parsed = json.loads(bytes(b).decode('utf-8'))
            linked = parsed == U and rt._sha(parsed) == pkg['cards']['input']['sha256']
        except (UnicodeDecodeError, ValueError):
            linked = False
        if not linked: _fail('cards_file_unlinked', 'bytes 解析後與呼叫端 U 不完全相等，不能宣稱 linked')
        linkage = 'synthetic-json-equals-U'
    else:
        _fail('bad_evidence', f'不支援的 derivation：{der!r}')
    h = hashlib.sha256(bytes(b)).hexdigest()
    return commit, dirty, dict(status='caller-bytes', algorithm=CARDS_FILE_ALGORITHM, sha256=h, byte_length=len(b),
                               label=f['label'], linkage=linkage), 'sha256:' + h


def _decks(decks, U):
    if not isinstance(decks, (list, tuple)) or not decks: _fail('bad_decks', 'decks 必須是非空串列')
    out, seen = [], set()
    for d in decks:
        if not isinstance(d, dict) or set(d) != {'deck_id', 'display_name', 'deck'} or not _str(d['deck_id']) \
                or not _str(d['display_name']):
            _fail('bad_decks', '每副牌需為 {deck_id, display_name, deck}')
        if d['deck_id'] in seen: _fail('bad_decks', f"deck_id 重複：{d['deck_id']}（同一 ID 只能對應一副牌）")
        seen.add(d['deck_id'])
        try:
            paired.check_deck(U, d['deck'])
        except ValueError as e:
            _fail('bad_decks', f"{d['deck_id']}：{e}")
        cards = [[n, c] for n, c in sorted(d['deck'].items())]
        out.append(dict(deck_id=d['deck_id'], display_name=d['display_name'], cards=cards,
                        fingerprint=paired.deck_fingerprint(d['deck'])))
    return out


def _roles(roles):
    ok = isinstance(roles, dict) and set(roles) == {'candidate', 'baseline', 'opponents'} \
        and all(isinstance(roles[k], dict) and set(roles[k]) == {'deck_id'} and _str(roles[k]['deck_id'])
                for k in ('candidate', 'baseline')) \
        and isinstance(roles['opponents'], (list, tuple)) and roles['opponents'] \
        and all(isinstance(o, dict) and set(o) == {'opponent_id', 'deck_id'} and _str(o['opponent_id']) and _str(o['deck_id'])
                for o in roles['opponents'])
    if not ok: _fail('role_mismatch', 'roles 需為 {candidate:{deck_id}, baseline:{deck_id}, opponents:[{opponent_id, deck_id}]}')
    return dict(candidate=dict(roles['candidate']), baseline=dict(roles['baseline']),
                opponents=[dict(opponent_id=o['opponent_id'], deck_id=o['deck_id']) for o in roles['opponents']])


def _check_roles(roles, decks_by_id, idt):
    """角色一一覆蓋 runtime 對手（含順序）、引用存在、指紋與 identity 一致；所有 archive 牌表都必須被引用。"""
    ids = [o['opponent_id'] for o in idt['decks']['opponents']]
    if [o['opponent_id'] for o in roles['opponents']] != ids:
        _fail('role_mismatch', f'opponents 角色必須依序一一覆蓋 runtime 對手 {ids}')
    want = [(roles['candidate']['deck_id'], idt['decks']['candidate'], 'candidate'),
            (roles['baseline']['deck_id'], idt['decks']['baseline'], 'baseline')] + \
        [(r['deck_id'], o['fingerprint'], r['opponent_id']) for r, o in zip(roles['opponents'], idt['decks']['opponents'])]
    for deck_id, fp, role in want:
        if deck_id not in decks_by_id: _fail('role_mismatch', f'角色 {role} 引用不存在的牌表 {deck_id}')
        if decks_by_id[deck_id]['fingerprint'] != fp: _fail('deck_tampered', f'角色 {role} 的牌表指紋與 runtime identity 不符')
    unused = set(decks_by_id) - {w[0] for w in want}
    if unused: _fail('bad_decks', f'未被任何角色引用的牌表：{sorted(unused)}')
    return {w[0] for w in want}


def _check_cards_memory(U, pkg, decks_by_id, used_ids):
    idt, cards = pkg['identity'], pkg.get('cards')
    try:
        nos = sorted({n for i in used_ids for n, _ in decks_by_id[i]['cards']})
        ok = isinstance(U, dict) and isinstance(cards, dict) \
            and rt._sha(U) == cards['input']['sha256'] and cards['input']['card_count'] == len(U) \
            and rt._sha({n: U[n] for n in nos}) == idt['cards_used']['sha256'] == cards['used']['sha256'] \
            and cards['used']['card_count'] == len(nos)
    except (KeyError, TypeError, ValueError):
        ok = False
    if not ok: _fail('cards_memory_mismatch', '呼叫端 U 的 input／used canonical hash 與 package 不一致')


# ---- 組裝 ----

def assemble_synthetic_archive(pkg, *, U, decks, roles, meta, evidence=None, require_sim2=True):
    """回傳內嵌 provenance 的 synthetic-only 研究封存（dict）。任何不符一律 ArchiveAssemblyError(code)。"""
    m = _meta(meta)
    frag = _package(pkg, require_sim2)
    idt = pkg['identity']
    arch_decks = _decks(decks, U)
    r = _roles(roles)
    by_id = {d['deck_id']: d for d in arch_decks}
    used = _check_roles(r, by_id, idt)
    _check_cards_memory(U, pkg, by_id, used)
    commit, dirty, file_ev, cards_hash = _evidence(evidence, U, pkg)
    run = pkg['run']
    conclusion = dict(id=m['conclusion_id'], release_id=m['release_id'], deck_id=r['candidate']['deck_id'], job_id=m['job_id'],
                      result_files=[], baseline_deck=dict(deck_id=r['baseline']['deck_id'], fingerprint=idt['decks']['baseline']),
                      **copy.deepcopy(frag))
    prov = dict(profile=PROFILE, mode=MODE, formal_eligible=False, assembler_version=ASSEMBLER_VERSION,
                conclusion_id=m['conclusion_id'], roles=r,
                package=dict(kind=pkg['kind'], runtime_version=pkg['runtime_version'], identity_sha256=pkg['identity_sha256'],
                             package_sha256=rt._sha(pkg), fragment_sha256=rt._sha(frag)),
                identity=copy.deepcopy(idt), execution=copy.deepcopy(pkg['execution']),
                run=dict(status=run['status'], usable=run['usable'], expected_pairs=run['expected_pairs'],
                         completed_pairs=run['completed_pairs'], failure_count=len(run['failures'])),
                cards=dict(memory=copy.deepcopy(pkg['cards']), file=file_ev),
                execution_commit=commit, dirty_scope=dirty, trust=dict(TRUST))
    archive = dict(kind=ARCHIVE_KIND, schema_version=SCHEMA_VERSION, release_id=m['release_id'],
                   research_version=m['research_version'], data_origin=MODE, computed_at=pkg['execution']['finished_at'],
                   sensitivity='internal-restricted', do_not_publish=True,
                   engine=dict(commit=COMMIT_SENTINEL, cards_data_hash=cards_hash, cfg=copy.deepcopy(idt['cfg'])),
                   cards_data=dict(hash=cards_hash, school_tags_source=SCHOOL_TAGS_SOURCE),
                   decks=arch_decks, conclusions=[conclusion], provenance=prov)
    verify_archive(archive, pkg, U=U, require_sim2=require_sim2)
    return archive


# ---- 完整入口重驗（不依賴組裝輸入，只用 archive＋package＋U）----

def verify_archive(archive, pkg, *, U, require_sim2=True):
    frag = _package(pkg, require_sim2)
    idt = pkg['identity']
    if not isinstance(archive, dict) or set(archive) != ARCHIVE_KEYS: _fail('archive_mismatch', '封存頂層欄位不符')
    a = archive
    try:
        rt._canon(a)
    except ValueError as e:
        _fail('archive_mismatch', str(e))
    eng, cd = a['engine'], a['cards_data']
    if a['kind'] != ARCHIVE_KIND or a['schema_version'] != SCHEMA_VERSION or a['data_origin'] != MODE \
            or a['sensitivity'] != 'internal-restricted' or a['do_not_publish'] is not True \
            or a['computed_at'] != pkg['execution']['finished_at'] \
            or not all(isinstance(a[k], str) and a[k].startswith(SYNTHETIC_PREFIX) for k in ('release_id', 'research_version')) \
            or not isinstance(eng, dict) or set(eng) != {'commit', 'cards_data_hash', 'cfg'} or eng['commit'] != COMMIT_SENTINEL \
            or eng['cfg'] != idt['cfg'] or not isinstance(cd, dict) or set(cd) != {'hash', 'school_tags_source'} \
            or cd['school_tags_source'] != SCHOOL_TAGS_SOURCE or cd['hash'] != eng['cards_data_hash']:
        _fail('archive_mismatch', '封存固定欄位（synthetic-only／哨兵 commit／CFG／cards hash／時間）不符')
    pv = a['provenance']
    if not isinstance(pv, dict): _fail('provenance_mismatch', 'provenance 必須是物件')
    try:
        r = _roles(pv.get('roles'))
    except ArchiveAssemblyError:
        _fail('provenance_mismatch', 'provenance.roles 形狀不符')
    # 牌表：內容可重算出宣告指紋、符合 40 張規則；角色指紋對 identity
    decks = a['decks']
    if not isinstance(decks, list) or not decks: _fail('deck_tampered', 'decks 必須是非空串列')
    by_id = {}
    for d in decks:
        if not isinstance(d, dict) or set(d) != {'deck_id', 'display_name', 'cards', 'fingerprint'} or d.get('deck_id') in by_id:
            _fail('deck_tampered', '牌表形狀不符或 deck_id 重複')
        cards = d['cards']
        if not isinstance(cards, list) or cards != sorted(cards) or len({c[0] for c in cards}) != len(cards):
            _fail('deck_tampered', f"{d['deck_id']} 的 cards 必須依卡號排序且不重複")
        deck = {c[0]: c[1] for c in cards}
        try:
            paired.check_deck(U, deck)
        except ValueError as e:
            _fail('deck_tampered', f"{d['deck_id']}：{e}")
        if paired.deck_fingerprint(deck) != d['fingerprint']: _fail('deck_tampered', f"{d['deck_id']} 的指紋與牌表內容不符")
        by_id[d['deck_id']] = d
    used = _check_roles(r, by_id, idt)
    _check_cards_memory(U, pkg, by_id, used)
    # 結論：與 runtime 片段一致，且統計可由逐 pair 獨立重算
    cs = a['conclusions']
    if not isinstance(cs, list) or len(cs) != 1 or not isinstance(cs[0], dict) or set(cs[0]) != CONCLUSION_KEYS:
        _fail('conclusion_mismatch', '第一版一個 package 只對應一個 paired 結論')
    c = cs[0]
    if c['id'] != pv.get('conclusion_id') or c['release_id'] != a['release_id'] or c['deck_id'] != r['candidate']['deck_id'] \
            or not _str(c['job_id']) or c['result_files'] != [] \
            or c['baseline_deck'] != dict(deck_id=r['baseline']['deck_id'], fingerprint=idt['decks']['baseline']):
        _fail('conclusion_mismatch', '結論的 id／牌表角色／baseline_deck／result_files 不符')
    if any(c[k] != frag[k] for k in ('design', 'seeds', 'pairing', 'pair_results')) or not _same_pairs(c['pairs'], frag['pairs']):
        _fail('conclusion_mismatch', '結論與 runtime 片段不一致')
    try:
        re_pairs = recompute_pairs(c['pair_results'], idt['decks']['opponents'])
    except (KeyError, TypeError):
        _fail('conclusion_mismatch', 'pair_results 形狀不符')
    if not _same_pairs(c['pairs'], re_pairs): _fail('conclusion_mismatch', '彙總無法由逐 pair 重算')
    # provenance：快照與 package 一致；狀態欄位彼此自洽
    run = pkg['run']
    want = dict(profile=PROFILE, mode=MODE, formal_eligible=False, assembler_version=ASSEMBLER_VERSION,
                package=dict(kind=pkg['kind'], runtime_version=pkg['runtime_version'], identity_sha256=pkg['identity_sha256'],
                             package_sha256=rt._sha(pkg), fragment_sha256=rt._sha(frag)),
                identity=idt, execution=pkg['execution'],
                run=dict(status=run['status'], usable=run['usable'], expected_pairs=run['expected_pairs'],
                         completed_pairs=run['completed_pairs'], failure_count=len(run['failures'])),
                trust=TRUST)
    keys = set(want) | {'conclusion_id', 'roles', 'cards', 'execution_commit', 'dirty_scope'}
    if set(pv) != keys or any(pv[k] != v for k, v in want.items()):
        _fail('provenance_mismatch', 'provenance 快照與 package 不一致')
    if not isinstance(pv['cards'], dict) or set(pv['cards']) != {'memory', 'file'} or pv['cards']['memory'] != pkg['cards']:
        _fail('provenance_mismatch', 'provenance.cards.memory 與 package 不一致')
    _check_file_evidence(pv['cards']['file'], cd['hash'])
    ec = pv['execution_commit']
    if ec not in (dict(status='absent', value=None),) and not (
            isinstance(ec, dict) and set(ec) == {'status', 'value'} and ec['status'] == 'caller-asserted'
            and isinstance(ec['value'], str) and HEX40.match(ec['value'])):
        _fail('provenance_mismatch', 'execution_commit 只能是 absent 或 caller-asserted＋40 位 hex')
    ds = pv['dirty_scope']
    if ds != dict(scope=DIRTY_SCOPE, status='not-recorded', paths=None) and not (
            isinstance(ds, dict) and set(ds) == {'scope', 'status', 'paths'} and ds['scope'] == DIRTY_SCOPE
            and ds['status'] == 'caller-asserted' and isinstance(ds['paths'], dict) and ds['paths']
            and all(k in paired.EXECUTION_SOURCES and _str(v) for k, v in ds['paths'].items())):
        _fail('provenance_mismatch', 'dirty_scope 只能是 not-recorded 或 caller-asserted 的 execution-source-files')


def _check_file_evidence(f, cards_hash):
    absent = dict(status='absent', algorithm=None, sha256=None, byte_length=None, label=None, linkage='none')
    if f == absent and cards_hash == CARDS_FILE_SENTINEL:
        return
    ok = isinstance(f, dict) and set(f) == set(absent) and f['status'] == 'caller-bytes' \
        and f['algorithm'] == CARDS_FILE_ALGORITHM and isinstance(f['sha256'], str) and re.match(r'^[0-9a-f]{64}$', f['sha256']) \
        and type(f['byte_length']) is int and f['byte_length'] >= 0 and isinstance(f['label'], str) and LABEL.match(f['label']) \
        and f['linkage'] in ('unlinked', 'synthetic-json-equals-U') and cards_hash == 'sha256:' + f['sha256']
    if not ok: _fail('provenance_mismatch', '卡庫檔案證據與 cards_data.hash 不一致（缺 bytes 必須是哨兵）')


def assert_formal_ready(archive):
    """正式封存入口閘門：第一版沒有正式 profile，永遠拒收；synthetic profile 改 data_origin 也不會變正式。"""
    pv = archive.get('provenance') if isinstance(archive, dict) else None
    if isinstance(pv, dict) and pv.get('profile') == PROFILE:
        _fail('synthetic_profile_not_formal', f'{PROFILE} 只供 synthetic 驗證，不能作正式研究封存')
    _fail('formal_not_delivered', '正式研究 profile 尚未交付')
