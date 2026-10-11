"""赤葦 P01-045 撿回木兎 P01-043，同一拍攻擊打 8；付 Guts 調奇數。"""
import os, sys, random
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
ok = lambda name, v: print(('OK  ' if v else 'FAIL') + ' ' + name)
rng = random.Random(1)
for L in (3, 4):  # 攻擊區原本 L 張（含最上面）：兩種奇偶都要能調成奇數
    P = sim2.Player([C('HV-P01-050')] * 5, rng, 'A'); P.deck = [C('HV-P01-050') for _ in range(10)]
    opp = sim2.Player([C('HV-P01-050')] * 5, rng, 'B'); opp.hand = [C(n) for n in ('HV-P01-050', 'HV-P01-046', 'HV-P01-049', 'HV-P03-062', 'HV-P01-044')]  # 能接 3 點、接不住 8 點
    P.hand = [C('HV-P01-050'), C('HV-P01-045'), C('HV-P01-051')]
    P.drop = [C('HV-P01-043')]
    P.zones['toss'] = [C('HV-P01-046') for _ in range(4)]
    P.zones['attack'] = [C('HV-P01-049') for _ in range(L)]
    rb = sim2.receive_best(P, opp, 5, 'attack')
    Pn, op = rb[1], rb[2]
    ok('攻擊區 %d 張：撿回 P01-043 同拍攻擊，進攻 3+5=8（實得 %d）' % (L, op),
       op == 8 and Pn.zones['attack'][-1].no == 'HV-P01-043' and Pn.stats.get('撿回立刻攻擊'))
