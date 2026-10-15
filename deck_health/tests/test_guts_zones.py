"""每個區域的 Guts 各自獨立：猿杙 PR-026 只付接球區，赤葦 P01-045 只付舉球區＋攻擊區。"""
import os, sys, random
os.environ['DH_PENDING'] = '1'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
ok = lambda name, v: print(('OK  ' if v else 'FAIL') + ' ' + name)
rng = random.Random(1)
opp = sim2.Player([C('HV-P01-050')] * 5, rng, 'B')
P = sim2.Player([C('HV-P01-050')] * 5, rng, 'A'); P.deck = [C('HV-P01-050') for _ in range(10)]
P.zones['receive'] = [C('HV-P01-050')] * 4; P.zones['toss'] = [C('HV-P01-046')] * 3; P.zones['attack'] = [C('HV-P01-049')] * 3
T = sim2.newT(opp, 7, 'attack')
sim2.enter(P, T, 'receive', C('HV-PR-026'), True)
ok('PR-026 付接球區 4 張（接球區剩 1 張＝只剩自己）', len(P.zones['receive']) == 1)
ok('PR-026 不動舉球區、攻擊區（仍為 3／3 張）', len(P.zones['toss']) == 3 and len(P.zones['attack']) == 3)
ok('PR-026 接球 3+4=7', sim2.cur_stat(P, T, 'receive') == 7)
P2 = sim2.Player([C('HV-P01-050')] * 5, rng, 'A'); P2.deck = [C('HV-P01-050') for _ in range(10)]
P2.zones['receive'] = [C('HV-P01-050')] * 5; P2.zones['toss'] = [C('HV-P01-046')] * 3; P2.zones['attack'] = [C('HV-P01-049')] * 3
T2 = sim2.newT(opp, 5, 'attack')
sim2.enter(P2, T2, 'toss', C('HV-P01-045'), True)
ok('P01-045 付舉球區＋攻擊區合計 4 張', (len(P2.zones['toss']) - 1) + (len(P2.zones['attack']) - 1) == 3 + 2 - 4)
ok('P01-045 不動接球區（仍 5 張）', len(P2.zones['receive']) == 5)
P3 = sim2.Player([C('HV-P01-050')] * 5, rng, 'A'); P3.deck = [C('HV-P01-050') for _ in range(10)]
P3.zones['receive'] = [C('HV-P01-050')] * 8; P3.zones['toss'] = [C('HV-P01-046')] * 2; P3.zones['attack'] = [C('HV-P01-049')] * 1
T3 = sim2.newT(opp, 5, 'attack')
sim2.enter(P3, T3, 'toss', C('HV-P01-045'), True)
ok('舉球＋攻擊區 Guts 不夠 4 張時，接球區再多也不能拿來付 P01-045', sim2.cur_stat(P3, T3, 'toss') == 1 and len(P3.zones['receive']) == 8)
