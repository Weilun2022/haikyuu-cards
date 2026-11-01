"""A2 runtime（paired_runtime.py）測試：spawn worker、IDLE、pair 原子派工、凍結狀態、identity／hash 語意、結論 adapter。
只用合成卡（SYN-RT-*）與合成牌表，不讀任何私人 JSON／牌表。
除 test_real_sim_spawn_replay（預設 skip；只在 `-k test_real_sim_spawn_replay` 精確指定時執行，共 12 場）以外，
worker 內只跑本檔的 stub，不進 sim2.play_game。"""
import concurrent.futures as cf
import copy, ctypes, glob, hashlib, json, os, random, re, sys, uuid
from concurrent.futures.process import BrokenProcessPool

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)   # spawn worker 要能 import 本模組的 stub
import paired
import paired_runtime as rt
import sim2

IDLE = 0x40


# ---- 合成卡庫與合法牌表（每張卡號最多 4 張、每副 40 張）----

def raw(i):
    return dict(card_no=f'SYN-RT-{i:03d}', name=f'合成選手{i:03d}', category='CHARACTER',
                position=['S', 'WS', 'MB', 'OP', 'L', 'WS'][i % 6], school='合成高校', school_tags=['合成高校'],
                srv=1 + i % 3, blk=1 + i % 4, rcv=2 + i % 4, tos=1 + (i * 2) % 5, atk=2 + (i * 3) % 5,
                affiliation='合成高校・1年', skill_jp='-')


U = {raw(i)['card_no']: raw(i) for i in list(range(1, 25)) + [90]}   # SYN-RT-090 不在任何牌表
UNUSED = 'SYN-RT-090'


def deck(*ids):
    return {f'SYN-RT-{i:03d}': 4 for i in ids}


CAND = deck(*range(1, 11))             # 含 SYN-RT-010
BASE = deck(*range(1, 10), 11)         # 以 011 取代 010
OPPS = [dict(opponent_id='opp-x', deck=deck(*range(13, 23))), dict(opponent_id='opp-y', deck=deck(*range(15, 25)))]
OPP_OF_FIRST = {'SYN-RT-013': 'opp-x', 'SYN-RT-015': 'opp-y'}   # build_isolated 依卡號排序，第一張可辨識對手
EXP = 'rt-exp'
BLOCKS = ['b0', 'b1', 'b2']
PLAN = paired.seed_plan(EXP, BLOCKS)
SEED_OF = {p['block_id']: p['seed'] for p in PLAN}
R0 = {b: random.Random(s).random() for b, s in SEED_OF.items()}   # 每個 half 第一個 rng.random()，用來辨識 block
BLOCK_OF_R0 = {v: k for k, v in R0.items()}


# ---- spawn worker 內執行的 stub（模組層級，才能被 pickle）----

def _side(cardsA):
    return 'candidate' if any(c.no == 'SYN-RT-010' for c in cardsA) else 'baseline'


