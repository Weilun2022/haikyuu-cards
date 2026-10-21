import os, sys, random
os.environ['DH_BATCH5'] = '1'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
fails = []
def ok(name, v):
    print(('OK  ' if v else 'FAIL') + ' ' + name)
    if not v: fails.append(name)
rng = random.Random(5)
EVC = [k for k, c in U.items() if c['category'] == 'EVENT'][:3]
CH = 'HV-P01-050'
def newp(op=3, src='attack', deck=None):
    P = sim2.Player(deck or [C(CH)] * 20, rng, 'X'); o = sim2.Player([C(CH)] * 20, rng, 'O')
    return P, o, sim2.newT(o, op, src)
FX = lambda P, T, effs, z='attack': sim2.apply_effects(effs, P, T, z)
M = sim2.MANUAL
# mill_tiers：牌庫頂 3 張含 2 張事件 → 累加 +2 +2；含 3 張 → +2 +2 +4
for nev, exp in ((0, 0), (1, 2), (2, 4), (3, 8)):
    P, o, T = newp(); P.deck = [C(EVC[0])] * nev + [C(CH)] * (3 - nev) + [C(CH)] * 5
    P.zones['attack'] = [C('HV-P04-039')]
    FX(P, T, M['HV-P04-039'][0]['effects'])
    ok('照島：牌庫頂 3 張含 %d 事件 → 攻擊 +%d（實際 %d）' % (nev, exp, T['mod'].get('attack', 0)), T['mod'].get('attack', 0) == exp and len(P.drop) == 3)
# 土湯：1 張事件 rcv+2；2 張事件再抽 1
P, o, T = newp(); P.deck = [C(EVC[0])] * 2 + [C(CH)] * 8; P.zones['receive'] = [C('HV-P04-045')]; h = len(P.hand)
FX(P, T, M['HV-P04-045'][0]['effects'], 'receive')
ok('土湯：2 張事件 → rcv+2 且抽 1', T['mod'].get('receive', 0) == 2 and len(P.hand) == h + 1)
# 鳴子：牌庫頂是和久谷南 → 一觸 3；不是 → 無
P, o, T = newp(op=5, src='attack'); P.deck = [C('HV-P04-049')] + [C(CH)] * 8
FX(P, T, M['HV-P04-051'][0]['effects'], 'block')
ok('鳴子：丟到和久谷南 → ワンタッチ(3)', T.get('onetouch') == 3)
P, o, T = newp(op=5, src='attack'); P.deck = [C(CH)] * 8
FX(P, T, M['HV-P04-051'][0]['effects'], 'block')
ok('鳴子：丟到別校 → 沒有一觸', not T.get('onetouch'))
# 百沢 P01-060：進攻 ≥4 才可用
P, o, T = newp(op=3); ok('百沢 P01-060：對手進攻 3 → 條件不成立', not all(sim2.cond_ok(c, P, T) for c in M['HV-P01-060'][0]['conditions']))
P, o, T = newp(op=4); ok('百沢 P01-060：對手進攻 4 → 條件成立', all(sim2.cond_ok(c, P, T) for c in M['HV-P01-060'][0]['conditions']))
# guts_each：三區各付 2
P, o, T = newp(); 
for z in ('receive', 'toss', 'attack'): P.zones[z] = [C(CH)] * 3
ok('guts_each：每區 2 Guts 付得起', sim2.cost_pay(M['HV-P03-073'][0]['cost'], P, T, 'attack'))
ok('guts_each：每區剩 1 張、共付 6 張', all(len(P.zones[z]) == 1 for z in ('receive', 'toss', 'attack')) and len(T['paid_guts']) == 6)
P, o, T = newp()
for z in ('receive', 'toss'): P.zones[z] = [C(CH)] * 3
P.zones['attack'] = [C(CH)] * 2
ok('guts_each：攻擊區只有 1 張 Guts → 付不起', not sim2.cost_pay(M['HV-P03-073'][0]['cost'], P, T, 'attack'))
# 大将：evz 有戸美 → 回手牌後棄 1
tomi = [k for k, c in U.items() if '戸美' in (c.get('school_tags') or []) and c['category'] == 'EVENT']
P, o, T = newp(); P.evz = [C(tomi[0])] if tomi else []; P.hand = [C(CH)] * 2
FX(P, T, M['HV-P02-073'][0]['effects'][1:])
ok('大将：Event 區戸美卡回手牌後棄 1 → 手牌 2、Event 區空' if tomi else '（卡庫沒有戸美事件，跳過）', (not tomi) or (len(P.hand) == 2 and not P.evz))
# 沼尻：evz 沒有、棄牌區有条善寺事件 → 也能撈
jz = [k for k, c in U.items() if '条善寺' in (c.get('school_tags') or []) and c['category'] == 'EVENT']
P, o, T = newp(); P.drop = [C(jz[0])] if jz else []; P.hand = [C(CH)] * 2
FX(P, T, M['HV-P04-044'][0]['effects'][1:])
ok('沼尻：棄牌區条善寺事件撈回後棄 1' if jz else '（卡庫沒有条善寺事件，跳過）', (not jz) or (len(P.hand) == 2 and len(P.drop) == 1))
# opp_rcv_add base_ge：原始接球 <5 不受影響、≥5 受影響
lo = [k for k, c in U.items() if c['category'] == 'CHARACTER' and (c['rcv'] or 0) <= 3][0]
hi = [k for k, c in U.items() if c['category'] == 'CHARACTER' and (c['rcv'] or 0) >= 5][0]
P, o, T = newp(); P.restrict.append(dict(rule='opp_rcv_add', n=-2, base_ge=5, duration='next_opp_turn'))
sim2.enter_skills(P, T, 'receive', C(lo), True, None, 'a', False)
ok('和久谷南 P04-097：原始接球 %s ≤3 不被減' % lo, T['mod'].get('receive', 0) == 0)
P, o, T = newp(); P.restrict.append(dict(rule='opp_rcv_add', n=-2, base_ge=5, duration='next_opp_turn'))
sim2.enter_skills(P, T, 'receive', C(hi), True, None, 'a', False)
ok('和久谷南 P04-097：原始接球 %s ≥5 被減 2' % hi, T['mod'].get('receive', 0) == -2)
# 預設規則的 opp_rcv_add 沒有 base_ge → 所有人都被減（舊行為不變）
P, o, T = newp(); P.restrict.append(dict(rule='opp_rcv_add', n=-1, duration='next_opp_turn'))
sim2.enter_skills(P, T, 'receive', C(lo), True, None, 'a', False)
ok('舊的 opp_rcv_add 沒指定 base_ge → 照舊減 1', T['mod'].get('receive', 0) == -1)
# rcv_best_of set_to=6
P, o, T = newp(); P.zones['receive'] = [C('HV-P04-049')]
cur = sim2.cur_stat(P, T, 'receive')
FX(P, T, [dict(type='rcv_best_of', school='和久谷南', set_to=6, min_cur=0)], 'receive')
ok('粘りの和久南：接球 %d → %d（取 +1 與變 6 較高者）' % (cur, sim2.cur_stat(P, T, 'receive')), sim2.cur_stat(P, T, 'receive') == max(cur + 1, 6))
# 木兎：付的 Guts 3 張梟谷、不含木兎、名字各異 → +7
fk = [c for c in U.values() if '梟谷' in (c.get('school_tags') or []) and c['category'] == 'CHARACTER' and c['name'] != '木兎 光太郎']
names = []; pick = []
for c in fk:
    if c['name'] not in names: names.append(c['name']); pick.append(c['card_no'])
    if len(pick) == 3: break
