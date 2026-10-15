"""一觸只能中間攔網用；多張一起攔網時不發動一觸（也不付代價）。【使用者 2026-10-15】"""
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
def fresh():
    P = sim2.Player([C('HV-P01-050')] * 5, rng, 'A'); P.deck = [C('HV-P01-050') for _ in range(10)]; return P
# 1. 單獨中間攔網：照常一觸
P = fresh(); T = sim2.newT(opp, 6, 'attack'); T['phase'] = 'block'
sim2.enter(P, T, 'block', C('HV-P01-051'), True)
ok('鷲尾單獨中間攔網 → 一觸 3、牌庫 −1', T.get('onetouch') == 3 and len(P.deck) == 9)
# 2. 側邊攔網：不能一觸，也不付代價
P = fresh(); T = sim2.newT(opp, 6, 'attack'); T['phase'] = 'block'
sim2.enter(P, T, 'block', C('HV-P01-051'), True, as_side_blocker=True)
ok('鷲尾當側邊攔網 → 不一觸、牌庫不動', not T.get('onetouch') and len(P.deck) == 10)
# 3. 多張一起攔網、鷲尾當中間：選擇不發動
P = fresh(); T = sim2.newT(opp, 6, 'attack'); T['phase'] = 'block'; T['decline_onetouch'] = True
sim2.enter(P, T, 'block', C('HV-P01-051'), True)
ok('多張攔網時鷲尾當中間 → 不一觸、牌庫不動', not T.get('onetouch') and len(P.deck) == 10)
# 4. 天童 P02-049 同規則
P = fresh(); T = sim2.newT(opp, 6, 'attack'); T['phase'] = 'block'
sim2.enter(P, T, 'block', C('HV-P02-049'), True, as_side_blocker=True)
ok('天童當側邊攔網 → 不一觸', not T.get('onetouch'))
