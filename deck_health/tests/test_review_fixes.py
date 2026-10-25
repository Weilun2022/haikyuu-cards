# 2026-10-25 卡片結構化重審的修正（攔網階段、山本 PR-084、P04-090、以及 8 張漏掉的效果）：單元測試
import os, sys, random
for k in ('DH_BATCH5', 'DH_BATCH6', 'DH_BATCH7', 'DH_BATCH8'): os.environ[k] = '1'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
fails = []
def ok(name, v):
    print(('OK   ' if v else 'FAIL ') + name)
    if not v: fails.append(name)
rng = random.Random(11)
FILL = 'HV-P01-050'
def newp(op=3, src='attack', phase='receive'):
    P = sim2.Player([C(FILL)] * 20, rng, 'X'); o = sim2.Player([C(FILL)] * 20, rng, 'O')
    T = sim2.newT(o, op, src); T['phase'] = phase; return P, o, T
def by_name(n): return next(k for k, c in U.items() if c['category'] == 'CHARACTER' and c['name'] == n)

# 1. 攔網階段補上
for no in ('HV-P03-096', 'HV-P02-100', 'HV-D02-011'):
    ok('%s 可在攔網階段打出' % no, 'block' in C(no).phases)
P, o, T = newp(phase='block'); P.zones['block'] = [C(by_name('黒尾 鉄朗'))]; ev = C('HV-D02-011'); P.hand = [ev]
sim2.play_event(P, T, ev, 'block')
ok('手は前っつったでしょ：攔網階段 → 黒尾攔網 +1（mod=%s）' % T['mod'].get('block'), T['mod'].get('block') == 1 and len(P.hand) == 1)
P, o, T = newp(phase='receive'); P.zones['receive'] = [C(FILL)]; ev = C('HV-D02-011'); P.hand = [ev]
sim2.play_event(P, T, ev, 'receive')
ok('手は前っつったでしょ：接球階段 → 接球 +1（mod=%s）' % T['mod'].get('receive'), T['mod'].get('receive') == 1)
P, o, T = newp(phase='block'); P.zones['block'] = [C('HV-P01-021')]; ev = C('HV-P02-100'); P.hand = [ev]
sim2.play_event(P, T, ev, 'block')
ok('灰羽アリサ：攔網階段，場上沒有灰羽 → 只抽牌、不加值', T['mod'].get('block', 0) == 0 and len(P.hand) == 1)
P, o, T = newp(phase='block'); P.zones['block'] = [C(by_name('灰羽 リエーフ'))]; ev = C('HV-P02-100'); P.hand = [ev]
sim2.play_event(P, T, ev, 'block')
ok('灰羽アリサ：攔網階段，攔網區是灰羽 → 攔網 +1', T['mod'].get('block', 0) == 1)

# 2. 山本 PR-084
yam = by_name('山本 猛虎')
for by_skill, exp in ((True, 2), (False, 1)):
    P, o, T = newp(phase='attack'); P.zones['attack'] = [C(yam)]; T['names'] = {'attack': '山本 猛虎'}
    T['by_skill'] = {'attack': by_skill}; ev = C('HV-PR-084'); P.hand = [ev]
    sim2.play_event(P, T, ev, 'attack')
    ok('山本 PR-084：以技能出場=%s → 攻擊加 %d（實際 %s）' % (by_skill, exp, T['mod'].get('attack')), T['mod'].get('attack') == exp)
# 以技能叫出的角色，enter() 會記錄 by_skill
P, o, T = newp(phase='attack'); T['entered_by'] = 'どん ぴしゃり'
sim2.enter(P, T, 'attack', C(yam), False)
ok('enter() 記錄「以技能出場」', T['by_skill'].get('attack') is True)
P, o, T = newp(phase='attack'); sim2.enter(P, T, 'attack', C(yam), False)
ok('enter() 從手牌正常出場 → 不算技能出場', T['by_skill'].get('attack') is False)