def _trace(cardsA, cardsB, r0):
    d = os.environ.get('PRT_TRACE_DIR')
    if not d:
        return
    rec = dict(pid=os.getpid(), side=_side(cardsA), opp=OPP_OF_FIRST.get(cardsB[0].no), r0=r0,
               prio=rt._current_priority(), w_cost=sim2.CFG['w_cost'], hash_rand=sys.flags.hash_randomization)
    with open(os.path.join(d, f'{os.getpid()}-{uuid.uuid4().hex}.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f)


def fake_game(cardsA, cardsB, rng, log=None):
    r0 = rng.random()
    _trace(cardsA, cardsB, r0)
    k = 4 if _side(cardsA) == 'candidate' else 0
    return dict(winner='A' if (r0 + 0.1 * k) % 1 < 0.5 else 'B')


def other_game(cardsA, cardsB, rng, log=None):
    return fake_game(cardsA, cardsB, rng)


def fail_cand_b1(cardsA, cardsB, rng, log=None):
    r0 = rng.random()
    if _side(cardsA) == 'candidate' and r0 == R0['b1']:
        raise RuntimeError('boom')
    _trace(cardsA, cardsB, r0)
    return dict(winner='A' if r0 < 0.5 else 'B')


def crash_b1(cardsA, cardsB, rng, log=None):
    r0 = rng.random()
    if r0 == R0['b1']:
        os._exit(3)
    return dict(winner='A' if r0 < 0.5 else 'B')


def cfg_mutating_game(cardsA, cardsB, rng, log=None):
    sim2.CFG['w_cost'] = sim2.CFG['w_cost'] + 1
    return fake_game(cardsA, cardsB, rng)


def _fail_idle():
    raise OSError('模擬 SetPriorityClass 失敗')


# ---- 輔助 ----

def run(workers=1, opps=OPPS, plan=PLAN, game=fake_game, **kw):
    return rt.execute(U, CAND, BASE, opps, plan, experiment_id=EXP, workers=workers, play_game=game, **kw)


def traces(d):
    out = []
    for p in sorted(glob.glob(os.path.join(str(d), '*.json'))):
        with open(p, encoding='utf-8') as f:
            out.append(json.load(f))
    return out


def tasks_of(opps=OPPS, plan=PLAN):
    return [(o['opponent_id'], p['block_id']) for p in plan for o in opps]


@pytest.fixture(scope='module')
def base_pkg():
    return run(workers=2)


@pytest.fixture
def trace_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('PRT_TRACE_DIR', str(tmp_path))
    return tmp_path


def boom(*a, **k):
    raise AssertionError('父程序不得執行引擎／配對對局')


# ---- workers ----

@pytest.mark.parametrize('w', [1, 2, 16])
def test_workers_accepts_1_to_16(w):
    assert rt._check_workers(w) == w


@pytest.mark.parametrize('w', [0, 17, -1, True, False, 1.0, 2.0, '4', None, 2 ** 70])
def test_workers_rejects_bool_non_int_and_out_of_range(w):
    with pytest.raises(ValueError):
        rt._check_workers(w)


def test_runtime_source_never_reads_dh_workers_or_parallel():
    with open(rt.__file__, encoding='utf-8') as f:
        src = f.read()
    assert 'DH_WORKERS' not in src
    assert not re.search(r'^\s*(import|from)\s+parallel\b', src, re.M)


# ---- spawn：DH_WORKERS、pair 原子、父程序不跑引擎、IDLE ----

def test_spawn_ignores_dh_workers_pairs_atomic_parent_runs_no_engine(trace_dir, monkeypatch):
    monkeypatch.setenv('DH_WORKERS', '99')
    monkeypatch.delenv('PYTHONHASHSEED', raising=False)
    for mod, name in ((sim2, 'play_game'), (paired, 'play_half'), (paired, 'run_paired'), (paired, 'build_isolated')):
        monkeypatch.setattr(mod, name, boom)
    prio_before = rt._current_priority()
    pkg = run(workers=2)
    assert rt._current_priority() == prio_before          # 父程序優先權不變
    assert 'PYTHONHASHSEED' not in os.environ               # 暫改的環境變數已還原
    ex, r = pkg['execution'], pkg['run']
    assert r['status'] == 'complete' and r['usable'] is True and r['failures'] == []
    assert ex['workers_requested'] == 2 and ex['workers_effective'] == 2
    pids = set(ex['worker_pids'])
    assert len(pids) == 2 and os.getpid() not in pids
    assert ex['worker_priorities'] == [IDLE]
    assert ex['games_played'] == 2 * len(tasks_of()) == 12
    assert pkg['identity']['engine_ref'] == 'test_paired_runtime:fake_game'
    tr = traces(trace_dir)
    assert len(tr) == 12
    assert all(t['pid'] in pids and t['prio'] == IDLE and t['hash_rand'] == 0 for t in tr)
    groups = {}
    for t in tr:
        groups.setdefault((t['opp'], BLOCK_OF_R0[t['r0']]), []).append(t)
    assert set(groups) == set(tasks_of())
    tw = {(oid, b): pid for b, oid, pid in ex['task_workers']}
    for key, g in groups.items():          # pair 原子：兩個 half 同一 worker、各一次
        assert sorted(t['side'] for t in g) == ['baseline', 'candidate']
        assert len({t['pid'] for t in g}) == 1 and g[0]['pid'] == tw[key]


def test_results_independent_of_workers_schedule_and_match_in_process_reference(base_pkg):
    a = run(workers=1)
    b = run(workers=3, schedule=list(reversed(tasks_of())))
    ref = paired.run_paired(U, CAND, BASE, OPPS, PLAN, play_game=fake_game)   # 測試行程內只跑 stub 作參照
    assert a['run'] == b['run'] == base_pkg['run'] == ref
    assert a['identity'] == b['identity'] == base_pkg['identity']
    assert a['identity_sha256'] == b['identity_sha256'] == base_pkg['identity_sha256']
    assert [a['execution']['workers_effective'], base_pkg['execution']['workers_effective'], b['execution']['workers_effective']] == [1, 2, 3]
    assert b['execution']['schedule'] == [list(t) for t in reversed(tasks_of())]
    assert all(p['execution']['hash_probe_consistent'] is True for p in (a, b, base_pkg))


# ---- 失敗：half 失敗、worker 死亡、setup 失敗零場 ----

def test_half_failure_marks_incomplete_and_fragment_refused():
    pkg = run(workers=2, game=fail_cand_b1)
    r = pkg['run']
    assert r['status'] == 'incomplete' and r['usable'] is False
    assert r['expected_pairs'] == 6 and r['completed_pairs'] == len(r['pair_results']) == 4
    assert all(p['seed'] != SEED_OF['b1'] for p in r['pair_results'])
    assert [(f['opponent_id'], f['block_id'], f['side'], f['reason']) for f in r['failures']] == \
        [('opp-x', 'b1', 'candidate', 'exception:RuntimeError'), ('opp-y', 'b1', 'candidate', 'exception:RuntimeError')]
    with pytest.raises(paired.IncompleteRun):
        rt.fragment(pkg, require_sim2=False)


def test_worker_death_marks_lost_no_half_pair_and_fragment_refused():
    pkg = run(workers=1, opps=OPPS[:1], game=crash_b1)
    r = pkg['run']
    assert r['status'] == 'incomplete' and r['usable'] is False
    lost = {f['block_id'] for f in r['failures'] if f['reason'] == 'worker_lost' and f['side'] == 'pair'}
    assert 'b1' in lost
    assert {p['seed'] for p in r['pair_results']} <= {SEED_OF['b0']}
    for p in r['pair_results']:
        assert set(p['candidate']) == set(p['baseline']) == {'outcome', 'metric_value'}
    covered = {f['block_id'] for f in r['failures']} | {b for b in BLOCKS if SEED_OF[b] in {p['seed'] for p in r['pair_results']}}
    assert covered == set(BLOCKS)
    with pytest.raises(paired.IncompleteRun):
        rt.fragment(pkg, require_sim2=False)


def test_idle_setup_failure_fails_closed_with_zero_games(trace_dir, monkeypatch):
    monkeypatch.delenv('PYTHONHASHSEED', raising=False)
    prio_before = rt._current_priority()
    with pytest.raises(rt.RuntimeSetupError):
        run(workers=2, _idle_impl=_fail_idle)
    assert traces(trace_dir) == []
    assert rt._current_priority() == prio_before
    assert 'PYTHONHASHSEED' not in os.environ


def test_manual_env_changed_after_import_fails_closed_with_zero_games(trace_dir, monkeypatch):
    monkeypatch.setenv('DH_BATCH5', '0')     # 父程序已載入含第 5 批的 MANUAL；worker 重新 import 會不同
    with pytest.raises(rt.RuntimeSetupError, match='manual_skills_hash'):
        run(workers=1, opps=OPPS[:1], plan=PLAN[:1])
    assert traces(trace_dir) == []


# ---- 凍結狀態 ----

def test_parent_cfg_frozen_into_workers_and_identity_tracks_cfg(trace_dir, monkeypatch):
    before = rt.identity_for(U, CAND, BASE, OPPS[:1], PLAN[:1], experiment_id=EXP, play_game=fake_game)
    monkeypatch.setitem(sim2.CFG, 'w_cost', 7.5)
    after = rt.identity_for(U, CAND, BASE, OPPS[:1], PLAN[:1], experiment_id=EXP, play_game=fake_game)
    assert before != after and after['cfg']['w_cost'] == 7.5
    pkg = run(workers=1, opps=OPPS[:1], plan=PLAN[:1])
    assert pkg['identity'] == after and pkg['run']['status'] == 'complete'
    tr = traces(trace_dir)
    assert len(tr) == 2 and all(t['w_cost'] == 7.5 for t in tr)


def test_cfg_mutation_inside_worker_detected_and_run_incomplete():
    pkg = run(workers=1, opps=OPPS[:1], plan=PLAN[:2], game=cfg_mutating_game)
    r = pkg['run']
    assert r['status'] == 'incomplete' and r['pair_results'] == []
    assert len(r['failures']) == 2 and all(f['side'] == 'pair' and f['reason'].startswith('state_drift:') and 'cfg' in f['reason']
                                           for f in r['failures'])
    with pytest.raises(paired.IncompleteRun):
        rt.fragment(pkg, require_sim2=False)


def _fz():
    return rt._freeze(U, CAND, BASE, OPPS, PLAN, EXP, fake_game)


def test_verify_clean_in_same_state():
    assert rt._verify(_fz()) == []


@pytest.mark.parametrize('path,value,name', [
    (('cfg_sha256',), 'x', 'cfg'),
    (('manual_skills_hash',), 'x', 'manual_skills_hash'),
    (('manual_env', 'DH_BATCH5'), '0', 'manual_env'),
    (('sources', 'combined_sha256'), 'x', 'sources'),
    (('sources', 'sha256', 'deck_health/sim2.py'), 'x', 'sources'),
    (('cards_used', 'sha256'), 'x', 'cards_used'),
    (('decks', 'candidate'), 'x', 'fingerprints'),
    (('engine_ref',), 'sim2:play_game', 'engine_ref'),
])
def test_verify_detects_each_tampered_frozen_value(path, value, name):
    fz = _fz()
    d = fz['identity']
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = value
    assert rt._verify(fz) == [name]


def test_verify_detects_changed_card_payload():
    fz = _fz()
    fz['U_sub']['SYN-RT-001']['atk'] = 99
    assert rt._verify(fz) == ['cards_used']


def test_manual_env_keys_cover_every_environ_read_in_execution_sources():
    found = set()
    for p in paired.EXECUTION_SOURCES:
        found |= set(re.findall(r"environ\.get\(\s*'([A-Z0-9_]+)'", paired._read_source(p).decode('utf-8')))
    assert found == set(rt.MANUAL_ENV_KEYS_FULL)
    assert set(paired.MANUAL_ENV_KEYS) < set(rt.MANUAL_ENV_KEYS_FULL)   # paired.manifest 的清單不完整（已知限制）


def test_sources_cover_execution_files_plus_runtime_with_documented_algorithm():
    src = rt.source_hashes()
    assert set(src['sha256']) == set(paired.EXECUTION_SOURCES) | {'deck_health/paired_runtime.py'}
    h = hashlib.sha256()
    for p in sorted(src['sha256']):
        b = paired._read_source(p) if p != 'deck_health/paired_runtime.py' else open(rt.__file__, 'rb').read()
        assert src['sha256'][p] == hashlib.sha256(b).hexdigest()
        pb = p.encode('utf-8')
        h.update(b'%d\0' % len(pb)); h.update(pb); h.update(b'\0%d\0' % len(b)); h.update(b)
    assert src['combined_sha256'] == h.hexdigest()
    with pytest.raises(ValueError):
        rt._read_runtime_source('deck_health/sim2.py')


def test_parent_reads_only_allowlisted_source_files(monkeypatch):
    import builtins
    real, seen = builtins.open, []
    def rec(f, *a, **k):
        seen.append(os.path.normcase(os.path.abspath(f)))
        return real(f, *a, **k)
    monkeypatch.setattr(builtins, 'open', rec)
    rt._freeze(U, CAND, BASE, OPPS, PLAN, EXP, fake_game)
    monkeypatch.setattr(builtins, 'open', real)
    allowed = {os.path.normcase(os.path.join(paired.REPO_ROOT, *p.split('/'))) for p in rt.SOURCES}
    assert seen and set(seen) <= allowed


# ---- cards hash 語意 ----

def canon_sha(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def test_cards_used_hash_only_covers_used_card_nos_with_documented_algorithm():
    c = rt.cards_hashes(U, CAND, BASE, OPPS)
    used = sorted(set(CAND) | set(BASE) | {n for o in OPPS for n in o['deck']})
    assert UNUSED not in used
    assert c['used']['sha256'] == canon_sha({n: U[n] for n in used}) and c['used']['card_count'] == len(used)
    assert c['input']['sha256'] == canon_sha(U) and c['input']['card_count'] == len(U)
    assert 'cards-used-v1' in c['used']['algorithm'] and 'cards-input-v1' in c['input']['algorithm']
    assert 'cards_data.js' in c['note']
    U2 = copy.deepcopy(U); U2[UNUSED]['name'] = '改名'
    c2 = rt.cards_hashes(U2, CAND, BASE, OPPS)
    assert c2['used']['sha256'] == c['used']['sha256'] and c2['input']['sha256'] != c['input']['sha256']
    U3 = copy.deepcopy(U); U3['SYN-RT-001']['atk'] = 9
    assert rt.cards_hashes(U3, CAND, BASE, OPPS)['used']['sha256'] != c['used']['sha256']


@pytest.mark.parametrize('bad', [{1, 2}, float('nan'), object()])
def test_cards_hash_rejects_non_canonical_values(bad):
    U2 = copy.deepcopy(U); U2['SYN-RT-001']['extra'] = bad
    with pytest.raises(ValueError):
        rt.cards_hashes(U2, CAND, BASE, OPPS)


def test_package_never_claims_cards_data_file_hash(base_pkg):
    blob = json.dumps(base_pkg, ensure_ascii=False)
    assert 'cards_data_hash' not in blob and '"cards_data"' not in blob
    assert base_pkg['cards']['used']['sha256'] == base_pkg['identity']['cards_used']['sha256']


# ---- identity ----

def test_identity_links_inputs_and_excludes_execution():
    idt = rt.identity_for(U, CAND, BASE, OPPS, PLAN, experiment_id=EXP, play_game=fake_game)
    assert idt['experiment_id'] == EXP and idt['seed_derivation'] == 'paired-seed-v1' and idt['plan'] == PLAN
    assert idt['decks'] == dict(fingerprint_version='deck-fingerprint-v1', candidate=paired.deck_fingerprint(CAND),
                                baseline=paired.deck_fingerprint(BASE),
                                opponents=[dict(opponent_id=o['opponent_id'], fingerprint=paired.deck_fingerprint(o['deck'])) for o in OPPS])
    assert idt['cfg'] == sim2.CFG and idt['manual_skills_hash'] == paired.manual_skills_hash()
    assert idt['runtime_version'] == 'paired-runtime-v1' and idt['hash_seed'] == '0'
    assert idt['engine_ref'] == 'test_paired_runtime:fake_game'
    assert set(idt['sources']['sha256']) == set(rt.SOURCES)
    blob = json.dumps(idt, ensure_ascii=False)
    assert not re.search(r'worker|pid|schedule|started|finished', blob)
    plan2 = paired.seed_plan('rt-exp-2', BLOCKS)
    variants = [rt.identity_for(U, CAND, BASE, OPPS, plan2, experiment_id='rt-exp-2', play_game=fake_game),
                rt.identity_for(U, BASE, BASE, OPPS, PLAN, experiment_id=EXP, play_game=fake_game),
                rt.identity_for(U, CAND, BASE, OPPS[:1], PLAN, experiment_id=EXP, play_game=fake_game),
                rt.identity_for(U, CAND, BASE, OPPS, PLAN, experiment_id=EXP, play_game=other_game)]
    assert all(v != idt for v in variants)


@pytest.mark.parametrize('plan,exp', [(paired.seed_plan('other', BLOCKS), EXP), ([dict(block_id='b0', seed=1)], EXP), (PLAN, '')])
def test_plan_must_derive_from_experiment_id(plan, exp):
    with pytest.raises(ValueError):
        rt.execute(U, CAND, BASE, OPPS, plan, experiment_id=exp, workers=1, play_game=fake_game)


@pytest.mark.parametrize('kw', [dict(schedule=[('opp-x', 'b0')]), dict(play_game=lambda a, b, r, log=None: None),
                                dict(opponents=OPPS + OPPS[:1])])
def test_bad_inputs_rejected_before_spawn(kw):
    args = dict(opponents=OPPS, play_game=fake_game); args.update(kw)
    opps = args.pop('opponents')
    with pytest.raises(ValueError):
        rt.execute(U, CAND, BASE, opps, PLAN, experiment_id=EXP, workers=1, **args)


def test_hash_seed_env_restored_to_previous_value(monkeypatch):
    monkeypatch.setenv('PYTHONHASHSEED', '123')
    pkg = run(workers=2, opps=OPPS[:1], plan=PLAN[:1])
    assert os.environ['PYTHONHASHSEED'] == '123'
    assert pkg['execution']['hash_seed'] == '0' and pkg['execution']['hash_probe_consistent'] is True


# ---- 封裝標記與私密內容 ----

def test_package_markers_and_no_private_content(base_pkg):
    p = base_pkg
    assert p['kind'] == 'internal-run-package' and p['is_archive'] is False and p['is_public_release'] is False
    assert p['sensitivity'] == 'internal-restricted' and p['do_not_publish'] is True
    assert p['identity_sha256'] == canon_sha(p['identity'])
    blob = json.dumps(p, ensure_ascii=False)
    for s in {os.path.expanduser('~'), paired.REPO_ROOT, os.getcwd(), 'evils', 'private'}:
        assert s not in blob
    assert not re.search(r'[A-Za-z]:\\\\', blob)


# ---- 結論 adapter 與契約驗證 ----

def test_fragment_adapter_is_conclusion_fragment_of_real_run(base_pkg):
    frag = rt.fragment(base_pkg, require_sim2=False)
    assert frag == paired.conclusion_fragment(base_pkg['run'])
    rt.validate_fragment(frag, base_pkg, require_sim2=False)
    with pytest.raises(rt.ContractError):
        rt.fragment(base_pkg)                  # 預設 require_sim2：stub 引擎不能產正式結論片段


def _swap(l):
    l[0], l[1] = l[1], l[0]


FRAG_TAMPER = {
    'extra_top_key': lambda f: f.__setitem__('delta', 0.1),
    'seeds_reordered': lambda f: f['seeds'].reverse(),
    'pairing_changed': lambda f: f['pairing'].__setitem__('scheme', 'x'),
    'pair_order': lambda f: _swap(f['pair_results']),
    'metric_mismatch': lambda f: f['pair_results'][0]['candidate'].__setitem__('metric_value', 1 - f['pair_results'][0]['candidate']['metric_value']),
    'metric_bool': lambda f: f['pair_results'][0]['candidate'].__setitem__('metric_value', bool(f['pair_results'][0]['candidate']['metric_value'])),
    'fingerprint': lambda f: f['pair_results'][0].__setitem__('opponent_fingerprint', '0' * 40),
    'pair_id': lambda f: f['pair_results'][0].__setitem__('pair_id', 'x'),
    'duplicate_pair': lambda f: f['pair_results'].__setitem__(1, copy.deepcopy(f['pair_results'][0])),
    'missing_pair': lambda f: f['pair_results'].pop(),
    'aggregate_wins': lambda f: f['pairs'][0].__setitem__('wins', f['pairs'][0]['wins'] + 1),
    'aggregate_delta': lambda f: f['pairs'][0].__setitem__('delta', 0.123),
}


@pytest.mark.parametrize('name', sorted(FRAG_TAMPER))
def test_validate_fragment_rejects_tampered_fragment(base_pkg, name):
    frag = copy.deepcopy(rt.fragment(base_pkg, require_sim2=False))
    FRAG_TAMPER[name](frag)
    with pytest.raises(rt.ContractError):
        rt.validate_fragment(frag, base_pkg, require_sim2=False)


PKG_TAMPER = {
    'kind': lambda p: p.__setitem__('kind', 'research-archive'),
    'archive_flag': lambda p: p.__setitem__('is_archive', True),
    'identity_hash': lambda p: p.__setitem__('identity_sha256', '0' * 64),
    'identity_fp_vs_run': lambda p: p['identity']['decks']['opponents'][0].__setitem__('fingerprint', '0' * 40),
    'games_count': lambda p: p['execution'].__setitem__('games_played', 11),
    'run_seed': lambda p: p['run']['pair_results'][0].__setitem__('seed', 5),
}


@pytest.mark.parametrize('name', sorted(PKG_TAMPER))
def test_fragment_rejects_tampered_package(base_pkg, name):
    p = copy.deepcopy(base_pkg)
    PKG_TAMPER[name](p)
    if name == 'identity_fp_vs_run':
        p['identity_sha256'] = canon_sha(p['identity'])
    with pytest.raises(rt.ContractError):
        rt.fragment(p, require_sim2=False)


# ---- 跨 repo：主 repo 唯讀 JS validator（validateResearchArchive），subprocess argv、shell=False、timeout ----

MAIN_MODEL_JS = os.path.join(os.path.dirname(paired.REPO_ROOT), '排球少年', 'js', 'deck-health-model.js')
NODE_SCRIPT = ("import { validateResearchArchive } from %s;\n"
               "let s = ''; process.stdin.setEncoding('utf8');\n"
               "for await (const c of process.stdin) s += c;\n"
               "const r = validateResearchArchive(JSON.parse(s));\n"
               "process.stdout.write(JSON.stringify({ ok: r.ok, codes: r.errors.map(e => e.code) }));\n")


def js_validate(archive):
    import pathlib, shutil, subprocess
    node = shutil.which('node')
    assert node, '找不到 node'
    assert os.path.isfile(MAIN_MODEL_JS), MAIN_MODEL_JS
    script = NODE_SCRIPT % json.dumps(pathlib.Path(MAIN_MODEL_JS).as_uri())
    p = subprocess.run([node, '--input-type=module', '-e', script], input=json.dumps(archive, ensure_ascii=False),
                       capture_output=True, text=True, encoding='utf-8', timeout=60, shell=False)
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    assert set(out) == {'ok', 'codes'}
    return out


def synthetic_archive(pkg):
    """測試用合成封存：改由 archive.assemble_synthetic_archive 組裝（不再手工拼）。candidate／baseline／所有對手的完整
    牌表都進 decks[]，baseline_deck 與 provenance（synthetic-runtime-snapshot-v1）由組裝器產生；result_files 為空。"""
    import archive as ar   # 延遲 import：本檔其他測試不依賴組裝器
    decks = [dict(deck_id='cand', display_name='合成候選', deck=CAND), dict(deck_id='base', display_name='合成基準', deck=BASE)] + \
        [dict(deck_id='deck-' + o['opponent_id'], display_name='合成對手', deck=o['deck']) for o in OPPS]
    roles = dict(candidate=dict(deck_id='cand'), baseline=dict(deck_id='base'),
                 opponents=[dict(opponent_id=o['opponent_id'], deck_id='deck-' + o['opponent_id']) for o in OPPS])
    return ar.assemble_synthetic_archive(pkg, U=U, decks=decks, roles=roles, require_sim2=False,
                                         meta=dict(release_id='synthetic-rt-1', research_version='synthetic-rt-test',
                                                   conclusion_id='c1', job_id='rt-job'))


def test_js_validator_accepts_synthetic_archive_from_runtime_fragment(base_pkg):
    a = synthetic_archive(base_pkg)
    assert a['conclusions'][0]['baseline_deck']['deck_id'] == 'base' and a['conclusions'][0]['result_files'] == []
    assert js_validate(a) == {'ok': True, 'codes': []}


# deck-fingerprint-v1 固定向量：Python 端值寫死，並由主 repo 實際 js/deck-fingerprint.js 重算比對（跨語言只宣稱牌表 SHA-1 一致）
CAND_FINGERPRINT = '8c4f12704577088255715ce76fbe1091aa2ad780'
FP_SCRIPT = ("const { deckFingerprint } = await import(process.argv[process.argv.length - 1]);\n"
             "let s = ''; process.stdin.setEncoding('utf8');\n"
             "for await (const c of process.stdin) s += c;\n"
             "const out = [];\n"
             "for (const v of JSON.parse(s)) out.push(await deckFingerprint(new Map(v)));\n"
             "process.stdout.write(JSON.stringify(out));\n")


def test_deck_fingerprint_fixed_vector_matches_main_repo_js():
    import pathlib, shutil, subprocess
    assert paired.deck_fingerprint(CAND) == CAND_FINGERPRINT
    decks = [CAND, BASE] + [o['deck'] for o in OPPS]
    node = shutil.which('node')
    assert node, '找不到 node'
    fp_js = pathlib.Path(os.path.dirname(MAIN_MODEL_JS), 'deck-fingerprint.js')
    assert fp_js.is_file(), fp_js
    p = subprocess.run([node, '--input-type=module', '-e', FP_SCRIPT, fp_js.as_uri()],
                       input=json.dumps([sorted(d.items()) for d in decks]), capture_output=True, text=True,
                       encoding='utf-8', timeout=60, shell=False, cwd=HERE)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout) == [paired.deck_fingerprint(d) for d in decks]


def test_js_validator_rejects_tampered_delta(base_pkg):
    a = synthetic_archive(base_pkg)
    agg = a['conclusions'][0]['pairs'][0]
    assert agg['delta'] is not None
    agg['delta'] += 0.25
    out = js_validate(a)
    assert out['ok'] is False and 'delta_mismatch' in out['codes']


def test_js_validator_rejects_tampered_count(base_pkg):
    a = synthetic_archive(base_pkg)
    agg = a['conclusions'][0]['pairs'][0]
    if agg['losses'] > 0:
        agg['wins'] += 1; agg['losses'] -= 1
    else:
        agg['wins'] -= 1; agg['losses'] += 1
    out = js_validate(a)
    assert out['ok'] is False and 'bad_total' in out['codes']


# ---- 合併（worker 結果信任邊界），純函式 ----

def _ok_outcome():
    r = paired.run_paired(U, CAND, BASE, OPPS[:1], PLAN[:1], play_game=fake_game)   # 測試行程內只跑 stub
    return dict(run=r, post_drift=[], meta=dict(pid=111, priority=IDLE, games=2))


def _merge(outcome, missing=False):
    fps = {'opp-x': paired.deck_fingerprint(OPPS[0]['deck'])}
    outcomes = {} if missing else {('opp-x', 'b0'): outcome}
    return rt._merge(PLAN[:1], ['opp-x'], fps, {111}, outcomes)


def test_merge_accepts_valid_worker_result():
    m = _merge(_ok_outcome())
    assert m['run']['status'] == 'complete' and m['run']['completed_pairs'] == 1
    assert m['task_workers'] == [['b0', 'opp-x', 111]] and m['games_played'] == 2


def _mut(fn):
    def f():
        o = _ok_outcome(); fn(o); return o
    return f


MERGE_BAD = {
    'half_pair': (_mut(lambda o: o['run']['pair_results'][0].pop('baseline')), 'malformed_worker_result'),
    'seed': (_mut(lambda o: o['run']['pair_results'][0].__setitem__('seed', 7)), 'malformed_worker_result'),
    'extra_pair': (_mut(lambda o: o['run']['pair_results'].append(copy.deepcopy(o['run']['pair_results'][0]))), 'malformed_worker_result'),
    'fingerprint': (_mut(lambda o: o['run']['pair_results'][0].__setitem__('opponent_fingerprint', 'x')), 'malformed_worker_result'),
    'pair_and_failure': (_mut(lambda o: o['run']['failures'].append(dict(opponent_id='opp-x', block_id='b0', seed=SEED_OF['b0'], side='baseline', reason='x'))), 'malformed_worker_result'),
    'metric_bool': (_mut(lambda o: o['run']['pair_results'][0]['baseline'].__setitem__('metric_value', bool(o['run']['pair_results'][0]['baseline']['metric_value']))), 'malformed_worker_result'),
    'plan': (_mut(lambda o: o['run']['plan'][0].__setitem__('seed', 7)), 'malformed_worker_result'),
    'unknown_pid': (_mut(lambda o: o['meta'].__setitem__('pid', 222)), 'malformed_worker_result'),
    'not_idle': (_mut(lambda o: o['meta'].__setitem__('priority', 0x20)), 'not_idle'),
    'drift': (_mut(lambda o: o.__setitem__('post_drift', ['cfg'])), 'state_drift:cfg'),
    'refused': (lambda: dict(refused='state_drift:manual', meta=dict(pid=111)), 'state_drift:manual'),
    'broken_pool': (lambda: BrokenProcessPool('x'), 'worker_lost'),
    'exception': (lambda: ValueError('x'), 'worker_exception:ValueError'),
    'not_dict': (lambda: [1], 'malformed_worker_result'),
}


@pytest.mark.parametrize('name', sorted(MERGE_BAD))
def test_merge_rejects_whole_pair_on_bad_worker_result(name):
    make, reason = MERGE_BAD[name]
    m = _merge(make())
    r = m['run']
    assert r['status'] == 'incomplete' and r['usable'] is False and r['pair_results'] == []
    assert [(f['side'], f['reason']) for f in r['failures']] == [('pair', reason)]


def test_merge_missing_result_is_worker_lost():
    r = _merge(None, missing=True)['run']
    assert r['pair_results'] == [] and r['failures'][0]['reason'] == 'worker_lost'


# ---- submit 途中失敗（fake executor＋真 concurrent.futures.Future；不 spawn、不進 sim2）----

class FakeExecutor:
    """probe 全部成功；第 fail_on 次 pair submit 丟 BrokenProcessPool（probe_fail 時 probe submit 就丟）。
    第 exc_on 中各次 pair submit 回傳已 set_exception(BrokenProcessPool) 的 Future（不跑任何半場）。
    其餘成功 submit 的 pair 在測試行程用 stub（fake_game）跑 paired.run_paired，包成已完成的 Future。"""
    def __init__(self, fail_on=None, probe_fail=False, exc_on=(), *, max_workers, mp_context, initializer, initargs):
        self.fz, self.fail_on, self.probe_fail, self.exc_on = initargs[0], fail_on, probe_fail, set(exc_on)
        self.max_workers, self.n_probe, self.n_pair, self.shutdowns = max_workers, 0, 0, []

    def submit(self, fn, *args):
        f = cf.Future()
        if fn is rt._probe:
            if self.probe_fail:
                raise BrokenProcessPool('probe submit 中斷')
            self.n_probe += 1
            f.set_result(dict(pid=90000 + self.n_probe, error=None, priority=IDLE, hash_randomization=0,
                              hash_probe=1, identity_sha256=self.fz['identity_sha256']))
            return f
        assert fn is rt._pair_task
        self.n_pair += 1
        if self.n_pair == self.fail_on:
            raise BrokenProcessPool('submit 中斷')
        if self.n_pair in self.exc_on:
            f.set_exception(BrokenProcessPool('worker 在執行中死亡'))
            return f
        oid, b, seed = args
        d = self.fz['decks']
        opp = next(o for o in d['opponents'] if o['opponent_id'] == oid)
        r = paired.run_paired(self.fz['U_sub'], d['candidate'], d['baseline'], [opp], [dict(block_id=b, seed=seed)],
                              play_game=self.fz['play_game'])
        f.set_result(dict(run=r, post_drift=[], meta=dict(pid=90001, priority=IDLE, games=2)))
        return f

    def shutdown(self, **kw):
        self.shutdowns.append(kw)


def fake_factory(made, **opts):
    def make(**kw):
        ex = FakeExecutor(**opts, **kw); made.append(ex); return ex
    return make


def _cover(r):
    pairs = {(p['opponent_id'], BLOCK_OF_SEED[p['seed']]) for p in r['pair_results']}
    fails = {(f['opponent_id'], f['block_id']) for f in r['failures']}
    assert not pairs & fails
    return pairs | fails


BLOCK_OF_SEED = {s: b for b, s in SEED_OF.items()}


@pytest.mark.parametrize('fail_on,n_ok', [(1, 0), (2, 1)])
def test_submit_failure_keeps_submitted_futures_and_returns_incomplete_package(monkeypatch, fail_on, n_ok):
    monkeypatch.delenv('PYTHONHASHSEED', raising=False)
    made = []
    pkg = run(workers=2, _executor_factory=fake_factory(made, fail_on=fail_on))
    r, ex = pkg['run'], pkg['execution']
    assert 'PYTHONHASHSEED' not in os.environ
    assert len(made) == 1 and made[0].shutdowns == [dict(wait=True, cancel_futures=True)]
    assert r['status'] == 'incomplete' and r['usable'] is False
    assert r['expected_pairs'] == 6 and r['completed_pairs'] == len(r['pair_results']) == n_ok
    assert _cover(r) == set(tasks_of())                       # 任務 coverage 完整
    for p in r['pair_results']:                               # 沒有半個 pair
        assert set(p['candidate']) == set(p['baseline']) == {'outcome', 'metric_value'}
    order = tasks_of()
    reasons = {(f['opponent_id'], f['block_id']): (f['side'], f['reason']) for f in r['failures']}
    assert reasons[order[fail_on - 1]] == ('pair', 'submit_failed:BrokenProcessPool')
    assert all(reasons[t] == ('pair', 'not_dispatched') for t in order[fail_on:])
    assert ex['submitted_tasks'] == n_ok and ex['submit_error'] == 'BrokenProcessPool' and ex['games_played'] == 2 * n_ok
    with pytest.raises(paired.IncompleteRun):
        rt.fragment(pkg, require_sim2=False)


def test_first_future_broken_then_second_submit_raises(monkeypatch):
    """主 Chat 精確重現：第 1 次 pair submit 回已 set_exception(BrokenProcessPool) 的 Future，第 2 次 submit 直接 raise。"""
    monkeypatch.delenv('PYTHONHASHSEED', raising=False)
    made = []
    pkg = run(workers=2, _executor_factory=fake_factory(made, fail_on=2, exc_on=(1,)))
    r, ex = pkg['run'], pkg['execution']
    assert 'PYTHONHASHSEED' not in os.environ
    assert len(made) == 1 and made[0].shutdowns == [dict(wait=True, cancel_futures=True)] and made[0].n_pair == 2
    assert r['status'] == 'incomplete' and r['usable'] is False
    assert r['expected_pairs'] == 6 and r['completed_pairs'] == 0 and r['pair_results'] == []
    assert _cover(r) == set(tasks_of())
    order = tasks_of()
    reasons = {(f['opponent_id'], f['block_id']): (f['side'], f['reason']) for f in r['failures']}
    assert len(r['failures']) == len(reasons) == 6
    assert reasons[order[0]] == ('pair', 'worker_lost')                          # 由 Future 的例外而來
    assert reasons[order[1]] == ('pair', 'submit_failed:BrokenProcessPool')
    assert all(reasons[t] == ('pair', 'not_dispatched') for t in order[2:])
    assert ex['submitted_tasks'] == 1 and ex['submit_error'] == 'BrokenProcessPool' and ex['games_played'] == 0
    assert ex['task_workers'][0][2] is None
    with pytest.raises(paired.IncompleteRun):
        rt.fragment(pkg, require_sim2=False)


def test_probe_submit_failure_is_setup_error_with_shutdown_and_env_restored(monkeypatch):
    monkeypatch.setenv('PYTHONHASHSEED', '123')
    made = []
    with pytest.raises(rt.RuntimeSetupError):
        run(workers=2, _executor_factory=fake_factory(made, probe_fail=True))
    assert os.environ['PYTHONHASHSEED'] == '123'
    assert made[0].shutdowns == [dict(wait=True, cancel_futures=True)] and made[0].n_pair == 0


# ---- IDLE 單元（假 kernel32，不改任何真實優先權）----

class FakeKernel:
    def __init__(self, set_ok=1, got=IDLE):
        self.set_ok, self.got, self.calls = set_ok, got, []

    def GetCurrentProcess(self):
        self.calls.append('cur'); return 'SELF'

    def SetPriorityClass(self, h, cls):
        self.calls.append(('set', h, cls)); return self.set_ok

    def GetPriorityClass(self, h):
        self.calls.append(('get', h)); return self.got


def test_ensure_idle_refuses_in_coordinator_parent():
    k = FakeKernel()
    with pytest.raises(RuntimeError):
        rt._ensure_idle(k, in_worker=False)
    assert k.calls == []
    with pytest.raises(RuntimeError):
        rt._ensure_idle()                      # 真實父程序：預設偵測為非 worker，直接拒絕


def test_ensure_idle_sets_only_current_process_and_verifies():
    k = FakeKernel()
    assert rt._ensure_idle(k, in_worker=True) == IDLE
    assert ('set', 'SELF', IDLE) in k.calls and all(c == 'cur' or c[1] == 'SELF' for c in k.calls)


@pytest.mark.parametrize('k,exc', [(FakeKernel(set_ok=0), OSError), (FakeKernel(got=0x20), RuntimeError)])
def test_ensure_idle_fails_closed(k, exc):
    with pytest.raises(exc):
        rt._ensure_idle(k, in_worker=True)


def test_ensure_idle_rejects_non_windows(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'linux')
    with pytest.raises(RuntimeError):
        rt._ensure_idle(in_worker=True)


def test_kernel32_loader_sets_pointer_restype():
    k = rt._kernel32()
    assert k.GetCurrentProcess.restype is ctypes.c_void_p
    assert isinstance(rt._current_priority(), int)


# ---- 唯一真 sim（預設 skip；預算 12 場）----

def test_real_sim_spawn_replay(request):
    if request.config.getoption('keyword') != 'test_real_sim_spawn_replay':
        pytest.skip('真 sim：只在 -k test_real_sim_spawn_replay 精確指定時執行（預算 12 場）')
    exp = 'rt-real-sim'
    plan, opps = paired.seed_plan(exp, ['r0', 'r1']), OPPS[:1]
    assert len(plan) * len(opps) * 2 == 4
    pkgs, total = [], 0
    for w in (1, 2, 2):                        # workers=1、workers=2、workers=2 replay
        p = rt.execute(U, CAND, BASE, opps, plan, experiment_id=exp, workers=w, play_game=sim2.play_game)
        total += p['execution']['games_played']
        assert p['execution']['games_played'] == 4 and total <= 12
        assert p['run']['status'] == 'complete', p['run']['failures']
        pkgs.append(p)
    assert total == 12
    a, b, c = pkgs
    assert a['identity'] == b['identity'] == c['identity'] and a['identity']['engine_ref'] == 'sim2:play_game'
    assert a['run'] == b['run'] == c['run']
    assert [p['execution']['workers_effective'] for p in pkgs] == [1, 2, 2]
    assert all(p['execution']['worker_priorities'] == [IDLE] for p in pkgs)
    for p in pkgs:
        frag = rt.fragment(p)                  # require_sim2=True
        assert frag['pair_results'] == p['run']['pair_results']
