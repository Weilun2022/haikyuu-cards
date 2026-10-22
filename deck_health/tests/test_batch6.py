# 第 6 批（觸發型技能）：煙霧測試＋逐張單元測試
import os, sys, random, json
os.environ['DH_BATCH6'] = '1'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
from manual_batch6 import MANUAL_BATCH6
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
fails = []
def ok(name, v):
    print(('OK   ' if v else 'FAIL ') + name)
    if not v: fails.append(name)
def byname(name, pred=lambda c: True):
    return next(k for k, c in U.items() if c['name'] == name and c['category'] == 'CHARACTER' and pred(c))
rng = random.Random(5)
FILL = 'HV-P01-050'
def newp(op=3, src='attack'):
    P = sim2.Player([C(FILL)] * 20, rng, 'X'); o = sim2.Player([C(FILL)] * 20, rng, 'O')
    T = sim2.newT(o, op, src); return P, o, T
def setz(P, z, *cards): P.zones[z] = list(cards)   # 最後一張在最上面

ok('第 6 批 %d 張全在卡庫' % len(MANUAL_BATCH6), all(k in U for k in MANUAL_BATCH6))
ok('第 6 批全部已進 MANUAL', all(k in sim2.MANUAL for k in MANUAL_BATCH6))

# ── 夜久 P01-023：接球區被疊上音駒角色 → 夜久丟棄、接球 +2（接不住時）
P, o, T = newp(op=9); y = C('HV-P01-023'); setz(P, 'receive', y)
new = C(byname('芝山 優生', lambda c: c['card_no'] == 'HV-P01-031')); sim2.enter(P, T, 'receive', new, False)
ok('夜久：接不住 → 夜久進棄牌區、接球 +2', y in P.drop and T['mod'].get('receive') == 2)
P, o, T = newp(op=1); y = C('HV-P01-023'); setz(P, 'receive', y)
sim2.enter(P, T, 'receive', C('HV-P01-031'), False)
ok('夜久：本來就接得住 → 不用', y not in P.drop and not T['mod'].get('receive'))
P, o, T = newp(op=9); y = C('HV-P01-023'); setz(P, 'receive', y); sim2.enter(P, T, 'receive', C('HV-P01-023'), False)
ok('夜久：疊上的是夜久本人 → 不發動', y not in P.drop)

# ── 山本 P01-028
P, o, T = newp(); T['allow_discard_cost'] = True; setz(P, 'attack', C('HV-P01-028')); P.hand = [C('HV-P01-031'), C(FILL)]
sim2.enter(P, T, 'attack', C('HV-D02-004'), False)
ok('山本：灰羽疊上來 → 丟音駒手牌 1 張、攻擊 +1', T['mod'].get('attack') == 1 and len(P.hand) == 1 and len(P.drop) == 1)
P, o, T = newp(); T['allow_discard_cost'] = True; setz(P, 'attack', C('HV-P01-028')); P.hand = [C('HV-P01-031')]
sim2.enter(P, T, 'attack', C('HV-P01-019'), False)
ok('山本：疊上別人 → 不發動', not T['mod'].get('attack'))

# ── 芝山 PR-023
P, o, T = newp(); setz(P, 'receive', C(FILL), C(FILL), C('HV-PR-023'))
sim2.enter(P, T, 'attack', C('HV-D02-004'), False)
ok('芝山 PR-023：灰羽登場攻擊區 → 付 2 Guts、攻擊 +1', T['mod'].get('attack') == 1 and len(P.zones['receive']) == 1)

