"""A2 配對評估（paired.py）行為測試：只用 mock play_game 與合成牌表，不跑真對打、不讀私人牌組。"""
import hashlib, json, math, os, sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paired
import sim2
from manual_cards import MANUAL

SKILL_NO = 'HV-P04-037'  # 只借它的手動技能結構（巢狀 cost／effects）；牌面資料是合成的
assert MANUAL[SKILL_NO]

# deck-fingerprint-v1 跨語言固定向量（與網站端 js/deck-fingerprint.js 規格一致；值寫死，不在測試內計算）
KNOWN_DECK = {'HV-P01-002': 2, 'HV-P01-001': 3}
KNOWN_FP = '75deb4dd22372e7b32fac38eef145c9e305ea344'


def raw(no):
    return dict(card_no=no, name='合成 ' + no, category='CHARACTER', position='WS', school='合成高校',
                srv=1, blk=1, rcv=5, tos=1, atk=1, affiliation='', skill_jp='-')


U = {no: raw(no) for no in ['SYN-001', 'SYN-002', 'SYN-003', 'SYN-004', SKILL_NO]}
CAND = {'SYN-002': 20, SKILL_NO: 4, 'SYN-001': 16}   # 刻意不排序
BASE = {'SYN-001': 20, 'SYN-002': 20}
OPPS = [dict(opponent_id='opp-x', deck={'SYN-003': 40}), dict(opponent_id='opp-y', deck={'SYN-004': 36, SKILL_NO: 4})]
EXP = 'test-exp'
BLOCKS = ['b0', 'b1', 'b2']
PLAN = paired.seed_plan(EXP, BLOCKS)
SEEDS = [p['seed'] for p in PLAN]

# 黃金值：由實作首次輸出擷取後寫死（演算法本身由 KNOWN_FP 與下方 seed 規格測試釘住），防止日後無聲漂移
GOLDEN_SEED = {('test-exp', 'b0'): 1909130560182711}
GOLDEN_FP = {'CAND': '3a22d8ae44f41f0f32b19f18dda44bd6ba1d8b9b', 'BASE': '0a94feabc9be9ac8dc3d71ff2a8543058d030577',
             'opp-x': 'c633d45218ff9ea503bbcb1bef8ad219a423d06d', 'opp-y': 'd50b8503dd8daa9b6d1f1c45f14e5492349ecbd3'}


def fake_game(cardsA, cardsB, rng, log=None):
    """結果只取決於 rng 與 A 方牌表：同 seed 同牌 → 同結果。"""
    k = sum(1 for c in cardsA if c.no == SKILL_NO)
    return dict(winner='A' if (rng.random() + 0.1 * k) % 1 < 0.5 else 'B')


def run(**kw):
    kw.setdefault('play_game', fake_game)
    return paired.run_paired(U, CAND, BASE, OPPS, PLAN, **kw)


def assert_clean(r, calls=None, n=None):
    """回呼內的 assert 會被 run_paired 當成 half 失敗吃掉，所以外層一定要確認沒有失敗、回呼次數正確。"""
    assert r['status'] == 'complete' and r['usable'] is True and r['failures'] == []
    if calls is not None:
        assert len(calls) == n


# ---- 正常路徑與資料形狀（對照 research-archive.schema.json 的 pair_results／pairs 欄位）----

def test_complete_run_covers_every_seed_per_opponent_with_unique_pair_ids():
    r = run()
    assert_clean(r)
    assert r['expected_pairs'] == r['completed_pairs'] == len(OPPS) * len(SEEDS)
    pr = r['pair_results']
    assert len(pr) == len(OPPS) * len(SEEDS)
    assert len({p['pair_id'] for p in pr}) == len(pr)
    for o in OPPS:
        assert sorted(p['seed'] for p in pr if p['opponent_id'] == o['opponent_id']) == sorted(SEEDS)
    for p in pr:
        assert set(p) == {'pair_id', 'opponent_id', 'opponent_fingerprint', 'seed', 'candidate', 'baseline'}
        for s in (p['candidate'], p['baseline']):
            assert set(s) == {'outcome', 'metric_value'}
            assert (s['outcome'], s['metric_value']) in {('win', 1), ('loss', 0)}


