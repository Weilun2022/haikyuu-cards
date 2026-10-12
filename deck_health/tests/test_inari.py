"""稲荷崎：どん ぴしゃり 叫出侑／治、登場技能延後、宮兄弟、封鎖一觸、手牌攔網 ≤2、北撈事件、D03-002。"""
import os, sys, random
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
ok = lambda name, v: print(('OK  ' if v else 'FAIL') + ' ' + name)
rng = random.Random(1)
FILL = 'HV-P02-022'  # 宮治（無技能）當填充


def setup(toss_top, atk_top, toss_guts, atk_guts, other=None):
    P = sim2.Player([C(FILL)] * 5, rng, 'A'); P.deck = [C(FILL) for _ in range(10)]
    opp = sim2.Player([C(FILL)] * 5, rng, 'B')
    T = sim2.newT(opp, 5, 'attack'); T['phase'] = 'attack'; T['allow_discard_cost'] = True
    P.zones['toss'] = [C(n) for n in toss_guts] + [C(toss_top)]
    P.zones['attack'] = [C(n) for n in atk_guts] + [C(atk_top)]
    for z, L in (other or {}).items(): P.zones[z] = [C(n) for n in L]
    T['names']['toss'] = P.zones['toss'][-1].name; T['names']['attack'] = P.zones['attack'][-1].name
    return P, T


# 1. 侑 D03-004（舉 2）＋治 D03-002（攻 2），Guts 有侑 P02-016 與治 P02-020，叫出的底下都有 ≥3 Guts
P, T = setup('HV-D03-004', 'HV-D03-002', [FILL, FILL, 'HV-P02-016'], [FILL, FILL, FILL, 'HV-P02-020'])
P.hand = [C('HV-P02-087'), C(FILL)]
h0 = len(P.hand)
sim2.play_event(P, T, P.hand[0], 'attack')
toss, atk = sim2.cur_stat(P, T, 'toss'), sim2.cur_stat(P, T, 'attack')
ok('叫出侑 P02-016：舉球 1+2=3（實得 %d）' % toss, P.zones['toss'][-1].no == 'HV-P02-016' and toss == 3)
ok('叫出治 P02-020：攻擊 2+3+1，加上 +1 共 %d+%d=%d（預期 10）' % (toss, atk, toss + atk),
   P.zones['attack'][-1].no == 'HV-P02-020' and toss + atk == 10)
ok('封鎖：一觸／接球手牌技能無效、手牌攔網 ≤2',
   any(l['rule'] == 'nullify_onetouch_and_receive_hand' for l in T['locks'])
   and sim2.max_blockers(T['locks']) == 2)
ok('抽牌：どんぴしゃり 1＋侑 1（手牌 %d → %d）' % (h0, len(P.hand)), len(P.hand) == h0 - 1 + 2)

# 2. QA 1368：+1 先解決，之後叫出的角色登場技能才付 Guts；叫出的卡從 Guts 移走
ok('叫出的侑／治已離開原本的 Guts', sum(c.no == 'HV-P02-016' for c in P.zones['toss'][:-1]) == 0
   and sum(c.no == 'HV-P02-020' for c in P.zones['attack'][:-1]) == 0)

# 3. 宮兄弟在 Guts 裡叫「宮兄弟」，不能被叫出
P, T = setup('HV-D03-004', 'HV-P02-022', [FILL, FILL, 'HV-P02-077'], [FILL, FILL, FILL])
P.hand = [C('HV-P02-087')]
sim2.play_event(P, T, P.hand[0], 'attack')
ok('Guts 裡的宮兄弟不會被叫出', P.zones['toss'][-1].no == 'HV-D03-004')

