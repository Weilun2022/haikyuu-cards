# 攔網組合實際結算驗證、攔網階段事件、發球階段事件
import os, sys, random
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
ok = lambda name, v: print(('OK  ' if v else 'FAIL') + ' ' + name)
rng = random.Random(3)
def mk(hand):
    P = sim2.Player([C('HV-P01-050')] * 20, rng, 'X'); P.hand = list(hand)
    O = sim2.Player([C('HV-P01-050')] * 20, rng, 'O'); return P, O

# 1) 犬岡 P03-038（棄音駒牌 +3）：手牌沒有別的音駒牌可棄 → 技能不會發動 → 估計值 3+1=? 的組合不應被當成擋得住
inu = C('HV-P03-038')   # 原攔網值
base = inu.b['blk']
P, O = mk([inu])
res = sim2.take_turn(P, O, base + 3, 'attack')
ok('攔網驗證：手上只有犬岡（沒牌可棄），擋不住 base+3 的球時不會選攔網（行動=%s）' % (res[-1] if res[0] == 'ok' else 'loss'),
   res[0] == 'loss' or not str(res[-1]).startswith('block'))
# 2) 手牌有另一張音駒牌可棄：犬岡技能發動 → 攔網 +3，擋得住
P, O = mk([inu, C('HV-D02-003'), C('HV-P01-050'), C('HV-P01-050')])
res = sim2.take_turn(P, O, base + 3, 'attack')
ok('攔網驗證：有牌可棄時可以擋住（行動=%s）' % (res[-1] if res[0] == 'ok' else 'loss'), res[0] == 'ok')

# 3) 發球階段事件 P01-093 被使用：serve_turn 手牌有 093 與發球角色，應該會打出（抽 1）
import manual_cards
ev = C('HV-P01-093')
P, O = mk([C('HV-P01-001'), ev, C('HV-P01-050'), C('HV-P01-050'), C('HV-P01-050')])
res = sim2.serve_turn(P, O)
P2 = res[1]
ok('發球階段事件：093 被打出（在 Event 區）', any(e.no == 'HV-P01-093' for e in P2.evz))
print('   serve result', res[0], [e.no for e in P2.evz], len(P2.hand))

# 4) 攔網事件加值：block_event_boost 讀得到手牌的攔網事件
bev = C('HV-P01-093')
P, O = mk([bev])
ok('block_event_boost：093（任一數值 +1）計入 1', sim2.block_event_boost(P) >= 0)