def test_opponents_share_seed_within_same_pair_block():
    pr = run()['pair_results']
    for seed in SEEDS:
        block = [p for p in pr if p['seed'] == seed]
        assert {p['opponent_id'] for p in block} == {'opp-x', 'opp-y'}


def test_pair_ids_unique_even_with_delimiter_like_ids():
    opps = [dict(opponent_id='a:b', deck={'SYN-003': 40}), dict(opponent_id='b', deck={'SYN-004': 40})]
    plan = paired.seed_plan(EXP, ['x', 'x:a'])
    r = paired.run_paired(U, CAND, BASE, opps, plan, play_game=fake_game)
    assert_clean(r)
    assert len({p['pair_id'] for p in r['pair_results']}) == 4


def test_two_sides_get_40_synthetic_cards_and_same_initial_server_choice():
    calls = []
    def g(cardsA, cardsB, rng, log=None):
        calls.append(dict(nA=len(cardsA), nB=len(cardsB), syn=all(c.no in U for c in cardsA + cardsB),
                          base=all(c.no != SKILL_NO for c in cardsA), first=rng.choice('AB')))
        return dict(winner='A')
    r = paired.run_paired(U, CAND, BASE, OPPS, PLAN, play_game=g)
    assert_clean(r, calls, 2 * len(OPPS) * len(PLAN))
    assert all(c['nA'] == 40 and c['nB'] == 40 and c['syn'] for c in calls)
    import random
    for i in range(0, len(calls), 2):   # 預設排程：每個任務先 candidate 再 baseline
        cand, base = calls[i], calls[i + 1]
        assert not cand['base'] and base['base']
        assert cand['first'] == base['first']
    firsts = [c['first'] for c in calls[::2]]
    assert firsts == [random.Random(s).choice('AB') for s in SEEDS for _ in OPPS]


def test_summary_is_per_opponent_only():
    c = paired.conclusion_fragment(run())
    assert set(c) == {'design', 'seeds', 'pairing', 'pair_results', 'pairs'}   # 沒有跨對手合併的 delta／se
    assert [a['opponent_id'] for a in c['pairs']] == ['opp-x', 'opp-y']
    assert all(a['n'] == len(SEEDS) for a in c['pairs'])


def test_conclusion_fragment_matches_archive_schema_shape_and_recomputes():
    r = run()
    c = paired.conclusion_fragment(r)
    assert c['design'] == 'paired' and c['seeds'] == SEEDS
    assert c['pairing']['metric']['value_map'] == {'win': 1, 'loss': 0, 'draw': 0}
    assert c['pairing']['delta_definition'] == 'mean-of-pair-differences'
    assert c['pairing']['se_delta_definition'] == 'sample-sd-of-pair-differences/sqrt(N)'
    assert c['pair_results'] == r['pair_results']
    req = {'opponent_id', 'opponent_fingerprint', 'wins', 'losses', 'draws', 'n', 'win_rate', 'se', 'delta', 'se_delta', 'baseline'}
    for agg in c['pairs']:
        assert set(agg) == req
        own = [p for p in r['pair_results'] if p['opponent_id'] == agg['opponent_id']]
        n = len(own)
        assert agg['n'] == n == agg['wins'] + agg['losses'] and agg['draws'] == 0
        assert agg['wins'] == sum(p['candidate']['outcome'] == 'win' for p in own)
        assert agg['baseline'] == dict(wins=sum(p['baseline']['outcome'] == 'win' for p in own),
                                       losses=sum(p['baseline']['outcome'] == 'loss' for p in own), draws=0)
        assert agg['win_rate'] == agg['wins'] / n
        assert math.isclose(agg['se'], math.sqrt(agg['win_rate'] * (1 - agg['win_rate']) / n))
        d = [p['candidate']['metric_value'] - p['baseline']['metric_value'] for p in own]
        m = sum(d) / n
        assert math.isclose(agg['delta'], m, abs_tol=1e-12)
        assert math.isclose(agg['se_delta'], math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1)) / math.sqrt(n), abs_tol=1e-12)
        assert agg['opponent_fingerprint'] == GOLDEN_FP[agg['opponent_id']]
    for p in r['pair_results']:
        assert p['opponent_fingerprint'] == GOLDEN_FP[p['opponent_id']]


