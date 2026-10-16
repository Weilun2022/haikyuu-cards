"""冠軍稲荷崎用卡（DH_CHAMP=1）：月島 +6 攔網、小作手坑、尾白、侑 P02-017、角名、P02-089。"""
import os, sys, random
os.environ.setdefault('DH_CHAMP', '1')
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
ok = lambda name, v: print(('OK  ' if v else 'FAIL') + ' ' + name)
rng = random.Random(1)
F = 'HV-P02-022'
EV = 'HV-P02-087'

def pl(): return sim2.Player([C(F)] * 5, rng, 'X')

# 1. 月島：攻方 Event 區 ≥2、守方手上有事件 → 1 張就能攔 8
att = pl(); att.evz = [C(EV), C(EV)]
B = pl(); B.hand = [C('HV-P02-003'), C(EV), C(F), C(F), C(F)]
tot, _ = sim2.block_total(B, (B.hand[0],), att, [])
ok('月島：預估攔網 2+6=8（實得 %d）' % tot, tot == 8)
ok('月島：對手 8 點只要 1 張攔網（response_cost=%s）' % sim2.response_cost(B, 8, [], False, attacker=att), sim2.response_cost(B, 8, [], False, attacker=att) == 1)
att.evz = [C(EV)]
ok('月島：攻方 Event 區只有 1 張 → 不加', sim2.block_total(B, (B.hand[0],), att, [])[0] == 2)
att.evz = [C(EV), C(EV)]; B.hand = [C('HV-P02-003'), C(F), C(F)]
ok('月島：手上沒有事件 → 不加', sim2.block_total(B, (B.hand[0],), att, [])[0] == 2)
# 實際攔網：take_turn 選 1 張月島攔下 8 點，事件進 Event 區、抽 1
B = pl(); B.deck = [C(F) for _ in range(10)]; B.hand = [C('HV-P02-003'), C(EV), C(F), C(F)]
res = sim2.take_turn(B, att, 8, 'attack')
ok('月島：take_turn 用 1 張攔下 8 點（行動 %s）' % res[-1], res[0] == 'ok' and res[-1] == 'block1' and len(res[1].evz) == 1)

# 2. 角名的封鎖：中間攔網的攔網值當作 0
B = pl(); B.hand = [C('HV-D03-007'), C('HV-P02-033')]  # 角名 D03-007 攔 3、大耳 P02-033 攔 3
lock = [dict(rule='center_no_blk')]
ok('角名封鎖：兩張攔 3 合計只算 3', sim2.block_total(B, tuple(B.hand), None, lock)[0] == 3)
ok('沒有封鎖：合計 6', sim2.block_total(B, tuple(B.hand), None, [])[0] == 6)

# 3. 小作手坑：稲荷崎接球角色 +2
B = pl(); B.hand = [C('HV-P02-035')]
ok('小作：對稲荷崎接球角色 +2', sim2.trap_bonus(B, C('HV-P02-034')) == 2)
ok('小作：對烏野角色不加', sim2.trap_bonus(B, C('HV-P01-002')) == 0)
B.hand = [C('HV-P01-013')]
ok('縁下（回歸）：對烏野角色 +2', sim2.trap_bonus(B, C('HV-P01-002')) == 2)

# 4. 尾白：接不住時棄稲荷崎的牌，接球 4+2
P = pl(); opp = pl(); T = sim2.newT(opp, 6, 'attack'); T['phase'] = 'receive'
P.hand = [C(F), C('HV-P01-002')]
sim2.enter(P, T, 'receive', C('HV-P03-045'), from_hand=True)
ok('尾白：接球 4+2=6，棄的是稲荷崎的牌', sim2.cur_stat(P, T, 'receive') == 6 and P.drop[-1].no == F)

# 5. 侑 P02-017：棄牌區 6 種名字 → 舉球 3、撈回 WS/MB
P = pl(); T = sim2.newT(opp, 3, 'attack'); T['phase'] = 'toss'
P.zones['toss'] = [C(F), C(F), C(F)]
P.drop = [C(n) for n in ('HV-P02-034', 'HV-P02-024', 'HV-P02-022', 'HV-D03-004', 'HV-P02-077', 'HV-P02-027')]
sim2.enter(P, T, 'toss', C('HV-P02-017'), from_hand=True)
ok('侑 P02-017：6 種 → 舉球 1+2=3（實得 %d）、撈回 WS/MB' % sim2.cur_stat(P, T, 'toss'),
   sim2.cur_stat(P, T, 'toss') == 3 and any(c.pos & {'WS', 'MB'} for c in P.hand))
P = pl(); T = sim2.newT(opp, 3, 'attack'); T['phase'] = 'toss'; P.zones['toss'] = [C(F), C(F), C(F)]
P.drop = [C(n) for n in ('HV-P02-034', 'HV-P02-024', 'HV-P02-022', 'HV-D03-004', 'HV-P02-077')]
sim2.enter(P, T, 'toss', C('HV-P02-017'), from_hand=True)
ok('侑 P02-017：5 種 → 不發動、不付 Guts', sim2.cur_stat(P, T, 'toss') == 1 and len(P.zones['toss']) == 4)

# 6. 角名 P02-027：6 種 → 攻擊 +2、對手中間攔網無效
P = pl(); T = sim2.newT(opp, 3, 'attack'); T['phase'] = 'attack'
P.drop = [C(n) for n in ('HV-P02-034', 'HV-P02-024', 'HV-P02-022', 'HV-D03-004', 'HV-P02-077', 'HV-P03-045')]
sim2.enter(P, T, 'attack', C('HV-P02-027'), from_hand=True)
ok('角名：攻擊 2+2=4、封鎖中間攔網', sim2.cur_stat(P, T, 'attack') == 4 and any(l['rule'] == 'center_no_blk' for l in T['locks']))

# 7. P02-089：抽牌階段撈回侑、治、宮兄弟，3 張都拿到則棄 1
P = pl(); P.hand = [C('HV-P02-089'), C(F)]; P.drop = [C('HV-D03-004'), C('HV-P02-020'), C('HV-P02-077')]
sim2.draw_phase_events(P, opp, 3, 'attack')
ok('P02-089：拿 3 張、棄 1（手牌 %d 張）' % len(P.hand), not any(c.no == 'HV-P02-089' for c in P.hand) and len(P.hand) == 3 and len(P.drop) == 1)

# 8. 手坑有幾張用幾張：2 張小作 → +4
B = pl(); B.hand = [C('HV-P02-035'), C('HV-P02-035')]
ok('小作 ×2：預估 +4（實得 %d）' % sim2.trap_bonus(B, C('HV-P02-034')), sim2.trap_bonus(B, C('HV-P02-034')) == 4)
P = pl(); P.deck = [C(F) for _ in range(5)]; opp = pl()
T = sim2.newT(opp, 10, 'attack')
P.hand = [C('HV-P02-034'), C('HV-D03-004'), C('HV-P02-022'), C('HV-P02-035'), C('HV-P02-035')]
r, t, a = P.hand[0], P.hand[1], P.hand[2]
op = sim2.do_receive_line(P, T, r, t, a, False)
ok('小作 ×2：接球 6+2+2=10 接住 10 點（實得接球 %d）' % sim2.cur_stat(P, T, 'receive'), op is not None and sim2.cur_stat(P, T, 'receive') == 10 and P.stats.get('手坑:HV-P02-035') == 2)
