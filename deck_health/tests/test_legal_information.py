"""M1 資訊邊界與試算隔離：以固定觀測驗證決策與正式結算。"""
import json
import random
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import sim2 as sim


def card(name, *, blk=0, rcv=0, tos=0, atk=0, srv=1):
    return sim.Card(dict(card_no=name, name=name, category='CHARACTER',
                         position='WS', school='S', srv=srv, blk=blk,
                         rcv=rcv, tos=tos, atk=atk, skill_jp='-'))


@pytest.mark.parametrize('src', ['attack', 'serve'])
def test_evaluation_does_not_read_opponent_hidden_hand(src):
    weak = [card('weak' + str(i)) for i in range(3)]
    strong = [card('strong' + str(i), blk=9, rcv=9, tos=1, atk=3)
              for i in range(3)]
    pool = weak + strong
    p = sim.Player(pool, random.Random(7), 'A')
    opp = sim.Player(pool, random.Random(8), 'B')
    opp.hand, opp.deck = weak[:], strong[:]
    before = sim.evaluate(p, 5, [], False, opp, src)
    opp.hand, opp.deck = strong[:], list(reversed(weak))
    assert sim.evaluate(p, 5, [], False, opp, src) == before


def test_block_or_receive_choice_cannot_know_future_draw():
    blocker = card('blocker', blk=4)
    setter = card('setter', tos=2)
    attacker = card('attacker', atk=5)
    good, weak = card('good', rcv=5), card('weak')
    pool = [blocker, setter, attacker, good, weak]
    p = sim.Player(pool, random.Random(7), 'A')
    p.hand = [blocker, setter, attacker]
    opp = sim.Player(pool, random.Random(8), 'B')
    opp.hand = [card('opp' + str(i), blk=1, rcv=1, tos=1, atk=1)
                for i in range(3)]
    p.deck = [good, weak]
    first = sim.take_turn(p.clone(), opp, 4, 'attack')
    p.deck = [weak, good]
    second = sim.take_turn(p.clone(), opp, 4, 'attack')
    # 選接球後才抽牌：抽到接不住的牌會輸球（loss），但「選了接球」這個決定不能隨牌庫順序改變
    chose = lambda r: r[-1] if r[0] == 'ok' else 'receive'
    assert chose(first) == chose(second)
    assert not str(chose(first)).startswith('block')


def test_unselected_serve_candidate_cannot_reshuffle_real_opponent():
    u = sim.load_cards(str(HERE.parent / 'cards_data.js'))
    c = lambda no: sim.Card(u[no])
    p = sim.Player([c('HV-P01-034') for _ in range(10)], random.Random(5), 'A')
    opp = sim.Player([c('HV-P01-050') for _ in range(20)] +
                     [c('HV-P01-046') for _ in range(3)], random.Random(6), 'B')
    opp.deck = [c('HV-P01-050') for _ in range(20)]
    strong = card('SYN-M1-SERVE', srv=20, blk=1, rcv=1, tos=1, atk=1)
    p.hand = [c('HV-P01-034'), strong]
    p.zones['serve'] = [c('HV-P01-033'), c('HV-P01-033')]
    opp.hand = [c('HV-P01-046') for _ in range(3)]
    before = (tuple(opp.hand), tuple(opp.deck), opp.rng.getstate())
    result = sim.serve_turn(p, opp)
    assert result[1].zones['serve'][-1].no == strong.no
    assert (tuple(opp.hand), tuple(opp.deck), opp.rng.getstate()) == before


def test_trial_clone_keeps_real_random_stream_unchanged():
    p = sim.Player([card('x')] * 12, random.Random(12), 'A')
    before = (tuple(p.deck), tuple(p.hand), p.rng.getstate())
    candidate = p.clone()
    candidate.rng.shuffle(candidate.deck)
    candidate.draw(3)
    assert (tuple(p.deck), tuple(p.hand), p.rng.getstate()) == before


def test_selected_oikawa_resolves_once_on_real_opponent():
    u = sim.load_cards(str(HERE.parent / 'cards_data.js'))
    c = lambda no: sim.Card(u[no])
    p = sim.Player([c('HV-P01-034')] * 10, random.Random(5), 'A')
    opp = sim.Player([c('HV-P01-050')] * 20 + [c('HV-P01-046')] * 3, random.Random(6), 'B')
    opp.deck = [c('HV-P01-050')] * 20
    p.hand = [c('HV-P01-034')]
    p.zones['serve'] = [c('HV-P01-033'), c('HV-P01-033')]
    opp.hand = [c('HV-P01-046')] * 3
    expected = opp.clone()
    expected.deck += expected.hand
    expected.hand = []
    expected.rng.shuffle(expected.deck)
    expected.draw(6)
    result = sim.serve_turn(p, opp)
    assert result[0] == 'ok'
    assert result[1].stats['對手手牌洗回重抽'] == 1
    assert (opp.hand, opp.deck, opp.rng.getstate()) == (expected.hand, expected.deck, expected.rng.getstate())


