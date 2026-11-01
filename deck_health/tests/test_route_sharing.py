"""接球路線加速：亂數延後複製、同 r 共用接球階段、同號牌路線沿用結果，都不能改變選擇。"""
import json
import random
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import sim2 as sim

U = sim.load_cards(str(HERE.parent / 'cards_data.js'))


def deck(name):
    return sim.build(U, json.loads((HERE / (name + '.json')).read_text(encoding='utf-8')))


def card(no, **stats):
    base = dict(srv=1, blk=1, rcv=1, tos=1, atk=1)
    base.update(stats)
    return sim.Card(dict(card_no=no, name=no, category='CHARACTER', position='WS', school='S', skill_jp='-', **base))


def test_cow_rng_snapshot_is_not_moved_by_source():
    source = random.Random(3); expected = random.Random(3)
    rng = sim.CowRng(source)
    fork = sim.CowRng(None, rng.getstate())
    first = rng.random()
    assert first == expected.random()
    assert source.getstate() == expected.getstate()  # 寫入落在外部 Random，連續多場共用亂數流
    assert fork.random() == first  # 來源前進後，快照仍從複製當下開始


def test_cow_rng_commit_keeps_stream():
    rng = sim.CowRng(random.Random(5))
    unused = sim.CowRng(None, rng.getstate())
    rng.setstate(unused.getstate())
    assert rng.snap is unused.snap  # 沒抽過亂數的試算提交時不用寫回
    used = sim.CowRng(None, rng.getstate())
    used.random()
    rng.setstate(used.getstate())
    assert rng.random() == used.random()


def test_clone_rng_streams_are_independent():
    p = sim.Player(deck('deck'), sim.CowRng(random.Random(9)), 'A')
    a, b = p.clone(), p.clone()
    value = a.rng.random()
    assert b.rng.random() == value
    assert p.rng.random() == value


def test_clone_context_isolates_by_skill():
    p = sim.Player(deck('deck'), random.Random(1), 'A')
    q, T = sim.trial(p, p.clone(), 3, 'attack')
    T['by_skill'] = dict(receive=False)
    copy = sim.cloneT(T, q.clone(), q)
    copy['by_skill']['toss'] = True
    assert T['by_skill'] == dict(receive=False)


def brute_force(Pd, opp, op_in, src):
    """未加速的走法：每條路線各自試算到底。"""
    dchars = [c for c in Pd.hand if not c.ev]
    if len(dchars) < 2: return {}
    rcands = [c for c in dchars if sim.can_enter(Pd, 'receive', c)]
    rcands.sort(key=lambda c: (sim.keep_value(c), -c.b['rcv']))
    two_ok = any(any(e['type'] == 'optional' for e in s['effects']) for c in dchars for s in c.skills
                 if s['timing'] == 'on_enter' and 'toss' in s.get('zones', []))
    out = {}
    for r in rcands[:5]:
        for t in dchars:
            if t is r or not sim.can_differ(t, r) or not sim.toss_allowed(Pd, t): continue
            modes = [('two', None)] if two_ok else []
            modes += [(m, a) for a in dchars if a is not r and a is not t and sim.can_differ(a, t) for m in (True, False)]
            if sim.has_holder_to_hand(r) and sim.can_differ(r, t): modes += [(m, r) for m in (True, False)]
            for aggressive, a in modes:
                P2, T = sim.trial(Pd, opp, op_in, src)
                op = sim.do_receive_line(P2, T, r, t, a, aggressive)
                if op is not None:
                    out[(r, t, a, aggressive)] = (sim.evaluate(P2, op, T['locks'], T['trap'], T['opp']), op)
    return out


@pytest.mark.parametrize('name,other', [('deck', 'champ'), ('ina_v4b', 'tsuki'), ('fuku_op8_v2', 'mixed_user'), ('aoba_0419', 'shira_final')])
def test_shared_routes_match_brute_force(name, other):
    for seed in range(25):
        rng = random.Random(seed)
        p = sim.Player(deck(name), rng, 'A'); opp = sim.Player(deck(other), rng, 'B')
        p.draw(7); opp.draw(6)
        for _ in range(seed % 4): p.zones['receive'].append(p.deck.pop(0))
        for _ in range(seed % 3): p.drop.append(p.deck.pop(0))
        for op_in in (0, 3, 5):
            sample = next(sim.planning_states(p))
            want = brute_force(sample, opp, op_in, 'attack')
            got = {plan: (res[0], res[2]) for plan, res in sim.receive_options(sample, opp, op_in, 'attack') if plan[3] != 'fetch'}
            assert got == want


def test_same_number_route_survives_when_cost_discards_first_copy():
    """走不通的同號路線不算試過：代價可能剛好棄掉第一張，第二張還在手上。"""
    r, t = card('R', rcv=9), card('T', tos=2)
    a1, a2 = card('A', atk=3), card('A', atk=3)
    p = sim.Player([r, t, a1, a2], random.Random(1), 'A'); p.hand = [r, t, a1, a2]; p.deck = []
    opp = sim.Player([card('O')], random.Random(2), 'B')
    original = sim.receive_part

    def drop_first_copy(P, T, entered, name):
        result = original(P, T, entered, name)
        if entered is r: P.hand.remove(a1); P.drop.append(a1)
        return result

    sim.receive_part = drop_first_copy
    try:
        plans = [plan for plan, _ in sim.receive_options(p, opp, 3, 'attack')]
    finally:
        sim.receive_part = original
    assert (r, t, a2, True) in plans
    assert (r, t, a1, True) not in plans


def test_duplicate_route_reports_under_both_plans():
    """另一個樣本可能只有副本走得通，分數要記在兩條路線名下。"""
    r, t = card('R', rcv=9), card('T', tos=2)
    a1, a2 = card('A', atk=3), card('A', atk=3)
    p = sim.Player([r, t, a1, a2], random.Random(1), 'A'); p.hand = [r, t, a1, a2]; p.deck = []
    opp = sim.Player([card('O')], random.Random(2), 'B')
    rows = dict(sim.receive_options(p, opp, 3, 'attack'))
    assert rows[(r, t, a2, True)] is rows[(r, t, a1, True)]
