"""梟谷四彈定案打法（使用者 2026-10-29）：年級判斷、木兎 P04-063 挑 Guts、木葉 P04-064 互換、小見 P04-066 與鷲尾 P04-067 發動條件。"""
import random
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import sim2 as sim

U = sim.load_cards(str(HERE.parent / 'cards_data.js'))
THIRD = dict(school='梟谷', grade=3)


def C(no): return sim.Card(U[no])


def test_grade_accepts_every_dot_style_and_both_names():
    assert sim.filt_ok(C('HV-PR-026'), THIRD)  # 梟谷･3年
    assert sim.filt_ok(C('HV-PR-062'), THIRD)  # 音駒・1年,梟谷・3年
    assert sim.filt_ok(C('HV-PR-013'), dict(grade=2)) and sim.filt_ok(C('HV-PR-013'), dict(grade=3))  # 梟谷·3年/梟谷2·年
    assert not sim.filt_ok(C('HV-P01-045'), THIRD)  # 赤葦是 2 年級


def player(hand=(), drop=(), **zones):
    P = sim.Player([C('HV-P01-050') for _ in range(10)], random.Random(1), 'A')
    P.hand = [C(x) for x in hand]; P.drop = [C(x) for x in drop]
    for zone, cards in zones.items(): P.zones[zone] = [C(x) for x in cards]
    return P


def context(op_in=0, phase='attack'):
    T = sim.newT(sim.Player([C('HV-P01-050') for _ in range(10)], random.Random(2), 'B'), op_in, 'attack')
    T['phase'] = phase
    return T


def nos(cards): return [c.no.replace('HV-', '') for c in cards]


def test_bokuto_063_picks_three_different_names_and_gets_seven():
    P, T = player(attack=['HV-P01-044', 'HV-P01-050', 'HV-P01-051', 'HV-P04-064']), context()  # 照疊的順序付會付到木兎
    sim.enter(P, T, 'attack', C('HV-P04-063'), True)
    assert sim.cur_stat(P, T, 'attack') == 7
    assert nos(P.zones['attack']) == ['P01-044', 'P04-063']


def test_bokuto_063_keeps_guts_when_three_names_are_impossible():
    P, T = player(attack=['HV-P01-050', 'HV-P04-066', 'HV-P01-051', 'HV-P01-051']), context()  # 只有小見、鷲尾兩種卡名
    sim.enter(P, T, 'attack', C('HV-P04-063'), True)
    assert sim.cur_stat(P, T, 'attack') == 0
    assert len(P.zones['attack']) == 5


def konoha_enters(P, T):
    P.zones['toss'] = P.zones['toss'] or [C('HV-P01-046'), C('HV-P01-046')]
    sim.enter(P, T, 'toss', C('HV-P04-064'), True)


def test_konoha_swaps_bokuto_043_back_to_hand():
    P, T = player(hand=['HV-P04-065'], attack=['HV-P01-043', 'HV-P01-051', 'HV-P01-050']), context(phase='toss')
    konoha_enters(P, T)
    assert sim.cur_stat(P, T, 'toss') == 2
    assert nos(P.hand) == ['P01-043']
    assert nos(P.zones['attack']) == ['P04-065', 'P01-051', 'P01-050']
    assert len(P.zones['toss']) == 1  # 2 Guts 付掉，只剩木葉


def test_konoha_swaps_to_complete_three_names():
    P, T = player(hand=['HV-P01-051'], attack=['HV-P01-046', 'HV-P01-045', 'HV-P01-050']), context(phase='toss')  # 赤葦兩張＋小見
    konoha_enters(P, T)
    assert sim.fuku_ready(P.zones['attack'])
    assert sorted(nos(P.hand)) in (['P01-045'], ['P01-046'])


def test_konoha_stays_home_without_a_reason():
    P, T = player(hand=['HV-P01-050'], attack=['HV-P01-051', 'HV-P04-064', 'HV-P01-050']), context(phase='toss')  # 已湊齊 3 種、沒有木兎 043
    konoha_enters(P, T)
    assert sim.cur_stat(P, T, 'toss') == 1
    assert len(P.zones['toss']) == 3


@pytest.mark.parametrize('fodder, fired', [('HV-P01-051', True), ('HV-P01-046', False)])  # 赤葦 2 年級不能棄給猿杙
def test_konoha_fires_for_saru_065_with_fodder_only(fodder, fired):
    P, T = player(hand=['HV-P04-065', fodder]), context(phase='toss')
    T['plan_attack'] = (P.hand[0], P.hand[0].name)
    konoha_enters(P, T)
    assert sim.cur_stat(P, T, 'toss') == (2 if fired else 1)


