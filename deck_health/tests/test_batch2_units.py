# 第 2 批新機制單元測試
import os, sys, random
os.environ['DH_BATCH2'] = '1'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
ok = lambda name, v: print(('OK  ' if v else 'FAIL') + ' ' + name)
rng = random.Random(1)
def newp(op=3, src='attack', phase=None):
    P = sim2.Player([C('HV-P01-050')] * 10, rng, 'X'); o = sim2.Player([C('HV-P01-050')] * 10, rng, 'O')
    T = sim2.newT(o, op, src)
    if phase: T['phase'] = phase
    return P, o, T
FX = lambda P, T, effs, z='attack': sim2.apply_effects(effs, P, T, z)

# 卡名各不相同的 Guts 2 張加入手牌（黒尾 P01-021）：Guts 有 夜久×2、孤爪 → 只能拿 2 種各 1 張
P, o, T = newp(); P.hand = []
P.zones['attack'] = [C('HV-P01-021'), C('HV-P02-062'), C('HV-P02-062'), C('HV-P01-018')][::-1]
FX(P, T, [dict(type='guts_to_hand_same_school', n=2, distinct=True)])
ok('distinct：手牌拿到 2 張、卡名不同', len(P.hand) == 2 and len({c.name for c in P.hand}) == 2)
P, o, T = newp(); P.hand = []
P.zones['attack'] = [C('HV-P01-021'), C('HV-P02-062'), C('HV-P02-062'), C('HV-P02-062')][::-1]
FX(P, T, [dict(type='guts_to_hand_same_school', n=2, distinct=True)])
ok('distinct：Guts 全同名 → 拿不到', len(P.hand) == 0)

# 接球二選一（P01-082）：接球 5 → 變 7（+2）；接球 3 → +1；接球 8 → +1（不降）
for base_no, want in (('HV-P02-062', None),):
    pass
P, o, T = newp(phase='receive'); P.zones['receive'] = [C('HV-P03-035')]  # 夜久：先看它原本接球值
b = P.zones['receive'][-1].b['rcv']
FX(P, T, [dict(type='rcv_best_of', school='音駒')], 'receive')
cur = sim2.cur_stat(P, T, 'receive')
ok('二選一：夜久接球 %d → %d（≥5 變 7，否則 +1）' % (b, cur), cur == (7 if b >= 5 and 7 - b > 1 else b + 1))

# 手白 P01-032：對手接球／舉球登場技能無效
P, o, T = newp(); P.restrict.append(dict(rule='nullify_receive_toss_skills', duration='next_opp_turn'))
P.zones['receive'] = [C('HV-P03-035')]
sim2.enter_skills(P, T, 'receive', C('HV-P03-035'), True, None, '夜久 衛輔', False)
ok('手白：接球區技能被無效（沒抽牌、沒加值）', T['mod'].get('receive', 0) == 0)

# 研磨 D02-001：對手攻擊角色登場 −2
P, o, T = newp(); P.restrict.append(dict(rule='opp_atk_add', n=-2, duration='next_opp_turn'))
P.zones['attack'] = [C('HV-P01-050')]
sim2.enter_skills(P, T, 'attack', C('HV-P01-050'), True, None, '小見', False)
ok('研磨：對手攻擊角色攻擊 −2', T['mod'].get('attack', 0) == -2)

# 音駒中名單：char_only 不拿事件
P, o, T = newp(); P.hand = []
P.deck = [C('HV-P01-082'), C('HV-P02-062'), C('HV-P01-050')] + P.deck
FX(P, T, [dict(type='look_top_take', who='self', n=3, school='音駒', char_only=True, max=1, rest='deck_bottom')])
ok('char_only：只拿角色卡（夜久）', len(P.hand) == 1 and not P.hand[0].ev)

# PR-014 名字二選一存在
ok('PR-014／PR-058／PR-062 有名字選項', all(len(sim2.NAME_CHOICE.get(k, [])) == 2 for k in ('HV-PR-014', 'HV-PR-058', 'HV-PR-062')))