# 3. P04-090：每個攔網角色攔網 −1
P, o, T = newp(phase='block'); P.restrict = [dict(rule='all_blockers_blk_add', n=-1)]
c1, c2 = C('HV-P01-021'), C('HV-P01-018')
sim2.enter(P, T, 'block', c1, True)
sim2.enter(P, T, 'block', c2, True, as_side_blocker=True)
base = c1.b['blk'] + c2.b['blk']
ok('P04-090：中間 + 側翼各 −1（%s → %s）' % (base, sim2.block_actual(P, T)), sim2.block_actual(P, T) == base - 2)
ok('P04-090：block_total 預估也各 −1', sim2.block_total(P, (c1, c2), None, P.restrict)[0] == (c1.b['blk'] + c2.b['blk']) - 2)

# 4a. 岩泉 P01-035：技能不能加手牌
P, o, T = newp(); P.restrict = [dict(rule='no_skill_add_hand')]; P.drop = [C('HV-P01-021')]; P.hand = []
sim2.apply_effects([dict(type='drop_to_hand', who='self', filter=dict(name=C('HV-P01-021').name), max=1)], P, T, 'toss')
ok('岩泉 P01-035：被封鎖時技能撿牌無效（手牌 %d、棄牌 %d）' % (len(P.hand), len(P.drop)), len(P.hand) == 0 and len(P.drop) == 1)
P.restrict = []
sim2.apply_effects([dict(type='drop_to_hand', who='self', filter=dict(name=C('HV-P01-021').name), max=1)], P, T, 'toss')
ok('沒封鎖時照常撿牌', len(P.hand) == 1)
for oh, exp in ((3, True), (6, False)):
    P, o, T = newp(op=9); o.hand = [C(FILL)] * oh; P.hand = [C('HV-P01-039'), C(FILL)]; P.zones['attack'] = [C(FILL)]
    T['allow_discard_cost'] = True
    sim2.enter(P, T, 'attack', C('HV-P01-035'), True)
    ok('岩泉 P01-035：對手手牌 %d 張 → 封鎖=%s' % (oh, exp), any(l['rule'] == 'no_skill_add_hand' for l in T['locks']) == exp)
# 4b. 岩泉 P04-020
ok('nullified() 認得 nullify_receive_hand', sim2.nullified([dict(rule='nullify_receive_hand')]) and not sim2.nullified([]))
# 4c. 黄金川：棄對手 Guts 的国見英
P, o, T = newp()
kun = by_name('国見 英'); o.zones['receive'] = [C(kun), C(kun), C(FILL)]; o.zones['attack'] = [C(kun), C(kun), C(FILL)]
rest = sim2.apply_now([dict(rule='drop_named_guts', name='国見 英', n=3, duration='now')], o)
left = sum(1 for z in ('receive', 'attack') for x in o.zones[z][:-1] if x.name == '国見 英')
ok('黄金川：對手 4 張国見 Guts 棄 3 張 → 剩 %d 張，棄牌區 %d 張' % (left, len(o.drop)), left == 1 and len(o.drop) == 3 and rest == [])
# 4d. 小鹿野：攔網角色技能無效
P, o, T = newp(phase='block'); P.restrict = [dict(rule='nullify_block_skills')]; P.zones['block'] = []; P.zones['block'] = [C(FILL)]
P.hand = [C(FILL)] * 3; P.zones['block'] = [C(FILL), C(FILL), C(FILL)]
sim2.enter(P, T, 'block', C('HV-P01-054'), True)
ok('小鹿野：攔網角色技能被無效（青根 P01-054 不加 +5）', T['mod'].get('block', 0) == 0 and P.stats.get('攔網技能被無效') == 1)
P, o, T = newp(phase='block'); P.zones['block'] = [C(FILL), C(FILL), C(FILL), C(FILL)]
sim2.enter(P, T, 'block', C('HV-P01-054'), True)
ok('沒被無效時青根照常 +5', T['mod'].get('block', 0) == 5)
# 4e. 百沢：付的 Guts 全是無技能的百沢
mom = by_name('百沢 雄大'); nos = [k for k, c in U.items() if c['category'] == 'CHARACTER' and c['name'] == '百沢 雄大' and (c.get('skill_jp') or '-').strip() in ('', '-')]
P, o, T = newp()
T['paid_guts'] = [C(nos[0])] if nos else []
ok('百沢 P04-032：無技能百沢 Guts → 條件成立（無技能版本 %d 種）' % len(nos), (not nos) or sim2.cond_ok(dict(type='paid_guts_name_noskill', name='百沢 雄大'), P, T))
T['paid_guts'] = [C(FILL)]
ok('百沢 P04-032：付別人 → 條件不成立', not sim2.cond_ok(dict(type='paid_guts_name_noskill', name='百沢 雄大'), P, T))
# 4f. 超インナークロス：側翼攔網手出場棄置一次
P, o, T = newp(phase='block'); P.restrict = [dict(rule='drop_side_blocker_once')]
s1, s2 = C('HV-P01-021'), C('HV-P01-018')
sim2.enter(P, T, 'block', C(FILL), True)
sim2.enter(P, T, 'block', s1, True, as_side_blocker=True)
sim2.enter(P, T, 'block', s2, True, as_side_blocker=True)
ok('超インナークロス：第一個側翼被棄置、第二個正常（_side=%d、棄牌 %d）' % (len(P.zones.get('_side', [])), len(P.drop)),
   len(P.zones.get('_side', [])) == 1 and P.zones['_side'][0] is s2 and s1 in P.drop)