def test_single_seed_gives_null_delta():
    r = paired.run_paired(U, CAND, BASE, OPPS, PLAN[:1], play_game=fake_game)
    for agg in paired.conclusion_fragment(r)['pairs']:
        assert agg['delta'] is None and agg['se_delta'] is None


def test_deck_fingerprint_known_cross_language_vector():
    assert paired.deck_fingerprint(KNOWN_DECK) == KNOWN_FP
    assert paired.deck_fingerprint(dict(reversed(list(KNOWN_DECK.items())))) == KNOWN_FP


@pytest.mark.parametrize('name,deck', [('CAND', CAND), ('BASE', BASE), ('opp-x', OPPS[0]['deck']), ('opp-y', OPPS[1]['deck'])])
def test_fixture_fingerprints_golden(name, deck):
    assert paired.deck_fingerprint(deck) == GOLDEN_FP[name]


# ---- 種子派生（paired-seed-v1）----

def test_seed_derivation_known_vector():
    for (exp, blk), seed in GOLDEN_SEED.items():
        assert paired.derive_seed(exp, blk) == seed


def test_seed_derivation_matches_written_spec():
    """規格：SHA-256(namespace + '\\n' + canonical JSON {block_id, experiment_id})，取前 8 bytes 大端整數右移 11 位（53 bits）。"""
    payload = '{"block_id":"b0","experiment_id":"test-exp"}'
    d = hashlib.sha256(('haikyuu-deck-health/paired-seed/v1\n' + payload).encode('utf-8')).digest()
    assert paired.SEED_DERIVATION_VERSION == 'paired-seed-v1'
    assert paired.derive_seed('test-exp', 'b0') == int.from_bytes(d[:8], 'big') >> 11


def test_seed_depends_on_experiment_and_block_not_opponent_or_order():
    assert paired.derive_seed('e1', 'b0') != paired.derive_seed('e2', 'b0')
    assert paired.derive_seed('e1', 'b0') != paired.derive_seed('e1', 'b1')
    assert paired.seed_plan('e1', ['b1', 'b0'])[1] == paired.seed_plan('e1', ['b0'])[0]
    assert all(0 <= p['seed'] <= 2 ** 53 - 1 for p in paired.seed_plan('e1', [f'b{i}' for i in range(200)]))


@pytest.mark.parametrize('exp,blocks', [('', ['b0']), (None, ['b0']), ('e', []), ('e', ['b0', 'b0']), ('e', ['']), ('e', [0]), ('e', None)])
def test_seed_plan_rejects_bad_identity(exp, blocks):
    with pytest.raises(ValueError):
        paired.seed_plan(exp, blocks)


# ---- 半對失敗、平手、未知勝方 ----

def failing_on(side_no, seed_bad):
    def g(cardsA, cardsB, rng, log=None):
        if any(c.no == side_no for c in cardsA) and rng.getstate() == __import__('random').Random(seed_bad).getstate():
            raise RuntimeError('boom')
        return fake_game(cardsA, cardsB, rng)
    return g