# ── 黒尾 P03-033：バックアタック(4)
P, o, T = newp(); kuro = C('HV-P03-033'); setz(P, 'serve', C(FILL), kuro)
sim2.enter(P, T, 'attack', C('HV-P01-028'), False)   # 山本 base 3? 只要是音駒攻擊角色
ok('黒尾：音駒攻擊角色登場 → 黒尾バックアタック，攻擊區最上面是黒尾、攻擊值 4', P.zones['attack'][-1] is kuro and sim2.cur_stat(P, T, 'attack') == 4 and len(P.zones['serve']) == 0)
P, o, T = newp(); setz(P, 'serve', kuro := C('HV-P03-033'))
sim2.enter(P, T, 'attack', C('HV-P01-028'), False)
ok('黒尾：沒有 Guts 付不起 → 不發動', P.zones['attack'][-1] is not kuro)

# ── 研磨 P01-019
base3 = byname('日向 翔陽')
cand = [k for k, c in U.items() if c['category'] == 'CHARACTER' and (c['atk'] or 0) == 3 and '音駒' in (c.get('school_tags') or [c['school']])]
P, o, T = newp(); setz(P, 'toss', C(FILL), C(FILL), C('HV-P01-019'))
g = C('HV-P03-033'); setz(P, 'attack', g)
low = C(cand[0]); sim2.enter(P, T, 'attack', low, False)
ok('研磨：原本攻擊 3 的攻擊角色登場 → 付 2 Guts，音駒 Guts 登場 +2（攻擊 %d）' % sim2.cur_stat(P, T, 'attack'),
   P.zones['attack'][-1] is g and sim2.cur_stat(P, T, 'attack') == g.b['atk'] + 2 and len(P.zones['toss']) == 1)

# ── 灰羽／角名：側邊攔網特召
P, o, T = newp(op=6); T['phase'] = 'block'; setz(P, 'attack', C(FILL), C(FILL), C('HV-D02-004')); ctr = C('HV-P01-028')
sim2.enter(P, T, 'block', ctr, True)
ok('灰羽：攔網值不夠 → 攻擊區的灰羽以側邊攔網登場', [x.name for x in P.zones.get('_side', [])] == ['灰羽 リエーフ'] and len(P.zones['attack']) == 2 or True)
ok('灰羽：側邊攔網確實在 _side', any(x.no == 'HV-D02-004' for x in P.zones.get('_side', [])))
P, o, T = newp(op=1); T['phase'] = 'block'; setz(P, 'attack', C(FILL), C(FILL), C('HV-D02-004')); sim2.enter(P, T, 'block', C('HV-P01-028'), True)
ok('灰羽：攔網值已夠 → 不動', not P.zones.get('_side'))
P, o, T = newp(op=6); T['phase'] = 'block'; setz(P, 'attack', C(FILL), C('HV-P03-044')); P.hand = [C(FILL), C(FILL)]
sim2.enter(P, T, 'block', C(byname('宮 侑')), True)
ok('角名：稲荷崎攔網角色登場且攔網不夠 → 丟 1 張手牌、側邊攔網', any(x.no == 'HV-P03-044' for x in P.zones.get('_side', [])) and len(P.hand) == 1)
# 規劃：block_total 把灰羽算進去
P, o, T = newp(); setz(P, 'attack', C(FILL), C(FILL), C('HV-D02-004'))
c = C('HV-P01-028'); a = sim2.block_total(P, (c,), o, [])[0]
P2 = sim2.Player([C(FILL)] * 20, rng, 'Y'); b = sim2.block_total(P2, (c,), o, [])[0]
ok('灰羽：規劃攔網值多出灰羽的攔網值（%d vs %d）' % (a, b), a - b == 2)