# 4. 宮兄弟當「宮 侑」舉球可以發動どんぴしゃり（從接球區 Guts 叫治，QA 1370 任一區）
P, T = setup('HV-P02-077', 'HV-P02-022', [FILL], [FILL, FILL, FILL], other={'receive': [FILL, FILL, FILL, 'HV-P02-020', 'HV-P02-034']})
T['names']['toss'] = '宮 侑'
P.hand = [C('HV-P02-087')]
sim2.play_event(P, T, P.hand[0], 'attack')
ok('宮兄弟（選侑）舉球 → 從接球區 Guts 叫出治 P02-020（攻擊 %d）' % sim2.cur_stat(P, T, 'attack'),
   P.zones['attack'][-1].no == 'HV-P02-020')

# 5. 叫出的卡比現在弱就不叫：舉球已是侑 D03-004（2），Guts 只有侑 P02-016 且付不起 3 Guts（底下只有 1 張）
P, T = setup('HV-D03-004', 'HV-P02-022', ['HV-P02-016'], [FILL])
P.hand = [C('HV-P02-087')]
sim2.play_event(P, T, P.hand[0], 'attack')
ok('付不起 Guts 的侑（舉 1）不會蓋掉舉 2 的侑', P.zones['toss'][-1].no == 'HV-D03-004')

# 6. 對手被封鎖時不能一觸、接球手牌技能無效
opp = sim2.Player([C(FILL)] * 5, rng, 'B')
opp.hand = [C('HV-P01-051'), C('HV-P01-050'), C('HV-P01-045'), C('HV-P01-049')]  # 鷲尾一觸(3)＋接 6
lock = [dict(rule='nullify_onetouch_and_receive_hand', duration='next_opp_turn')]
c_free = sim2.response_cost(opp, 9, [], False); c_lock = sim2.response_cost(opp, 9, lock, False)
ok('一觸可用時 9 點要花 3 張（實得 %s），被封鎖後接不住（實得 %s）' % (c_free, c_lock), c_free == 3 and c_lock is None)

# 7. D03-002：舉球是侑，手牌 1 張放牌庫底，攻擊 +2
P, T = setup('HV-D03-004', 'HV-P02-022', [FILL], [FILL])
P.hand = [C(FILL)]; d0 = len(P.deck)
sim2.enter(P, T, 'attack', C('HV-D03-002'), from_hand=True, name='宮 治')
ok('D03-002 攻擊 2+2=4（實得 %d），手牌 1 張放到牌庫底' % sim2.cur_stat(P, T, 'attack'),
   sim2.cur_stat(P, T, 'attack') == 4 and len(P.hand) == 0 and len(P.deck) == d0 + 1)

# 8. 北：Event 區有どんぴしゃり 時，棄 1 張＋付 3 Guts，接球 +1 並撈回
P = sim2.Player([C(FILL)] * 5, rng, 'A'); opp = sim2.Player([C(FILL)] * 5, rng, 'B')
T = sim2.newT(opp, 3, 'attack'); T['phase'] = 'receive'
P.zones['receive'] = [C(FILL) for _ in range(3)]; P.evz = [C('HV-P02-087')]; P.hand = [C(FILL)]
sim2.enter(P, T, 'receive', C('HV-P02-024'), from_hand=True)
ok('北：接球 6、撈回どんぴしゃり', sim2.cur_stat(P, T, 'receive') == 6 and any(c.no == 'HV-P02-087' for c in P.hand) and not P.evz)

# 9. 黒須：Event 區有 2 張攻擊階段的稲荷崎事件時接球 +2
P = sim2.Player([C(FILL)] * 5, rng, 'A'); T = sim2.newT(opp, 7, 'attack'); T['phase'] = 'receive'
P.zones['receive'] = [C(FILL)]; P.evz = [C('HV-P02-087'), C('HV-P02-087')]; P.hand = [C('HV-P02-084')]
sim2.play_event(P, T, P.hand[0], 'receive')
ok('黒須：接球 5+2=7（實得 %d）' % sim2.cur_stat(P, T, 'receive'), sim2.cur_stat(P, T, 'receive') == 7)
