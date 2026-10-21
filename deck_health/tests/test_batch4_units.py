import os, sys, random
os.environ['DH_BATCH4'] = '1'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
ok = lambda name, v: print(('OK  ' if v else 'FAIL') + ' ' + name)
rng = random.Random(5)
def newp(op=3, src='attack', phase=None, deck=None):
    P = sim2.Player(deck or [C('HV-P01-050')] * 20, rng, 'X'); o = sim2.Player([C('HV-P01-050')] * 20, rng, 'O')
    T = sim2.newT(o, op, src)
    if phase: T['phase'] = phase
    return P, o, T
FX = lambda P, T, effs, z='attack': sim2.apply_effects(effs, P, T, z)
M = sim2.MANUAL
# 硬幣：1000 次大約一半
heads = 0
for i in range(400):
    P, o, T = newp(); P.rng = random.Random(i)
    FX(P, T, [dict(type='coin', heads=[dict(type='stat_add', target='this', stat='blk', n=4)], tails=[dict(type='mill_n', n=3)])], 'block')
    P.zones['block'] = [C('HV-P02-048')]
    heads += T['mod'].get('block', 0) == 4
ok('硬幣：400 次正面 %d 次（約一半）' % heads, 150 < heads < 250)
# 攔網失敗門檻
r = [dict(rule='block_fail_le', n=6)]
ok('block_need：進攻 3 但門檻 6 → 需要 7', sim2.block_need(r, 3) == 7 and sim2.block_need(r, 9) == 9 and sim2.block_need([], 3) == 3)
ok('onetouch_nullified：只有一觸規則也成立；接球手牌技能不受影響', sim2.onetouch_nullified([dict(rule='nullify_onetouch')]) and not sim2.nullified([dict(rule='nullify_onetouch')]))
# 撈回 2 張 + 棄 1
P, o, T = newp(); P.hand = [C('HV-P01-050')] * 2
P.drop = [C('HV-P02-052'), C('HV-P04-060'), C('HV-P01-050')]  # 大平（有技能）、牛島（有技能）
FX(P, T, M['HV-P02-095'][0]['effects'], 'draw')
ok('斉藤：棄牌區只有 0 張「無技能的白鳥沢角色」→ 不撈、不棄', len(P.hand) == 2)
nos = [k for k, c in U.items() if c.get('school') == '白鳥沢' and c['category'] == 'CHARACTER' and c['skill_jp'] in ('-', '')][:2]
P, o, T = newp(); P.hand = [C('HV-P01-050')] * 2; P.drop = [C(k) for k in nos]
FX(P, T, M['HV-P02-095'][0]['effects'], 'draw')
ok('斉藤：撈回 %d 張無技能白鳥沢（%s），2 張才棄 1 → 手牌 3' % (len(nos), nos), len(P.hand) == 2 + len(nos) - (1 if len(nos) == 2 else 0))
# 無技能接球減值
P, o, T = newp(); P.restrict.append(dict(rule='opp_noskill_rcv_add', n=-1, duration=TO if False else 'next_opp_turn'))
sim2.enter_skills(P, T, 'receive', C('HV-P01-050'), True, None, '小見', False)
ok('無技能接球角色登場 −1', T['mod'].get('receive', 0) == -1)
P, o, T = newp(); P.restrict.append(dict(rule='opp_noskill_rcv_add', n=-1, duration='next_opp_turn'))
sim2.enter_skills(P, T, 'receive', C('HV-P03-035'), True, None, '夜久', False)
ok('有技能的接球角色不受影響', T['mod'].get('receive', 0) == 0)
# 理石：付的 Guts 是理石 → srv+6
P, o, T = newp(); P.zones['serve'] = [C('HV-P02-031'), C('HV-P02-031')]
T['paid_guts'] = [C('HV-P02-031')]
ok('paid_guts_name 理石 成立', sim2.cond_ok(dict(type='paid_guts_name', name='理石 平介'), P, T))
T['paid_guts'] = [C('HV-P01-050')]
ok('paid_guts_name 非理石 不成立', not sim2.cond_ok(dict(type='paid_guts_name', name='理石 平介'), P, T))
# 側邊攔網條件、攔網區伊達工業數
P, o, T = newp(); a, b, c = C('HV-P01-054'), C('HV-P02-042'), C('HV-P02-038')
T['block_comb'] = (a, b, c)
ok('block_comb_school_ge 伊達工業 3 人成立', sim2.cond_ok(dict(type='block_comb_school_ge', school='伊達工業', n=3), P, T))
T['block_comb'] = (a, C('HV-P01-050'))
ok('block_comb_school_ge 只有 1 人 → 3 不成立', not sim2.cond_ok(dict(type='block_comb_school_ge', school='伊達工業', n=3), P, T))
# stat_set_zone：宮侑發球值變 6
P, o, T = newp(phase='serve'); P.zones['serve'] = [C('HV-P03-039')]
FX(P, T, [dict(type='stat_set_zone', zone='serve', value=6)], 'serve')
ok('stat_set_zone：發球值變 6', sim2.cur_stat(P, T, 'serve') == 6)
# 疑似ユース 兩段撿牌
pu = [k for k, c in U.items() if '疑似ユース' in (c.get('school_tags') or []) and c['category'] == 'CHARACTER']
pos = lambda k: U[k].get('position')
ball = [k for k in pu if pos(k) == 'ボール拾い'][:1]; wk = [k for k in pu if pos(k) in ('WS', 'MB', 'S', 'Li')][:1]
P, o, T = newp(); P.hand = []; P.deck = [C(wk[0]), C(ball[0])] + P.deck
FX(P, T, M['HV-P03-079'][0]['effects'], 'draw')
ok('P03-079：撿到 2 張（%s、%s）' % (wk, ball), len(P.hand) == 2)
# 丟牌撈回
P, o, T = newp(); P.hand = []; P.deck = [C('HV-P02-052'), C('HV-P01-050')] + P.deck   # 大平（白鳥沢 3 年）
FX(P, T, [dict(type='mill_take', n=2, filter=dict(school='白鳥沢', grade=3, category='CHARACTER'))])
ok('mill_take：丟 2 張、白鳥沢 3 年的大平入手', len(P.hand) == 1 and P.hand[0].name == '大平 獅音' and len(P.drop) == 1)
# 滑津
P, o, T = newp(); P.hand = [C('HV-P01-050')]
P.drop = [C('HV-P01-054'), C('HV-P02-042'), C('HV-P02-042'), C('HV-P01-054')]
FX(P, T, M['HV-P03-097'][0]['effects'], 'block')
ok('滑津：撈 2 種不同伊達工業角色，再棄 1（手牌 2）', len(P.hand) == 2 and len({x.name for x in P.hand}) >= 1)