def test_yamaguchi_trial_does_not_read_hidden_event():
    event, character = card('event'), card('character')
    event.ev = True
    p = sim.Player([], random.Random(1), 'A')
    opp = sim.Player([event, character], random.Random(2), 'B')
    effect = dict(type='lock_unless_opp_places', p_place=1,
                  lock=dict(rule='owner_draw_any', duration='next_opp_turn'))
    outcomes = []
    for hand, deck in (([event], [character]), ([character], [event])):
        opp.hand, opp.deck = hand, deck
        candidate, context = sim.trial(p, opp, 0, 'serve')
        sim.apply_effects([effect], candidate, context, 'serve')
        outcomes.append((context['locks'], candidate.stats))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize('has_event', [False, True])
def test_selected_yamaguchi_resolves_after_choice(has_event):
    event, character = card('event'), card('character')
    event.ev = True
    p = sim.Player([], random.Random(1), 'A')
    opp = sim.Player([event, character], random.Random(2), 'B')
    opp.hand = [event if has_event else character]
    candidate, context = sim.trial(p, opp, 0, 'serve')
    sim.apply_effects([dict(type='lock_unless_opp_places', p_place=1,
                           lock=dict(rule='owner_draw_any'))], candidate, context, 'serve')
    selected = sim.commit_trial(sim.remember(candidate, context), p, opp)
    assert context['locks'] == ([] if has_event else [dict(rule='owner_draw_any')])
    assert selected.stats == ({'對手放事件化解': 1} if has_event else {'封鎖:owner_draw_any': 1})


def test_fetched_attacker_choice_cannot_peek_at_next_card():
    receiver, setter = card('receiver', rcv=5), card('setter', tos=2)
    safe, fetched = card('safe', atk=4), card('fetched', atk=3)
    event, blank = card('event'), card('blank')
    event.ev = True
    setter.skills = [dict(timing='on_enter', zones=['toss'], effects=[
        dict(type='drop_to_hand', max=1, filter=dict(name='fetched'))])]
    fetched.skills = [dict(timing='on_enter', zones=['attack'], effects=[
        dict(type='mill_tiers', n=1, count='event', tiers=[dict(ge=1, effects=[
            dict(type='stat_add', target='this', stat='atk', n=8)])])])]
    pool = [receiver, setter, safe, fetched, event, blank]
    defender = card('defender', blk=9, rcv=9, tos=2, atk=3)
    opp = sim.Player([defender] * 6, random.Random(8), 'B')
    opp.hand, opp.deck = [defender] * 3, [defender] * 3
    choices = []
    for deck in ([event, blank], [blank, event]):
        p = sim.Player(pool, random.Random(7), 'A')
        p.hand, p.drop, p.deck = [receiver, setter, safe], [fetched], deck
        result = sim.receive_best(p, opp, 5, 'attack')
        assert result is not None
        choices.append(result[1].zones['attack'][-1].no)
    assert choices[0] == choices[1]


@pytest.mark.parametrize('policy', ['lethal', 'lethal_smart'])
@pytest.mark.parametrize('can_defend', [False, True])
def test_lethal_payment_uses_visible_information(monkeypatch, policy, can_defend):
    monkeypatch.setitem(sim.CFG, 'hand_bottom_policy', policy)
    u = sim.load_cards(str(HERE.parent / 'cards_data.js'))
    attacker = sim.Card(u['HV-D03-002'])
    setter = card('宮 侑', tos=2)
    weak = card('weak')
    strong = card('strong', blk=20 if can_defend else 0)
    results = []
    for hand, deck in (([weak], [strong]), ([strong], [weak])):
        p = sim.Player([attacker, setter, weak], random.Random(1), 'A')
        p.hand, p.deck, p.zones['toss'] = [attacker, weak], [], [setter]
        opp = sim.Player([weak, strong], random.Random(2), 'B')
        opp.hand, opp.deck = hand, deck
        context = sim.newT(opp, 0, 'attack')
        op = sim.attack_part(p, context, attacker, attacker.name, True)
        results.append((op, tuple(p.hand), p.stats.get('技能:HV-D03-002', 0)))
    assert results[0] == results[1]
    assert results[0][2] == (0 if can_defend else 1)