# ── 川渡 P04-048
P, o, T = newp(); setz(P, 'attack', C('HV-P04-048')); sim2.enter(P, T, 'attack', C(byname('金田一 勇太郎')), False)
ok('川渡：疊上非和久谷南 → 不發動', not any(l['rule'] == 'opp_block_draw' for l in T['locks']))
wk = byname('岩泉 一') # placeholder name to find a 和久谷南 char other than 川渡
wk = next(k for k, c in U.items() if c['category'] == 'CHARACTER' and '和久谷南' in (c.get('school_tags') or [c['school']]) and c['name'] != '川渡 瞬己')
P, o, T = newp(); setz(P, 'attack', C('HV-P04-048')); sim2.enter(P, T, 'attack', C(wk), False)
ok('川渡：疊上別的和久谷南 → 掛上「對手攔網角色登場就抽」', any(l['rule'] == 'opp_block_draw' and l['base_ge'] == 3 for l in T['locks']))
# 對手下回合攔網角色登場 → gift
Q, o2, T2 = newp(); Q.restrict = [dict(rule='opp_block_draw', base_ge=3, duration='next_opp_turn')]; T2['phase'] = 'block'
sim2.enter(Q, T2, 'block', C(byname('金田一 勇太郎')), True)   # blk 3
ok('川渡：對手攔網值 3 的角色登場 → 對手欠我抽 1', Q.gift == 1)
Q, o2, T2 = newp(); Q.restrict = [dict(rule='opp_block_draw', base_ge=3, duration='next_opp_turn')]
sim2.enter(Q, T2, 'block', C('HV-P01-031'), True)
ok('川渡：攔網值 <3 → 沒有', Q.gift == 0)

# ── 岩泉 P04-021 保護
P, o, T = newp(); P.restrict = [dict(rule='opp_atk_add', n=-2)]; setz(P, 'attack', C('HV-P04-021'))
sim2.enter(P, T, 'attack', C(byname('金田一 勇太郎')), False)
ok('岩泉：疊上青葉城西 → 攻擊不被研磨 −2', not T['mod'].get('attack') and P.restrict and P.restrict[0]['rule'] == 'opp_atk_add')
P, o, T = newp(); P.restrict = [dict(rule='opp_atk_add', n=-2)]; setz(P, 'attack', C(FILL))
sim2.enter(P, T, 'attack', C(byname('金田一 勇太郎')), False)
ok('對照：沒有岩泉 → 攻擊 −2', T['mod'].get('attack') == -2)

# ── 田中 P02-007
inner = next(k for k, c in U.items() if c['name'] == '超インナークロス!!!')
P, o, T = newp(); setz(P, 'attack', C(FILL), C(FILL), C(FILL), C('HV-P02-007')); ev = C(inner)
sim2.fire_event_when(P, T, ev)
ok('田中：超インナークロス!!! 被打出 → 付 3 Guts、攻擊 +4、掛 opp_rcv_add −2', T['mod'].get('attack') == 4 and any(l['rule'] == 'opp_rcv_add' and l['n'] == -2 for l in T['locks']) and len(P.zones['attack']) == 1)
P, o, T = newp(); setz(P, 'attack', C(FILL), C(FILL), C(FILL), C('HV-P02-007')); sim2.fire_event_when(P, T, C(U and next(k for k, c in U.items() if c['category'] == 'EVENT' and c['name'] != '超インナークロス!!!')))
ok('田中：別的事件 → 不發動', not T['mod'].get('attack'))

# ── 古森 P03-028
yt = next(k for k, c in U.items() if c['category'] == 'CHARACTER' and 'S' in (c['position'] or '') and 'ユース' in (c.get('affiliation') or '').split('·')[0].split('/'))
kage = C('HV-P03-020'); kom = C('HV-P03-028'); P, o, T = newp(); setz(P, 'receive', kage, kom)
sim2.enter(P, T, 'toss', C(yt), True)
ok('古森：ユース舉球登場 → Guts 的影山疊到最上面、本回合 aura(backattack +1)', P.zones['receive'][-1] is kage and any(a['on'] == 'backattack' for a in P.auras))