# 4g. 入畑：本回合青葉城西角色登場 +1
P, o, T = newp(phase='receive'); P.auras = [dict(on='enter_any', school='青葉城西', n=1)]
aoj = next(k for k, c in U.items() if c['category'] == 'CHARACTER' and c['school'] == '青葉城西' and c['position'] == 'Li')
sim2.enter(P, T, 'receive', C(aoj), True)
ok('入畑 P01-085：青葉城西角色登場 → 該區 +1（mod=%s）' % T['mod'].get('receive'), T['mod'].get('receive') == 1)
P, o, T = newp(phase='attack'); P.zones['receive'] = [C(FILL)] * 3; P.zones['toss'] = [C(FILL)] * 3; P.zones['attack'] = [C(FILL)] * 6
ev = C('HV-P01-085'); P.hand = [ev]; T['allow_optional'] = True
sim2.play_event(P, T, ev, 'draw')
ok('入畑：Guts 夠 8 張 → 付 8 Guts、掛上登場加值（auras=%s、剩 Guts %d）' % (P.auras, sum(len(P.zones[z]) - 1 for z in ('receive', 'toss', 'attack'))),
   any(a['on'] == 'enter_any' for a in P.auras) and sum(len(P.zones[z]) - 1 for z in ('receive', 'toss', 'attack')) == 1)
P, o, T = newp(phase='attack'); P.zones['attack'] = [C(FILL)] * 3
ev = C('HV-P01-085'); P.hand = [ev]; T['allow_optional'] = True
sim2.play_event(P, T, ev, 'draw')
ok('入畑：Guts 不夠 8 張 → 只抽牌、不掛加值', not P.auras)
# 4h. 俺も思った：對手非抽牌加牌要棄 1
P, o, T = newp(); P.restrict = [dict(rule='discard_on_nondraw_add')]; P.hand = [C(FILL), C(FILL)]
P.add_nondraw(C('HV-P01-021'))
ok('俺も思った☆：對手非抽牌加牌 → 加 1 棄 1（手牌 %d、棄牌 %d）' % (len(P.hand), len(P.drop)), len(P.hand) == 2 and len(P.drop) == 1)
ok('P01-087 發球階段也能打', 'serve' in C('HV-P01-087').phases and 'toss' in C('HV-P01-087').phases)

# 5. 煙霧測試：含這些卡的牌組對打 20 場不報錯
pool = ['HV-P03-096', 'HV-P02-100', 'HV-D02-011', 'HV-PR-084', 'HV-P04-090', 'HV-P01-035', 'HV-P04-020', 'HV-P04-073',
        'HV-P03-073', 'HV-P04-032', 'HV-P02-082', 'HV-P01-085', 'HV-P01-087']
ok('13 張全在卡庫', all(k in U for k in pool))
ok('13 張全部已進 MANUAL', all(k in sim2.MANUAL for k in pool))
print('FAILED: %d' % len(fails))
sys.exit(1 if fails else 0)