def test_konoha_needs_a_real_saru_plan_before_paying():
    P, T = player(hand=['HV-P04-065', 'HV-P01-051']), context(phase='toss')  # 攻擊手等舉球後才選：手上有猿杙不代表這拍用牠
    konoha_enters(P, T)
    assert sim.cur_stat(P, T, 'toss') == 1


def test_konoha_never_gives_away_the_planned_attacker():
    P, T = player(hand=['HV-P01-051'], attack=['HV-P01-043', 'HV-P01-050']), context(phase='toss')
    T['plan_attack'] = (P.hand[0], P.hand[0].name)
    konoha_enters(P, T)
    assert nos(P.hand) == ['P01-051']


def test_konoha_swap_is_blocked_by_no_skill_add_hand():
    P, T = player(hand=['HV-P04-065'], attack=['HV-P01-043', 'HV-P01-051', 'HV-P01-050']), context(phase='toss')
    P.restrict = [dict(rule='no_skill_add_hand')]
    konoha_enters(P, T)
    assert nos(P.zones['attack'])[0] == 'P01-043'


def test_swapped_bokuto_attacks_the_same_turn():
    rng = random.Random(1)
    ohand = [C(n) for n in ('HV-P01-050', 'HV-P01-046', 'HV-P01-049', 'HV-P03-062', 'HV-P01-044')]
    opp = sim.Player(ohand, rng, 'B'); opp.deck = []; opp.hand = ohand[:]
    hand = [C('HV-P01-050'), C('HV-P04-064'), C('HV-P01-051')]
    toss = [C('HV-P01-046') for _ in range(2)]
    attack = [C('HV-P01-043'), C('HV-P01-046'), C('HV-P01-049')]  # 3 張疊起來，木兎上場後 Guts 奇數
    deck = [C('HV-P01-050') for _ in range(10)]
    P = sim.Player(hand + toss + attack + deck, rng, 'A'); P.deck = deck
    P.hand = hand; P.zones['toss'] = toss; P.zones['attack'] = attack
    result = sim.receive_best(P, opp, 5, 'attack')
    assert result[2] == 7  # 木葉 1+1，木兎 0+5
    assert result[1].zones['attack'][-1].no == 'HV-P01-043'


@pytest.mark.parametrize('op_in, fired', [(5, False), (6, True), (7, False)])
def test_komi_066_fires_only_when_plus_one_exactly_saves_the_ball(op_in, fired):
    P, T = player(hand=['HV-P01-051'], drop=['HV-P01-043'], receive=['HV-P01-046', 'HV-P01-046']), context(op_in, 'receive')  # 付掉的 Guts 是 2 年級，撿不回來
    sim.enter(P, T, 'receive', C('HV-P04-066'), True)
    assert sim.cur_stat(P, T, 'receive') == (6 if fired else 5)
    assert nos(P.hand) == (['P01-043'] if fired else ['P01-051'])


def test_komi_066_fetches_bokuto_063_once_the_names_are_ready():
    P, T = player(hand=['HV-P01-051'], drop=['HV-P04-063', 'HV-P01-043'], receive=['HV-P01-050', 'HV-P01-050'],
                  attack=['HV-P01-046', 'HV-P01-050', 'HV-P01-051']), context(3, 'receive')
    sim.enter(P, T, 'receive', C('HV-P04-066'), True)
    assert nos(P.hand) == ['P04-063']


def test_washio_067_fires_whenever_it_can_pay():
    P, T = player(hand=['HV-P01-051'], serve=['HV-P01-044']), context(phase='serve')
    washio = C('HV-P04-067')
    sim.enter(P, T, 'serve', washio, True)
    assert sim.cur_stat(P, T, 'serve') == washio.b['srv'] + 3
    assert len(P.hand) == 2  # 棄 1 張、抽 2 張


def test_komi_066_pays_nothing_for_a_fetch_it_cannot_make():
    P, T = player(hand=['HV-P01-051'], drop=['HV-P04-063'], receive=['HV-P01-046', 'HV-P01-046'],
                  attack=['HV-P01-046', 'HV-P01-050', 'HV-P01-051']), context(3, 'receive')
    P.restrict = [dict(rule='no_skill_add_hand')]
    sim.enter(P, T, 'receive', C('HV-P04-066'), True)
    assert nos(P.hand) == ['P01-051'] and len(P.zones['receive']) == 3


def test_komi_066_discards_around_the_planned_attacker():
    P, T = player(hand=['HV-PR-026', 'HV-P01-050'], receive=['HV-P01-046', 'HV-P01-046']), context(6, 'receive')  # PR-026 比 P01-050 便宜
    T['plan_attack'] = (P.hand[0], P.hand[0].name)
    sim.enter(P, T, 'receive', C('HV-P04-066'), True)
    assert sim.cur_stat(P, T, 'receive') == 6
    assert 'PR-026' in nos(P.hand)  # 棄掉的 P01-050 可以被同一個技能撿回來
