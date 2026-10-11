"""白鳥沢機制單元測試。用法：python -I tests/test_shira.py"""
import os, sys, random
os.environ['DH_SHIRA'] = '1'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sim2
from sim2 import Card, Player, newT, enter, cur_stat, can_enter, play_event, apply_now, draw_phase_events
U = sim2.load_cards(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'cards_data.js'))
C = lambda no: Card(U[no])
rng = random.Random(1)
FAIL = []
def ok(name, v):
    print(('OK  ' if v else 'FAIL') + ' ' + name)
    if not v: FAIL.append(name)
def player():
    P = Player([C('HV-P02-047')] * 10, rng, 'A'); P.deck = [C('HV-P02-047') for _ in range(10)]; return P

# Li：發球、攔網不能出
li = C('HV-P02-053')
ok('Li 不能發球、攔網', not can_enter(player(), 'serve', li) and not can_enter(player(), 'block', li))
ok('Li 可以接球', can_enter(player(), 'receive', li))

# 白布 P02-050：付 2 張 S Guts，舉球 1+2=3，搬 1 張白鳥沢 Guts 到攻擊區
opp = player(); P = player(); T = newT(opp, 5, 'attack')
P.zones['receive'] = [C('HV-P02-053')]
P.zones['block'] = [C('HV-P03-068'), C('HV-P02-049')]
P.zones['attack'] = [C('HV-P02-047')]
P.zones['toss'] = [C('HV-P03-068'), C('HV-P02-055'), C('HV-P02-050')]   # Guts：天童(MB)、瀬見(S)；最上面白布
enter(P, T, 'toss', C('HV-P02-050'), True)   # 疊上新的白布，Guts = 天童、瀬見、白布 → 優先付 2 張 S
ok('白布 舉球 3', cur_stat(P, T, 'toss') == 3)
ok('白布 付的是 S', all('S' in x.pos for x in T['paid_guts']))
ok('白布 搬 Guts 到攻擊區（攻擊區 1→2 張）', len(P.zones['attack']) == 2 and len(P.zones['block']) == 1)

# 牛島 P02-046：舉球白鳥沢 S，付 3 Guts，攻擊 2+3=5；棄對手接球區 Guts 2 張
P.zones['attack'] = [C('HV-P02-047')] * 3
enter(P, T, 'attack', C('HV-P02-046'), True)
ok('牛島 P02-046 攻擊 5', cur_stat(P, T, 'attack') == 5)
opp.zones['receive'] = [C('HV-P02-053')] * 4
rest = apply_now(T['locks'], opp)
ok('對手接球區 Guts 3→1', len(opp.zones['receive']) == 2 and not rest)
P2 = player(); T2 = newT(opp, 5, 'attack'); P2.zones['toss'] = [C('HV-P03-068')]; P2.zones['attack'] = [C('HV-P02-047')] * 3
enter(P2, T2, 'attack', C('HV-P02-046'), True)
ok('舉球是天童(MB) 不觸發', cur_stat(P2, T2, 'attack') == 2)

# 瀬見 P03-072：疊在白鳥沢上發球 6；對手 Li 接球 −1
P = player(); T = newT(opp, 0, None); P.zones['serve'] = [C('HV-P02-055')]
enter(P, T, 'serve', C('HV-P03-072'), True)
ok('瀬見 發球 6', cur_stat(P, T, 'serve') == 6)
O = player(); O.restrict = T['locks']; TO = newT(P, 6, 'serve')
enter(O, TO, 'receive', C('HV-P02-053'), True)
ok('對手 Li 接球 6−1=5', cur_stat(O, TO, 'receive') == 5)
P = player(); T = newT(opp, 0, None)
enter(P, T, 'serve', C('HV-P03-072'), True)
ok('發球區空的不觸發', cur_stat(P, T, 'serve') == 3)