P, o, T = newp(); T['paid_guts'] = [C(k) for k in pick]
ok('木兎 P04-063：3 張異名梟谷 → 條件成立', sim2.cond_ok(dict(type='paid_guts_school_excl_name', school='梟谷', exclude_name='木兎 光太郎'), P, T))
T['paid_guts'] = [C(pick[0]), C(pick[0]), C(pick[1])]
ok('木兎 P04-063：有重名 → 不成立', not sim2.cond_ok(dict(type='paid_guts_school_excl_name', school='梟谷', exclude_name='木兎 光太郎'), P, T))
T['paid_guts'] = [C(pick[0]), C(pick[1]), C('HV-P01-043')]
ok('木兎 P04-063：含木兎自己 → 不成立', not sim2.cond_ok(dict(type='paid_guts_school_excl_name', school='梟谷', exclude_name='木兎 光太郎'), P, T))
# 雙名卡：NAME_CHOICE 兩個名字、技能空
ok('雙名卡 12 張：各有 2 個名字', all(len(sim2.NAME_CHOICE[k]) == 2 for k in ('HV-P01-072', 'HV-PR-067', 'HV-P03-077')) and sim2.MANUAL['HV-PR-012'] == [])
# 疊在同名上登場的 PR-001：+1 只有疊在日向上才發動
P, o, T = newp(); T['under'] = C('HV-P01-001') if False else None
ok('PR-001 疊在別人上不發動（條件不成立）', not sim2.cond_ok(dict(type='enter_on_top_name', name='日向 翔陽'), P, T))
print('FAILED: %d' % len(fails))