@pytest.mark.parametrize('hidden_set', [False, True])
def test_server_choice_cannot_peek_at_next_card(hidden_set):
    safe, risky = card('safe', srv=4), card('risky', srv=3)
    event, blank = card('event'), card('blank')
    event.ev = True
    risky.skills = [dict(timing='on_enter', zones=['serve'], effects=[
        dict(type='mill_tiers', n=1, count='event', tiers=[dict(ge=1, effects=[
            dict(type='stat_add', target='this', stat='srv', n=8)])])])]
    defender = card('defender', blk=9, rcv=9, tos=2, atk=3)
    choices = []
    for deck in ([event, blank], [blank, event]):
        p = sim.Player([safe, risky, event, blank], random.Random(7), 'A')
        p.hand, p.deck = [safe, risky], deck
        if hidden_set: p.deck, p.setz = deck[:1], deck[1:]
        opp = sim.Player([defender] * 6, random.Random(8), 'B')
        opp.hand, opp.deck = [defender] * 3, [defender] * 3
        result = sim.serve_turn(p, opp)
        choices.append(result[1].zones['serve'][-1].no)
    assert choices[0] == choices[1]


def test_blocker_choice_cannot_peek_at_skill_mill():
    safe, risky = card('safe', blk=5), card('risky', blk=5)
    event, blank = card('event'), card('blank')
    event.ev = True
    risky.skills = [dict(timing='on_enter', zones=['block'], effects=[
        dict(type='mill_tiers', n=1, count='event', tiers=[dict(ge=1, effects=[
            dict(type='keyword', name='ドシャット', n=15)])])])]
    defender = card('defender', blk=9, rcv=9, tos=2, atk=3)
    choices = []
    for deck in ([event, blank], [blank, event]):
        p = sim.Player([safe, risky, event, blank], random.Random(7), 'A')
        p.hand, p.deck = [safe, risky], deck
        opp = sim.Player([defender] * 6, random.Random(8), 'B')
        opp.hand, opp.deck = [defender] * 3, [defender] * 3
        result = sim.take_turn(p, opp, 5, 'attack')
        assert result[0] == 'ok'
        choices.append(result[1].zones['block'][-1].no)
    assert choices[0] == choices[1]


@pytest.mark.parametrize('field,value', [('once_used', {'used'}), ('deferred', ['pending']),
                                        ('defer_when', ['pending'])])
def test_sibling_trials_do_not_share_pending_effects(field, value):
    p = sim.Player([], random.Random(1), 'A')
    context = sim.newT(p, 0, 'attack')
    context[field] = value.copy()
    sibling = sim.cloneT(context)
    sibling[field].clear()
    assert context[field] == value


def test_chosen_receive_loss_keeps_actual_draw():
    drawn = card('drawn')
    p = sim.Player([drawn], random.Random(1), 'A')
    opp = sim.Player([], random.Random(2), 'B')
    result = sim.take_turn(p, opp, 20, 'attack')
    assert result[0] == 'loss'
    assert result[1].hand == [drawn]
    assert result[1].deck == []


def test_serve_selects_actual_drawn_event_not_hypothetical_copy():
    server = card('server')
    server.skills = [dict(timing='on_enter', zones=['serve'], effects=[dict(type='draw', n=1)])]
    events = [card('event') for _ in range(2)]
    for event in events:
        event.ev, event.phases = True, {'serve'}
        event.skills = [dict(timing='event', phases=['serve'], effects=[
            dict(type='stat_add', target='this', stat='srv', n=20)])]
    defender = card('defender', blk=9, rcv=9, tos=2, atk=3)
    for deck in (events, list(reversed(events))):
        p = sim.Player([server] + events, random.Random(1), 'A')
        p.hand, p.deck = [server], deck[:]
        opp = sim.Player([defender] * 6, random.Random(2), 'B')
        opp.hand = [defender] * 3
        result = sim.serve_turn(p, opp)
        assert result[1].evz == [deck[0]]
        assert result[1].deck == [deck[1]]