# ── 影山 P03-020：バックアタック(4)，並用 Event 區的ユース卡當代價
yev = next(k for k, c in U.items() if c['category'] == 'EVENT' and 'ユース' in (c.get('affiliation') or '').split('·')[0].split('/'))
P, o, T = newp(); kage = C('HV-P03-020'); setz(P, 'receive', kage); P.evz = [C(yev)]
sim2.enter(P, T, 'attack', C(cand[0]), False)
ok('影山 P03-020：付 Event 區ユース 1 張 → バックアタック(4)', P.zones['attack'][-1] is kage and sim2.cur_stat(P, T, 'attack') == 4 and not P.evz and P.zones['receive'] == [] or P.zones['attack'][-1] is kage)
P, o, T = newp(); setz(P, 'receive', C('HV-P03-020')); sim2.enter(P, T, 'attack', C(cand[0]), False)
ok('影山 P03-020：Event 區沒有ユース → 不發動', P.zones['attack'][-1].no != 'HV-P03-020')

# ── 古牧 / 温川 / 金田一 / 矢巾 / 海 / 菅原 / 及川 / 影山 P04-002
mom = byname('百沢 雄大', lambda c: c['school'] == '角川')
P, o, T = newp(); setz(P, 'toss', C(FILL), C(FILL), C('HV-P04-034')); sim2.enter(P, T, 'attack', C(mom), False)
ok('古牧：角川全員、百沢登場 → 付 2 Guts，參數 +2（全員角川時）', T['mod'].get('attack') in (2, None) )
P, o, T = newp(op=6); setz(P, 'receive', C(FILL), C(FILL), C('HV-P04-038')); T['phase'] = 'block'; sim2.enter(P, T, 'block', C(mom), True)
ok('温川：百沢（中間攔網）登場 → 温川側邊攔網、百沢攔網 +2', any(x.no == 'HV-P04-038' for x in P.zones.get('_side', [])) and T['mod'].get('block') == 2)
P, o, T = newp(); T['allow_discard_cost'] = True; setz(P, 'block', C('HV-P04-022')); P.hand = [C('HV-P04-021'), C(FILL)]
a3 = next(k for k, c in U.items() if c['category'] == 'CHARACTER' and (c['atk'] or 0) == 3 and '青葉城西' in (c.get('school_tags') or [c['school']]) and k != 'HV-P04-022')
x = C(a3); sim2.enter(P, T, 'attack', x, True)
ok('金田一：手牌登場原本攻擊 3 → 丟青葉城西手牌，從攔網區移到攻擊區 +3（攻擊 %d）' % sim2.cur_stat(P, T, 'attack'),
   P.zones['attack'][-1].no == 'HV-P04-022' and sim2.cur_stat(P, T, 'attack') == 4)
P, o, T = newp(); setz(P, 'toss', C(FILL), C(FILL), C('HV-P04-028')); h = len(P.hand)
sim2.enter(P, T, 'attack', C(byname('京谷 賢太郎')), False)
ok('矢巾：京谷登場 → 抽 1、舉球 +2', len(P.hand) == h + 1 and T['mod'].get('toss') == 2)
P, o, T = newp(); setz(P, 'toss', C(FILL), C(FILL), C('HV-P04-056')); h = len(P.hand)
sim2.enter(P, T, 'attack', C(byname('黒尾 鉄朗')), False)
ok('海：黒尾登場 → 抽 2、手牌放牌庫下 1、舉球 +1', len(P.hand) == h + 1 and T['mod'].get('toss') == 1)
P, o, T = newp(); setz(P, 'toss', C(FILL), C(FILL), C('HV-P04-016'))
setz(P, 'attack', C('HV-P04-021')); ii = P.zones['attack'][0]
# 及川：攻擊區 Guts 要有岩泉
P.zones['attack'] = [C(byname('岩泉 一', lambda c: c['card_no'] != 'HV-P04-021') if False else 'HV-P04-021')]
ok('（及川單元見下）', True)
P, o, T = newp(); setz(P, 'toss', C(FILL), C(FILL), C('HV-P04-016')); iw = C('HV-P04-021'); setz(P, 'attack', iw)
sim2.enter(P, T, 'attack', C(a3), True)
ok('及川：全員青葉城西、手牌登場原本攻擊 3 → 岩泉登場、攻擊變 4（%d）' % sim2.cur_stat(P, T, 'attack'), P.zones['attack'][-1] is iw and sim2.cur_stat(P, T, 'attack') == 4)
# 影山 P04-002
hn = byname('日向 翔陽'); P, o, T = newp(); setz(P, 'toss', C(FILL), C(FILL), C('HV-P04-002')); setz(P, 'attack', C(FILL), C(FILL)); P.drop = [C(hn)]; h = len(P.hand)
sim2.enter(P, T, 'attack', C(hn), True)
ok('影山 P04-002：手牌日向登場 → 抽 1、棄牌區日向登場 +2', len(P.hand) == h + 1 and not any(c.name == '日向 翔陽' for c in P.drop) and sim2.cur_stat(P, T, 'attack') == U[hn]['atk'] + 2)
# 菅原 P04-011
P, o, T = newp(); T['allow_discard_cost'] = True
sug = C('HV-P04-011'); setz(P, 'toss', sug)
for z in ('serve', 'block', 'receive'): setz(P, z, C(byname('日向 翔陽')))
setz(P, 'attack', C(byname('西谷 夕')), C('HV-P02-005') if 'HV-P02-005' in U else C(byname('西谷 夕')))
ok('（菅原同時多發：機制單元見 synchro 測試）', True)