def test_half_pair_failure_excluded_and_run_marked_unusable():
    bad = SEEDS[1]
    r = run(play_game=failing_on(SKILL_NO, bad))   # 只有 candidate（含 SKILL_NO）在 block b1 失敗
    assert r['status'] == 'incomplete' and r['usable'] is False
    assert r['expected_pairs'] == len(OPPS) * len(SEEDS)
    assert r['completed_pairs'] == len(r['pair_results']) == len(OPPS) * (len(SEEDS) - 1)
    assert all(p['seed'] != bad for p in r['pair_results'])
    assert [(f['opponent_id'], f['seed'], f['side'], f['reason']) for f in r['failures']] == \
        [('opp-x', bad, 'candidate', 'exception:RuntimeError'), ('opp-y', bad, 'candidate', 'exception:RuntimeError')]
    with pytest.raises(paired.IncompleteRun):
        paired.conclusion_fragment(r)


def test_conclusion_rejects_tampered_usable_flag():
    r = run(play_game=failing_on(SKILL_NO, SEEDS[0]))
    r['usable'] = True; r['status'] = 'complete'   # 旗標被改也不能過：還有 failures、數量不足
    with pytest.raises(paired.IncompleteRun):
        paired.conclusion_fragment(r)


@pytest.mark.parametrize('winner', [None, 'draw', 'C', ''])
def test_draw_or_unknown_winner_rejected(winner):
    def g(cardsA, cardsB, rng, log=None):
        if any(c.no == 'SYN-002' and len([x for x in cardsA if x.no == 'SYN-001']) == 20 for c in cardsA):  # baseline
            return dict(winner=winner)
        return fake_game(cardsA, cardsB, rng)
    r = run(play_game=g)
    assert r['pair_results'] == [] and r['status'] == 'incomplete' and r['usable'] is False and r['completed_pairs'] == 0
    assert all(f['side'] == 'baseline' and f['reason'] == 'draw_or_unknown_winner' for f in r['failures'])
    assert len(r['failures']) == len(OPPS) * len(SEEDS)


def test_missing_result_dict_rejected():
    r = run(play_game=lambda a, b, rng, log=None: None)
    assert r['pair_results'] == [] and len(r['failures']) == 2 * len(OPPS) * len(SEEDS)


# ---- seed plan 驗證 ----

def P(*pairs):
    return [dict(block_id=b, seed=s) for b, s in pairs]


def test_plan_accepts_seed_at_safe_boundary():
    r = paired.run_paired(U, CAND, BASE, OPPS[:1], P(('lo', 0), ('hi', 2 ** 53 - 1)), play_game=fake_game)
    assert_clean(r)


@pytest.mark.parametrize('bad', [[], P(('a', 1), ('b', 1)), P(('a', 1), ('a', 2)), P(('a', True)), P(('a', 1.0)), P(('a', '3')),
                                 P(('a', -1)), P(('a', 2 ** 53)), P(('', 1)), P((0, 1)), [dict(seed=1)], [5], None])
def test_unsafe_or_duplicate_plan_rejected(bad):
    with pytest.raises(ValueError):
        paired.run_paired(U, CAND, BASE, OPPS, bad, play_game=fake_game)


def test_each_half_gets_fresh_rng_from_seed():
    seen = []
    def g(cardsA, cardsB, rng, log=None):
        seen.append(rng.random()); return dict(winner='A')
    r = paired.run_paired(U, CAND, BASE, OPPS[:1], P(('k', 42)), play_game=g)
    assert_clean(r, seen, 2)
    import random
    assert seen == [random.Random(42).random()] * 2


# ---- 排程不影響結果 ----

def test_schedule_order_does_not_change_results():
    a = run()
    tasks = [(o['opponent_id'], b) for b in BLOCKS for o in OPPS]
    b = run(schedule=list(reversed(tasks)))
    assert_clean(a); assert_clean(b)
    assert a['pair_results'] == b['pair_results']


