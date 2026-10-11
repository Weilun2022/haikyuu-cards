import os, sys, random
os.environ['DH_PENDING'] = '1'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sim2
from sim2 import Card, Player, newT, enter, cur_stat, cond_ok, assign_distinct, line_names, apply_effects
U = sim2.load_cards(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'cards_data.js'))
C = lambda no: Card(U[no])
rng = random.Random(1)
def player(deck=None):
    P = Player([C('HV-P01-050')] * 10, rng, 'A'); P.deck = deck or [C('HV-P01-050') for _ in range(10)]; return P
opp = player()
ok = lambda name, v: print(('OK  ' if v else 'FAIL') + ' ' + name)

# 1 雙名
ok('PR-013 當舉球選赤葦', line_names(C('HV-P01-050'), C('HV-PR-013'), C('HV-P01-044'))[1] == '赤葦 京治')
ok('PR-013 當攻擊選木兎', line_names(C('HV-P01-050'), C('HV-P01-045'), C('HV-PR-013'))[2] == '木兎 光太郎')
ok('木兎+赤葦+PR-013 三人攔網不行', assign_distinct([C('HV-P01-044'), C('HV-P01-045'), C('HV-PR-013')]) is None)
ok('木兎+PR-013 兩人攔網可以', assign_distinct([C('HV-P01-044'), C('HV-PR-013')]) == ['木兎 光太郎', '赤葦 京治'])
ok('PR-062 算梟谷', '梟谷' in C('HV-PR-062').school)
P = player(); T = newT(opp, 5, 'attack')
enter(P, T, 'toss', C('HV-P01-045'), True); enter(P, T, 'attack', C('HV-PR-013'), True, name='木兎 光太郎')
ok('PR-031 條件：舉球赤葦＋攻擊 PR-013(木兎)', cond_ok(dict(type='self_role_name', role='attack', name='木兎 光太郎'), P, T))

# 2 PR-026
P = player(); T = newT(opp, 7, 'attack'); P.zones['receive'] = [C('HV-P01-050')] * 4
enter(P, T, 'receive', C('HV-PR-026'), True)
ok('PR-026 付 4 Guts 接球 3+4=7', cur_stat(P, T, 'receive') == 7 and len(P.zones['receive']) == 1)

# 3 木葉
P = player(); P.hand = [C('HV-P01-091'), C('HV-P01-050')]; T = newT(opp, 5, 'attack'); T['allow_discard_cost'] = True
P.zones['attack'] = [C('HV-P01-047')]
enter(P, T, 'attack', C('HV-P01-044'), True)
ok('木葉：木兎疊上去攻擊 3+1=4、手牌少 1', cur_stat(P, T, 'attack') == 4 and len(P.hand) == 1)

# 4 赤葦 P02-066
P = player(); T = newT(opp, 5, 'attack'); P.zones['toss'] = [C('HV-P01-050')] * 2
enter(P, T, 'toss', C('HV-P02-066'), True)
ok('P02-066 舉球 1+2=3、牌庫 −3、Guts 付 2', cur_stat(P, T, 'toss') == 3 and len(P.deck) == 7 and len(P.zones['toss']) == 1)
P.zones['attack'] = [C('HV-P01-050')]  # 1 Guts → 木兎 P01-043 出場後 Guts 數奇數
enter(P, T, 'attack', C('HV-P01-043'), True)
ok('P02-066 後木兎 P01-043 沒有 +5', cur_stat(P, T, 'attack') == C('HV-P01-043').b['atk'])
P = player(); T = newT(opp, 5, 'attack'); P.zones['toss'] = [C('HV-P01-050')] * 2
T['plan_attack'] = (C('HV-P01-043'), '木兎 光太郎')
enter(P, T, 'toss', C('HV-P02-066'), True)
ok('計畫用 P01-043 攻擊時不發動 P02-066', cur_stat(P, T, 'toss') == 1 and len(P.deck) == 10)
P = player(deck=[C('HV-P01-050')] * 2); T = newT(opp, 5, 'attack'); P.zones['toss'] = [C('HV-P01-050')] * 2
enter(P, T, 'toss', C('HV-P02-066'), True)
ok('牌庫只剩 2 張不發動', cur_stat(P, T, 'toss') == 1)

# 5 闇路
P = player(deck=[C('HV-P01-074'), C('HV-P01-044'), C('HV-P01-006'), C('HV-P01-050')]); T = newT(opp, 5, 'attack')
apply_effects(sim2.MANUAL['HV-P01-089'][0]['effects'], P, T, 'receive')
ok('闇路：拿到梟谷木兎、其餘 2 張放牌庫底', [c.no for c in P.hand] == ['HV-P01-044'] and [c.no for c in P.deck] == ['HV-P01-050', 'HV-P01-074', 'HV-P01-006'])

# 6 P01-090 鎖定
P = player(); T = newT(opp, 5, 'attack'); P.zones['attack'] = [C('HV-P01-044')]; P.zones['toss'] = [C('HV-P01-045')]
apply_effects(sim2.MANUAL['HV-P01-090'][0]['effects'], P, T, 'attack')
ok('P01-090 全梟谷：攻擊 +1、抽 1、對手被掛「LOSS 時我抽到 7」', T['mod']['attack'] == 1 and len(P.hand) == 1 and any(l['rule'] == 'owner_draw_to_on_loss' for l in T['locks']))
P.zones['receive'] = [C('HV-P01-006')]; T = newT(opp, 5, 'attack')
apply_effects(sim2.MANUAL['HV-P01-090'][0]['effects'], P, T, 'attack')
ok('P01-090 有烏野角色時沒有後半效果', not T['locks'])