# 鷲匠 P02-094：接球 5 → 抽 1、+1，不夠時棄無技能白鳥沢再 +2 = 8
P = player(); ev = C('HV-P02-094'); P.hand = [ev, C('HV-P02-047'), C('HV-P02-050')]
T = newT(opp, 8, 'attack'); T['phase'] = 'receive'
enter(P, T, 'receive', C('HV-P03-071'), True); play_event(P, T, ev, 'receive')
ok('鷲匠 接球 5+1+2=8', cur_stat(P, T, 'receive') == 8)
ok('鷲匠 棄的是無技能卡（白布留著）', any(c.no == 'HV-P02-050' for c in P.hand) and sum(c.no == 'HV-P02-047' for c in P.hand) == 1 and P.drop[-1].no == 'HV-P02-047')
P = player(); ev = C('HV-P02-094'); P.hand = [ev, C('HV-P02-047')]; T = newT(opp, 4, 'attack'); T['phase'] = 'receive'
enter(P, T, 'receive', C('HV-P03-071'), True); play_event(P, T, ev, 'receive')
ok('鷲匠 夠了就不棄', cur_stat(P, T, 'receive') == 6 and any(c.no == 'HV-P02-047' for c in P.hand))

# P02-096：舉球白布、攻擊牛島 P02-047（原本 3）→ 攻擊區 Guts 的牛島 P02-046 拉上場，觸發登場技能：2+3+1=6
P = player(); T = newT(opp, 5, 'attack'); T['phase'] = 'attack'; ev = C('HV-P02-096'); P.hand = [ev]
P.zones['toss'] = [C('HV-P02-050')]
P.zones['attack'] = [C('HV-P02-047'), C('HV-P02-047'), C('HV-P02-047'), C('HV-P02-046')]
enter(P, T, 'attack', C('HV-P02-047'), True)
play_event(P, T, ev, 'attack')
ok('P02-096 拉牛島 P02-046 攻擊 6', P.zones['attack'][-1].no == 'HV-P02-046' and cur_stat(P, T, 'attack') == 6)

# P02-097：攻擊角色牛島 → 對手下回合不能從手牌出 MB 攔網
P = player(); T = newT(opp, 5, 'attack'); T['phase'] = 'attack'; ev = C('HV-P02-097'); P.hand = [ev]
enter(P, T, 'attack', C('HV-P02-047'), True); play_event(P, T, ev, 'attack')
O = player(); O.restrict = T['locks']
ok('P02-097 擋 MB 攔網、不擋 S', not can_enter(O, 'block', C('HV-P03-068')) and can_enter(O, 'block', C('HV-P02-055')))
ok('P02-097 攻擊 3+1=4', cur_stat(P, T, 'attack') == 4)

# P03-090：Event 區有 P02-097 時拿回
P = player(); ev = C('HV-P03-090'); P.hand = [ev]; P.evz = [C('HV-P02-094'), C('HV-P02-097')]
draw_phase_events(P, opp, 5, 'attack')
ok('P03-090 拿回攻擊事件', any(c.no == 'HV-P02-097' for c in P.hand) and any(c.no == 'HV-P03-090' for c in P.evz))

# 山形 P03-071：Set 合計 ≤1、付 3 Guts → 接球 7，撈 3 年（不撈山形、白布）
P = player(); opp2 = player(); P.setz = [C('HV-P02-047')]; opp2.setz = []
P.drop = [C('HV-P02-053'), C('HV-P02-050'), C('HV-P02-055')]; P.zones['receive'] = [C('HV-P02-053')] * 3
T = newT(opp2, 7, 'attack'); enter(P, T, 'receive', C('HV-P03-071'), True)
ok('山形 接球 7', cur_stat(P, T, 'receive') == 7)
ok('山形 撈回瀬見（3 年）', [c.no for c in P.hand] == ['HV-P02-055'])

# 天童 P02-049：對手進攻 ≥4 一觸 2
P = player(); T = newT(opp, 4, 'attack'); enter(P, T, 'block', C('HV-P02-049'), True)
ok('天童 一觸 2', T.get('onetouch') == 2)
P = player(); T = newT(opp, 3, 'attack'); enter(P, T, 'block', C('HV-P02-049'), True)
ok('進攻 3 不觸發', not T.get('onetouch'))

print('FAILED:', FAIL if FAIL else 'none')