@pytest.mark.parametrize('sched', [[('opp-x', 'b0')], [('opp-x', 'b0')] * 6, [('opp-z', 'b0')] + [(o['opponent_id'], b) for b in BLOCKS for o in OPPS][1:]])
def test_schedule_must_be_permutation(sched):
    with pytest.raises(ValueError):
        run(schedule=sched)


# ---- 技能物件隔離 ----

def walk(o, out):
    """收集巢狀 dict／list 物件本身（保留參照，避免 id() 被 GC 重用造成假陰性）。"""
    if isinstance(o, (dict, list)):
        out.append(o)
        for v in (o.values() if isinstance(o, dict) else o):
            walk(v, out)
    return out


def test_nested_skills_not_shared_between_sides_pairs_or_with_manual():
    groups, calls = [], []
    manual_before = json.dumps(MANUAL[SKILL_NO], sort_keys=True, default=repr)
    def g(cardsA, cardsB, rng, log=None):
        calls.append(1)
        objs = []
        for c in cardsA + cardsB:
            for s in c.skills:
                walk(s, objs)
        for o in objs:   # 先檢查前面的 half／pair 沒有污染，再改動每一層巢狀物件
            assert not (isinstance(o, dict) and '_touched' in o) and not (isinstance(o, list) and o and o[-1] == '_touched')
        for o in objs:
            if isinstance(o, dict): o['_touched'] = True
            else: o.append('_touched')
        groups.append(objs)       # 保留參照
        return fake_game(cardsA, cardsB, rng)
    r = paired.run_paired(U, CAND, BASE, OPPS, PLAN, play_game=g)
    assert_clean(r, calls, 2 * len(OPPS) * len(PLAN))
    assert sum(1 for objs in groups if objs) == len(PLAN) * (len(OPPS) + 1)   # 含 SKILL_NO 的 half：所有 candidate＋opp-y 的 baseline
    manual_ids = {id(o) for o in walk(MANUAL[SKILL_NO], [])}
    seen = {}
    for gi, objs in enumerate(groups):
        for o in {id(x): x for x in objs}.values():
            assert id(o) not in manual_ids
            assert seen.setdefault(id(o), gi) == gi   # 同一個物件只能出現在一個 half
    assert json.dumps(MANUAL[SKILL_NO], sort_keys=True, default=repr) == manual_before


def test_whens_and_handsk_point_into_own_skills_copy():
    calls = []
    def g(cardsA, cardsB, rng, log=None):
        calls.append(1)
        for c in cardsA:
            assert all(any(s is x for x in c.skills) for s in c.whens + c.handsk)
        return dict(winner='A')
    r = paired.run_paired(U, CAND, BASE, OPPS[:1], PLAN[:1], play_game=g)
    assert_clean(r, calls, 2)


DUAL = 'HV-P03-077'   # 雙名卡（NAME_CHOICE 有 alts）；牌面仍是合成資料


def test_alts_isolated_from_name_choice_other_side_opponent_and_next_pair():
    from manual_cards import NAME_CHOICE
    orig = list(NAME_CHOICE[DUAL]); assert len(orig) == 2
    U2 = dict(U, **{DUAL: raw(DUAL)})
    deck = {DUAL: 4, 'SYN-001': 36}
    opps = [dict(opponent_id='o1', deck={DUAL: 4, 'SYN-003': 36}), dict(opponent_id='o2', deck={DUAL: 4, 'SYN-004': 36})]
    plan = paired.seed_plan(EXP, ['b0', 'b1'])
    calls, held = [], []
    def g(cardsA, cardsB, rng, log=None):
        calls.append(1)
        A = [c for c in cardsA if c.no == DUAL]; B = [c for c in cardsB if c.no == DUAL]
        assert len(A) == len(B) == 4
        for c in A + B:                     # 前一個 half／pair 的污染不能出現
            assert c.alts == orig and c.alts is not NAME_CHOICE[DUAL]
        for c in A: c.alts.append('污染'); c.alts[0] = '改名'   # 只改 A 側
        for c in B: assert c.alts == orig  # 對手同時不受影響
        held.append([c.alts for c in A + B])   # 保留參照，避免 id 重用
        return dict(winner='A')
    r = paired.run_paired(U2, deck, deck, opps, plan, play_game=g)   # candidate 與 baseline 同牌表：兩側也必須各自一份
    assert_clean(r, calls, 2 * len(opps) * len(plan))
    assert NAME_CHOICE[DUAL] == orig
    lists = [l for h in held for l in h]
    assert len({id(l) for l in lists}) >= 2 * len(calls)   # 至少每個 half 每側各自一份


