import os, sys, random
os.environ['DH_BATCH3'] = '1'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
ok = lambda name, v: print(('OK  ' if v else 'FAIL') + ' ' + name)
rng = random.Random(1)
def newp(op=3, src='attack', phase=None):
    P = sim2.Player([C('HV-P01-050')] * 10, rng, 'X'); o = sim2.Player([C('HV-P01-050')] * 10, rng, 'O')
    T = sim2.newT(o, op, src)
    if phase: T['phase'] = phase
    return P, o, T
FX = lambda P, T, effs, z='attack': sim2.apply_effects(effs, P, T, z)
P, o, T = newp(); o.hand = [C('HV-P01-050')] * 2; n = len(o.deck)
FX(P, T, [dict(type='opp_reshuffle_draw', n=6)])
ok('洗回重抽：對手手牌 6 張，牌庫+手牌總數不變', len(o.hand) == 6 and len(o.deck) + len(o.hand) == n + 2)
# 溫田 D04-013：翻到青葉城西事件 → 入手並再抽 1；翻到非青葉 → 放底
P, o, T = newp(); P.hand = []
P.deck = [C('HV-P01-086')] + P.deck
FX(P, T, [dict(type='reveal_top_take_school', school='青葉城西')])
ok('D04-013：翻到青葉城西事件 → 入手 + 抽 1（手牌 2）', len(P.hand) == 2)
P, o, T = newp(); P.hand = []; top = P.deck[0]
FX(P, T, [dict(type='reveal_top_take_school', school='青葉城西')])
ok('D04-013：翻到梟谷角色 → 不入手、放牌庫底', len(P.hand) == 0 and P.deck[-1] is top)
# 數值 ≥8
P, o, T = newp(); P.zones['attack'] = [C('HV-P01-035')]
ok('zone_stat_ge 對攻擊 1..', isinstance(sim2.cond_ok(dict(type='zone_stat_ge', zone='attack', n=99), P, T), bool))
# 接球 −1 規則
P, o, T = newp(); P.restrict.append(dict(rule='opp_rcv_add', n=-1, duration='next_opp_turn'))
sim2.enter_skills(P, T, 'receive', C('HV-P01-050'), True, None, '小見', False)
ok('接球角色登場 −1', T['mod'].get('receive', 0) == -1)
# 年級篩選
ok('filt_ok grade=3：及川(3年) 成立、国見(1年) 不成立', sim2.filt_ok(C('HV-P02-056'), dict(school='青葉城西', grade=3)) and not sim2.filt_ok(C('HV-P01-041'), dict(school='青葉城西', grade=3)))