@pytest.mark.parametrize('decision', ['serve', 'receive', 'fetch', 'block'])
@pytest.mark.parametrize('seed', [1, 7, 19])
def test_full_choices_ignore_opponent_hidden_zones(decision, seed):
    receiver, setter = card('receiver', rcv=5), card('setter', tos=2)
    attacker, fetched = card('attacker', atk=3), card('fetched', atk=40)
    blank, blocker = card('blank'), card('blocker', blk=9)
    server = card('server', srv=6)
    server.skills = [dict(timing='on_enter', zones=['serve'], effects=[
        dict(type='lock_unless_opp_places', p_place=1, lock=dict(rule='owner_draw_any'))])]
    if decision == 'fetch':
        setter.skills = [dict(timing='on_enter', zones=['toss'], effects=[
            dict(type='drop_to_hand', max=1, filter=dict(name='fetched'))])]
    own_hand = [receiver, setter, attacker] if decision in ('receive', 'fetch') else [blocker, server]
    own_drop = [fetched] if decision == 'fetch' else []
    pool = own_hand + own_drop + [blank] * 2
    weak = [card('weak' + str(i)) for i in range(3)]
    strong = [card('strong' + str(i), blk=9, rcv=9, tos=2, atk=3) for i in range(3)]
    weak[0].ev = True
    choices = []
    for hand, deck in ((weak, strong), (strong, weak), (weak, list(reversed(strong)))):
        p = sim.Player(pool, random.Random(seed), 'A')
        p.hand, p.drop, p.deck = own_hand[:], own_drop[:], [blank] * 2
        opp = sim.Player(weak + strong, random.Random(seed + 1), 'B')
        opp.hand, opp.deck = hand[:], deck[:]
        if decision == 'serve': result = sim.serve_turn(p, opp)
        elif decision == 'block': result = sim.take_turn(p, opp, 8, 'attack')
        else:
            result = sim.receive_best(p, opp, 5, 'attack')
            assert result is not None
        after = result[1]
        if decision == 'fetch': assert after.zones['attack'][-1] is fetched
        choices.append(tuple((z, tuple(c.no for c in cards)) for z, cards in after.zones.items()))
    assert choices[0] == choices[1] == choices[2]


def two_attack_setter():
    """舉球登場時翻牌頂，翻到事件才成立二段攻擊：成立與否在選定路線後才知道。"""
    t = card('t', tos=2)
    t.skills = [dict(timing='on_enter', zones=['toss'], effects=[
        dict(type='optional', effects=[]),
        dict(type='mill_tiers', n=1, count='event',
             tiers=[dict(ge=1, effects=[dict(type='keyword', name='ツーアタック', n=20)])])])]
    return t


@pytest.mark.parametrize('top_is_event, op, action, attackers', [
    (True, 20, 'receive2', []),
    (False, 5, 'receive', ['a']),  # 沒成立：舉球已結算，看到結果後照常攻擊，不是輸
])
def test_two_attack_plan_attacks_normally_when_reveal_misses(top_is_event, op, action, attackers):
    r, t, a, event, blank = card('r', rcv=5), two_attack_setter(), card('a', atk=3), card('ev'), card('blank')
    event.ev = True
    p = sim.Player([r, t, a] + [event] * 6 + [blank], random.Random(1), 'A')
    p.hand, p.deck = [r, t, a], [event, blank] if top_is_event else [blank, blank]
    d = card('d', blk=9, rcv=9, tos=2, atk=3)
    opp = sim.Player([d] * 6, random.Random(2), 'B')
    opp.hand, opp.deck = [d] * 3, [d] * 3
    result = sim.receive_best(p, opp, 5, 'attack')
    assert (result[2], result[6]) == (op, action)
    assert [c.no for c in result[1].zones['attack']] == attackers


@pytest.mark.parametrize('kind', ['onetouch', 'endblock'])
def test_forced_block_plan_that_fails_keeps_resolved_state(monkeypatch, kind):
    monkeypatch.setattr(sim, 'onetouch_n' if kind == 'onetouch' else 'has_end_block', lambda c: 1)
    c = card('c')
    p = sim.Player([c], random.Random(1), 'A')
    p.hand, p.deck = [c], [card('x')]
    opp = sim.Player([], random.Random(2), 'B')
    result = sim.resolve_turn(p, opp, 9, 'attack', forced=(kind, (c,)))
    assert result[0] == 'loss'
    assert c not in result[1].hand  # 已經登場的牌不會因判輸而回到手牌


def test_loser_gift_is_paid_to_the_winner(monkeypatch):
    u = sim.load_cards(str(HERE.parent / 'cards_data.js'))
    deck = json.loads((HERE / 'deck.json').read_text(encoding='utf-8'))
    a, b = sim.build(u, deck), sim.build(u, deck)
    paid, draw = [], sim.Player.draw

    def lose_with_gift(P, opp, op_in, src):
        P.gift = 3
        return ('loss', P)

    def spy(self, n=1):
        paid.append(n)
        return draw(self, n)

    monkeypatch.setattr(sim, 'take_turn', lose_with_gift)
    monkeypatch.setattr(sim.Player, 'draw', spy)
    sim.play_game(a, b, random.Random(1))
    assert 3 in paid


def test_planning_random_stream_does_not_depend_on_real_seed():
    def stream(seed):
        p = sim.Player([card(str(i)) for i in range(6)], random.Random(seed), 'A')
        p.draw(3)
        state = p.rng.getstate()
        values = [s.rng.random() for s in sim.planning_states(p)]
        assert p.rng.getstate() == state  # 規劃不消耗真實亂數
        return values
    assert stream(1) == stream(2)