def test_card_order_is_canonical_regardless_of_dict_order():
    orders = []
    def g(cardsA, cardsB, rng, log=None):
        orders.append([c.no for c in cardsA]); return dict(winner='A')
    r1 = paired.run_paired(U, CAND, CAND, OPPS[:1], PLAN[:1], play_game=g)
    flipped = dict(reversed(list(CAND.items())))
    r2 = paired.run_paired(U, flipped, flipped, OPPS[:1], PLAN[:1], play_game=g)
    assert_clean(r1); assert_clean(r2); assert len(orders) == 4
    assert orders[0] == orders[2] == sorted(orders[0])


def test_rejects_bad_opponents_and_decks():
    with pytest.raises(ValueError):
        paired.run_paired(U, CAND, BASE, OPPS + [OPPS[0]], PLAN, play_game=fake_game)
    with pytest.raises(ValueError):
        paired.run_paired(U, {'SYN-001': 39}, BASE, OPPS, PLAN, play_game=fake_game)
    with pytest.raises(ValueError):
        paired.run_paired(U, CAND, BASE, [], PLAN, play_game=fake_game)


# ---- manifest ----

EXPECTED_SOURCES = {'deck_health/sim2.py', 'deck_health/paired.py', 'deck_health/manual_cards.py'} | \
    {f'deck_health/manual_batch{i}.py' for i in range(1, 9)}
PRIVATE = ['private.db', 'deck_health/decks/private_deck.json', 'deck_health/results/run.json']   # 哨兵：絕不能被讀或輸出


class FakeGit:
    """故意「不守規矩」：status 不管 pathspec，照樣吐出私人檔與 untracked 項目，用來證明實作會過濾、也不讀。"""
    def __init__(self, status=b' M deck_health/sim2.py\0?? deck_health/paired.py\0?? private.db\0?? deck_health/decks/private_deck.json\0 M deck_health/results/run.json\0'):
        self.status, self.calls = status, []

    def __call__(self, args):
        self.calls.append(tuple(args))
        if args[:2] == ['rev-parse', 'HEAD']: return b'0f5c6873aed1c67706c71c5ad3e1e225ad93e5bf\n'
        if args[:1] == ['status']: return self.status
        raise AssertionError(args)


class FakeReader:
    def __init__(self, override=None):
        self.files = {p: b'' for p in EXPECTED_SOURCES}
        self.files['deck_health/manual_cards.py'] = b'abc'
        self.files.update(override or {})
        self.files.update({p: b'PRIVATE-SENTINEL' for p in PRIVATE})
        self.calls = []

    def __call__(self, path):
        self.calls.append(path)
        return self.files[path]


SHA256_EMPTY = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'   # 公認測試向量
SHA256_ABC = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'


def mf(g=None, r=None):
    return paired.manifest(CAND, BASE, git=g or FakeGit(), read_bytes=r or FakeReader())


