"""闇路 P01-089：抽牌階段先打，撿到的木兎同一拍就能當攻擊角色。"""
import os, sys, random
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
ok = lambda name, v: print(('OK  ' if v else 'FAIL') + ' ' + name)
rng = random.Random(1)
P = sim2.Player([C('HV-P01-050')] * 5, rng, 'A')
# 手上：接球小見、舉球赤葦 P01-046、闇路；沒有攻擊手。牌庫：抽牌抽到非梟谷（烏野影山），闇路看到木兎 P01-044
P.hand = [C('HV-P01-050'), C('HV-P01-046'), C('HV-P01-089')]
P.deck = [C('HV-P01-006'), C('HV-P01-074'), C('HV-P01-044'), C('HV-P01-078')] + [C('HV-P01-006') for _ in range(6)]
opp = sim2.Player([C('HV-P01-050')] * 5, rng, 'B')
opp.hand = [C(n) for n in ('HV-P01-050', 'HV-P01-046', 'HV-P01-049', 'HV-P03-062')]
res = sim2.take_turn(P, opp, 5, 'attack')
Pn = res[1]
atk = Pn.zones['attack'][-1].no if Pn.zones['attack'] else None
ok('闇路在抽牌階段打出並撿到木兎', Pn.stats.get('闇路檢索命中') == 1)
ok('撿到的木兎同一拍當攻擊角色（實際攻擊角色：%s）' % atk, res[0] == 'ok' and atk == 'HV-P01-044')
