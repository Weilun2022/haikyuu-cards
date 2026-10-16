"""第四彈稲荷崎（DH_P04=1）：P04-099 撈どんぴしゃり、北 P04-070、侑 P04-068。"""
import os, sys, random
os.environ.setdefault('DH_P04', '1')
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
ok = lambda name, v: print(('OK  ' if v else 'FAIL') + ' ' + name)
rng = random.Random(1); F = 'HV-P02-022'
def pl(): return sim2.Player([C(F)] * 5, rng, 'X')
opp = pl()

# 1. P04-099：舉球侑、牌庫頂 3 張含どんぴしゃり → 抽 1、舉球 +1、撈到どんぴしゃり，其餘 2 張到牌庫底
P = pl(); T = sim2.newT(opp, 3, 'attack'); T['phase'] = 'toss'
P.zones['toss'] = [C('HV-D03-004')]; T['names']['toss'] = '宮 侑'
P.deck = [C(F), C(F), C('HV-P02-087'), C('HV-P02-024'), C('HV-P02-024')]
P.hand = [C('HV-P04-099')]
sim2.play_event(P, T, P.hand[0], 'toss')
ok('P04-099：舉球 2+1=3（實得 %d）、手上有どんぴしゃり、其餘 2 張到牌庫底' % sim2.cur_stat(P, T, 'toss'),
   sim2.cur_stat(P, T, 'toss') == 3 and any(c.no == 'HV-P02-087' for c in P.hand) and len(P.deck) == 3 and P.deck[0].no == 'HV-P02-024')  # 抽走第 1 張，再看 3 張撈どんぴしゃり，其餘 2 張到底
# 每回合 1 次
P.hand.append(C('HV-P04-099')); n0 = len(P.hand)
sim2.play_event(P, T, P.hand[-1], 'toss')
ok('P04-099：同一回合第 2 張不能用', len(P.hand) == n0)
# 舉球不是侑 → 不能打
P = pl(); T = sim2.newT(opp, 3, 'attack'); T['phase'] = 'toss'
P.zones['toss'] = [C('HV-P02-077')]; T['names']['toss'] = '宮 治'; P.hand = [C('HV-P04-099')]
sim2.play_event(P, T, P.hand[0], 'toss')
ok('P04-099：舉球是治 → 不能打', len(P.hand) == 1)

# 2. 北 P04-070：Event 區稲荷崎 3 張、接不住 → 棄稲荷崎 1 張，接球 5+2=7
P = pl(); T = sim2.newT(opp, 7, 'attack'); T['phase'] = 'receive'
P.evz = [C('HV-P02-087'), C('HV-P02-087'), C('HV-P02-084')]; P.hand = [C(F)]
sim2.enter(P, T, 'receive', C('HV-P04-070'), from_hand=True)
ok('北 P04-070：接球 7（實得 %d）' % sim2.cur_stat(P, T, 'receive'), sim2.cur_stat(P, T, 'receive') == 7 and not P.hand)
P = pl(); T = sim2.newT(opp, 7, 'attack'); T['phase'] = 'receive'
P.evz = [C('HV-P02-087'), C('HV-P02-087')]; P.hand = [C(F)]
sim2.enter(P, T, 'receive', C('HV-P04-070'), from_hand=True)
ok('北 P04-070：Event 區只有 2 張 → 不發動', sim2.cur_stat(P, T, 'receive') == 5 and len(P.hand) == 1)

# 3. 侑 P04-068：疊在侑上發球、全部稲荷崎 → 抽 1、對手 S 舉球 −1
P = pl(); P.deck = [C(F) for _ in range(3)]; T = sim2.newT(opp, 0, None); T['phase'] = 'serve'
P.zones['serve'] = [C('HV-D03-004')]; P.hand = []
sim2.enter(P, T, 'serve', C('HV-P04-068'), from_hand=True)
ok('侑 P04-068：抽 1、封鎖對手 S 舉球', len(P.hand) == 1 and any(l['rule'] == 'opp_s_toss_add' for l in T['locks']))
B = pl(); B.restrict = [dict(rule='opp_s_toss_add', n=-1)]; TB = sim2.newT(P, 3, 'serve'); TB['phase'] = 'toss'
sim2.enter(B, TB, 'toss', C('HV-D03-004'), from_hand=True)
ok('被封鎖方：從手牌出 S 舉球 2−1=1（實得 %d）' % sim2.cur_stat(B, TB, 'toss'), sim2.cur_stat(B, TB, 'toss') == 1)
P = pl(); P.deck = [C(F)]; T = sim2.newT(opp, 0, None); T['phase'] = 'serve'
P.zones['serve'] = [C('HV-P02-022')]; P.hand = []
sim2.enter(P, T, 'serve', C('HV-P04-068'), from_hand=True)
ok('侑 P04-068：底下不是侑 → 不發動', not P.hand)