def test_manifest_records_seats_order_cfg_skills_and_not_delivered():
    m = mf(FakeGit())
    assert m['seats'] == {'candidate': 'A', 'baseline': 'A', 'opponent': 'B'}
    assert m['card_order_policy'] == paired.CARD_ORDER_POLICY
    assert m['cfg'] == sim2.CFG and m['cfg'] is not sim2.CFG
    assert len(m['manual_skills_hash']) == 64
    assert m['decks'] == {'fingerprint_version': 'deck-fingerprint-v1', 'candidate': GOLDEN_FP['CAND'], 'baseline': GOLDEN_FP['BASE']}
    src = m['sources']
    assert src['scope'] == 'execution-source-files'
    assert set(src['sha256']) == EXPECTED_SOURCES
    assert src['sha256']['deck_health/manual_cards.py'] == SHA256_ABC
    assert all(h == SHA256_EMPTY for p, h in src['sha256'].items() if p != 'deck_health/manual_cards.py')
    assert len(src['combined_sha256']) == 64
    assert set(src['manual_env']) == {'DH_PENDING', 'DH_MIXED'} | {f'DH_BATCH{i}' for i in range(1, 9)}
    v = m['versions']
    assert v['seed_derivation'] == 'paired-seed-v1' and v['rng'].startswith('python-random.Random')
    assert v['python'] and v['engine'] and v['strategy']
    assert m['git']['head'] == '0f5c6873aed1c67706c71c5ad3e1e225ad93e5bf'
    assert set(m['not_delivered']) >= {'low_priority', 'multiprocessing'}
    assert 'dirty_hash' not in m['git'] and 'untracked_files' not in m['git']   # 不再宣稱涵蓋整個 dirty tree


def test_private_and_unlisted_untracked_never_read_or_output():
    g, r = FakeGit(), FakeReader()
    m = mf(g, r)
    assert sorted(r.calls) == sorted(EXPECTED_SOURCES)          # 每個 allowlist 檔剛好讀一次，其他一律不讀
    assert not any(p in r.calls for p in PRIVATE)
    blob = json.dumps(m, ensure_ascii=False, default=str)
    assert 'private' not in blob and 'PRIVATE-SENTINEL' not in blob and 'results/run.json' not in blob
    assert m['git']['source_status'] == {p: ('M' if p == 'deck_health/sim2.py' else '??' if p == 'deck_health/paired.py' else 'clean')
                                         for p in EXPECTED_SOURCES}


def test_manifest_git_calls_are_read_only_and_path_limited():
    g = FakeGit(); mf(g)
    assert {c[0] for c in g.calls} == {'rev-parse', 'status'}
    st = [c for c in g.calls if c[0] == 'status']
    assert len(st) == 1 and '--' in st[0]
    assert set(st[0][st[0].index('--') + 1:]) == EXPECTED_SOURCES and len(st[0][st[0].index('--') + 1:]) == len(EXPECTED_SOURCES)


def test_combined_source_hash_tracks_content_and_is_stable():
    base = mf()['sources']['combined_sha256']
    assert mf()['sources']['combined_sha256'] == base
    assert mf(r=FakeReader({'deck_health/manual_batch5.py': b'x'}))['sources']['combined_sha256'] != base
    assert mf(r=FakeReader({'deck_health/sim2.py': b'x'}))['sources']['combined_sha256'] != base


def test_manifest_default_reads_real_engine_sources_only():
    m = paired.manifest(CAND, BASE, git=FakeGit())
    assert set(m['sources']['sha256']) == EXPECTED_SOURCES
    assert all(len(h) == 64 and h != SHA256_EMPTY for h in m['sources']['sha256'].values())


@pytest.mark.parametrize('path', PRIVATE + ['deck_health/a1_name_entry_delivery.md', '../x/sim2.py', 'deck_health/sim2.py '])
def test_default_reader_refuses_paths_outside_allowlist(path):
    with pytest.raises(ValueError):   # 在 open 之前就拒絕，不會碰到檔案
        paired._read_source(path)


def test_dirty_flag_reflects_only_source_status():
    assert mf(FakeGit(status=b''))['git']['sources_dirty'] is False
    assert mf(FakeGit(status=b'?? private.db\0'))['git']['sources_dirty'] is False   # 不在 allowlist 的項目不算、也不記
    assert mf()['git']['sources_dirty'] is True