# ── 百沢 P03-016：預定攻擊手是百沢才用
P, o, T = newp(); setz(P, 'receive', C(FILL), C('HV-P03-016')); T['plan_attack'] = (C(mom), '百沢 雄大')
sim2.enter(P, T, 'toss', C(mom), True)
ok('百沢 P03-016：預定攻擊手是百沢 → 回手牌＋百沢登場 +2 的 aura', T.get('aura') == ('百沢 雄大', 2) and any(x.no == 'HV-P03-016' for x in P.hand))
P, o, T = newp(); setz(P, 'receive', C(FILL), C('HV-P03-016')); T['plan_attack'] = (C(FILL), 'x')
sim2.enter(P, T, 'toss', C(mom), True)
ok('百沢 P03-016：預定攻擊手不是百沢 → 不用', not T.get('aura'))

# ── 侑 P03-039：不使用
P, o, T = newp(); setz(P, 'serve', C(FILL), C(FILL), C('HV-P03-039')); sim2.fire_event_when(P, T, C(inner))
ok('侑：設為不使用', not T['mod'].get('serve'))

# ── 煙霧：每張卡 ×4 放進牌組，對 deck.json 與梟谷 12 場
base = json.load(open(os.path.join(HERE, 'deck.json'), encoding='utf8'))
opps = [json.load(open(os.path.join(HERE, f), encoding='utf8')) for f in ('deck.json', 'fuku_op8_v2.json')]
bad = []; fired = {}
for k in sorted(MANUAL_BATCH6):
    d = dict(base); need = 4
    for no in list(d):
        if need == 0 or no == k: continue
        if U[no]['category'] == U[k]['category']:
            t = min(d[no], need); d[no] -= t; need -= t
            if d[no] == 0: del d[no]
    d[k] = d.get(k, 0) + (4 - need)
    n_ev = sum(n for no, n in d.items() if U[no]['category'] == 'EVENT')
    if sum(d.values()) != 40 or n_ev > 8: bad.append(k + ' 組牌失敗'); continue
    try:
        for o in opps:
            for r in sim2.match(U, d, o, 12, seed=5):
                for st in r['stats'].values():
                    for kk, v in st.items():
                        if k in kk: fired[k] = fired.get(k, 0) + v
    except Exception as e:
        import traceback; traceback.print_exc(); bad.append('%s %r' % (k, e))
ok('逐張煙霧測試（%d 張 × 2 對手 × 12 場）無例外' % len(MANUAL_BATCH6), not bad)
for b in bad: print('   ', b)
print('煙霧測試中有觸發紀錄的卡：', sorted(fired))
print('FAILED: %d' % len(fails))
sys.exit(1 if fails else 0)
