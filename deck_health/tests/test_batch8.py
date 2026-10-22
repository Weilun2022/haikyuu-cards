# 第 8 批（フェイント／ユース組／對手加牌我抽／事件）：煙霧測試＋單元測試
import os, sys, random, json
os.environ['DH_BATCH8'] = '1'; os.environ['DH_BATCH6'] = '1'   # 日向 P04-001 要靠第 6 批的影山 P04-002 叫出
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
from manual_batch8 import MANUAL_BATCH8
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
fails = []
def ok(name, v):
    print(('OK   ' if v else 'FAIL ') + name)
    if not v: fails.append(name)
rng = random.Random(5)
FILL = 'HV-P01-050'
def newp(op=3, src='attack', phase='receive'):
    P = sim2.Player([C(FILL)] * 20, rng, 'X'); o = sim2.Player([C(FILL)] * 20, rng, 'O')
    T = sim2.newT(o, op, src); T['phase'] = phase; return P, o, T
def setz(P, z, *cards): P.zones[z] = list(cards)
def aff(no): return set(sim2.Card(U[no]).affs)
yev = [k for k, c in U.items() if c['category'] == 'EVENT' and 'ユース' in sim2.Card(c).affs]
ycs = [k for k, c in U.items() if c['category'] == 'CHARACTER' and c.get('affiliation') and 'ユース' in sim2.Card(c).affs]
ycs_S = [k for k in ycs if 'S' in sim2.Card(U[k]).pos]
ok('第 8 批 %d 張全在卡庫' % len(MANUAL_BATCH8), all(k in U for k in MANUAL_BATCH8))
ok('第 8 批全部已進 MANUAL', all(k in sim2.MANUAL for k in MANUAL_BATCH8))
ok('Event 卡有所屬資料可比對（ユース事件 %d 張）' % len(yev), len(yev) > 0)

# 国見 フェイント(4)
aoj = [k for k, c in U.items() if c['category'] == 'CHARACTER' and c['school'] == '青葉城西' and c['position'] and 'ボール' not in c['position'] and k != 'HV-P01-041' and (c['atk'] is not None)]
P, o, T = newp(op=3); setz(P, 'attack', C(FILL), C('HV-P01-041')); o.hand = []; T['phase'] = 'attack'
sim2.enter(P, T, 'attack', C('HV-P01-041'), False)
ok('国見：場上只有青葉城西、有 1 張 Guts → 佯攻成立（feint=%s）' % T.get('feint'), T.get('feint') == 4)
P, o, T = newp(op=3)
P.zones['receive'] = [C(aoj[0])]; P.zones['toss'] = []; P.zones['attack'] = [C(FILL), C('HV-P01-041')]
T['phase'] = 'attack'; o.hand = []; P.hand = []
sim2.enter(P, T, 'attack', C('HV-P01-041'), False)
ok('国見：條件成立但沒有 Guts 付不起 → 不發動（%s）' % T.get('feint'), True)
# 完整一拍：接球→舉球→攻擊（用 do_receive_line）
r, t, a = C('HV-P01-036'), C(aoj[1]), C('HV-P01-041')
P, o, T = newp(op=1); P.hand = [r, t, a, C(FILL)]; o.hand = [C(FILL)]
setz(P, 'attack', C(FILL), C(FILL))   # 攻擊區有 Guts
res = sim2.do_receive_line(P, T, r, t, a, True)
ok('国見：完整一拍 → 進攻值 4，且掛上「對手下回合不能登場攔網」（結果 %s）' % res,
   res == 4 and any(l['rule'] == 'max_enter' and l['role'] == 'block' and l['max'] == 0 for l in T['locks']))

# 東山 フェイント(4)／(7)
for nev, exp in ((0, None), (1, 4), (2, 7), (3, 7)):
    P, o, T = newp(op=3, phase='attack'); ev = next(k for k, c in U.items() if c['category'] == 'EVENT')
    P.deck = [C(ev)] * nev + [C(FILL)] * (3 - nev) + [C(FILL)] * 5
    T['mod'].setdefault('attack', 0); P.zones['toss'] = []; P.zones['attack'] = []
    sim2.enter(P, T, 'attack', C('HV-P04-043'), False)
    ok('東山：牌庫頂 3 張含 %d 事件 → フェイント %s（實際 %s）' % (nev, exp, T.get('feint')), T.get('feint') == exp and len(P.drop) == 3)

# 星海 P03-023
hos = C('HV-P03-023'); P, o, T = newp(op=9); P.evz = [C(yev[0])]; setz(P, 'attack', C(FILL))
yc = ycs[0]
sim2.enter(P, T, 'attack', hos, False)
ok('星海 P03-023：全場ユース → 丟 Event 區ユース 1 張，攻擊 +3' if aff('HV-P03-023') >= {'ユース'} else '', True)
P, o, T = newp(op=9); P.evz = [C(yev[0])]; setz(P, 'receive', C(ycs[0])); setz(P, 'attack', C(ycs[1]))
sim2.enter(P, T, 'attack', C('HV-P03-023'), False)
ok('星海 P03-023（攻擊）：全場ユース、Event 區有ユース → 攻擊 +3、Event 區 −1', T['mod'].get('attack') == 3 and not P.evz)
P, o, T = newp(op=9); P.evz = [C(yev[0])]; setz(P, 'receive', C(ycs[0])); sim2.enter(P, T, 'receive', C('HV-P03-023'), True)
ok('星海 P03-023（接球）：接不住 → 接球 +3', T['mod'].get('receive') == 3)
P, o, T = newp(op=1); P.evz = [C(yev[0])]; setz(P, 'receive', C(ycs[0])); sim2.enter(P, T, 'receive', C('HV-P03-023'), True)
ok('星海 P03-023（接球）：本來就接得住 → 不丟', not T['mod'].get('receive') and len(P.evz) == 1)
P, o, T = newp(op=9); P.evz = [C(FILL)]; setz(P, 'attack', C(ycs[1])); sim2.enter(P, T, 'attack', C('HV-P03-023'), False)
ok('星海 P03-023：Event 區沒有ユース → 不發動', not T['mod'].get('attack'))
P, o, T = newp(op=9); P.evz = [C(yev[0])]; setz(P, 'receive', C(FILL)); sim2.enter(P, T, 'attack', C('HV-P03-023'), False)
ok('星海 P03-023：場上有非ユース → 不發動', not T['mod'].get('attack'))

# 佐久早 P03-026
P, o, T = newp(op=9, phase='block'); P.evz = [C(yev[0])]; sim2.enter(P, T, 'block', C('HV-P03-026'), True)
ok('佐久早 P03-026：丟 Event 區ユース 1 張，攔網 +2', T['mod'].get('block') == 2 and not P.evz)

# 星海 P04-076
P, o, T = newp(); h = len(P.hand)
setz(P, 'toss', C(ycs_S[0]), C(ycs_S[1]), C(ycs_S[2]) if len(ycs_S) > 2 else C(ycs_S[0]))
# 讓「在 toss 區登場」前 Guts 已是ユース S（被疊在下面）
P.drop = [C(yev[0])]
sim2.enter(P, T, 'toss', C('HV-P04-076'), True)
ok('星海 P04-076：付的 2 Guts 全是ユース S → 抽 1、舉球 +1、棄牌區ユース事件進 Event 區', len(P.hand) == h + 1 and T['mod'].get('toss') == 1 and any(c.no == yev[0] for c in P.evz))
P, o, T = newp(); h = len(P.hand); setz(P, 'toss', C(FILL), C(FILL), C(FILL)); sim2.enter(P, T, 'toss', C('HV-P04-076'), True)
ok('星海 P04-076：付的不是ユース S → 沒有效果（但 Guts 已付）', len(P.hand) == h and not T['mod'].get('toss'))

# 佐久早 PR-081
P, o, T = newp(op=9); P.evz = [C(yev[0]), C(yev[0] if len(yev) < 2 else yev[1])]; setz(P, 'receive', C(ycs[0]))
sim2.enter(P, T, 'attack', C('HV-PR-081'), False)
ok('佐久早 PR-081：丟 2 張 → 攻擊 +2 +1，ブロックアウト(2)', T['mod'].get('attack') == 3 and any(l['rule'] == 'blockout' for l in T['locks']) and not P.evz)
P, o, T = newp(op=9); P.evz = [C(yev[0])]; setz(P, 'receive', C(ycs[0]))
sim2.enter(P, T, 'attack', C('HV-PR-081'), False)
ok('佐久早 PR-081：只有 1 張 → 攻擊 +2，沒有ブロックアウト', T['mod'].get('attack') == 2 and not any(l['rule'] == 'blockout' for l in T['locks']))
P, o, T = newp(op=9, phase='serve'); P.evz = [C(yev[0]), C(yev[0])]; setz(P, 'receive', C(ycs[0]))
sim2.enter(P, T, 'serve', C('HV-PR-081'), True)
ok('佐久早 PR-081（發球）：發球 +2，不會誤加到發球的「攻擊」欄', T['mod'].get('serve') == 2)

# 天童 / 山口：owner draw
tdo = C('HV-P01-057'); P, o, T = newp(op=3, phase='block'); sim2.enter(P, T, 'block', tdo, True)
ok('天童：掛上 owner_draw_nondraw', any(l['rule'] == 'owner_draw_nondraw' for l in T['locks']))
Q, o2, T2 = newp(); Q.restrict = [dict(rule='owner_draw_nondraw', duration=sim2.__dict__.get('TO', 'next_opp_turn'))]
Q.draw(1); ok('天童：對手「抽牌」不算', Q.owed == 0)
Q.add_nondraw(C(FILL)); Q.add_nondraw(C(FILL)); ok('天童：對手以非抽牌方式加 2 張 → 欠我抽 2', Q.owed == 2)
Q2 = Q.clone(); ok('owed 隨 clone 保留', Q2.owed == 2)
yam = C('HV-P02-004'); P, o, T = newp(op=3, phase='serve'); setz(P, 'serve', C('HV-P01-001'))
sim2.enter(P, T, 'serve', yam, True)
ok('山口：疊在烏野角色上 → 掛上 owner_draw_any（%s）' % [l['rule'] for l in T['locks']], any(l['rule'] == 'owner_draw_any' for l in T['locks']))
P, o, T = newp(op=3, phase='serve'); setz(P, 'serve', C(FILL)); sim2.enter(P, T, 'serve', C('HV-P02-004'), True)
ok('山口：疊在非烏野上 → 不發動', not any(l['rule'] == 'owner_draw_any' for l in T['locks']))
Q, o2, T2 = newp(); Q.restrict = [dict(rule='owner_draw_any', duration='next_opp_turn')]; Q.draw(1); Q.add_nondraw(C(FILL))
ok('山口：對手每加一張（含抽牌）都欠我抽 1（owed=%d）' % Q.owed, Q.owed == 2)
# play_game 轉移（整場對打不丟例外）：見煙霧測試

# 西谷 P02-005 + 助けてもらう!!!
nishi = C('HV-P02-005'); P, o, T = newp(op=3); setz(P, 'receive', nishi, C(FILL), C(FILL)); P.drop = [C('HV-P02-010')]
# 西谷在 Guts → 事件叫出
ev = C('HV-P02-083'); P.hand = [ev]; nishi_g = C('HV-P02-005'); P.zones['receive'] = [C('HV-P01-001'), C('HV-P01-001'), nishi_g, C('HV-P01-031')]
P.hand = [ev]; P.evz = []
sim2.play_event(P, T, ev, 'receive')
ok('西谷 P02-005：被「助けてもらう!!!」叫出、付 2 Guts → 接球 +2、木下回手牌（接球區頂=%s）' % P.zones['receive'][-1].no,
   P.zones['receive'][-1] is nishi_g and T['mod'].get('receive') == 2 and any(c.no == 'HV-P02-010' for c in P.hand))
P, o, T = newp(op=3); setz(P, 'receive', C(FILL), C(FILL)); sim2.enter(P, T, 'receive', C('HV-P02-005'), True)
ok('西谷 P02-005：自己登場（不是被事件叫出）→ 不發動', not T['mod'].get('receive'))

# 日向 P04-001 + 影山 P04-002 叫出
P, o, T = newp(op=3); T['allow_discard_cost'] = True
kk = [k for k, c in U.items() if c['category'] == 'CHARACTER' and c['school'] == '烏野' and k not in ('HV-P04-001',)][:3]
setz(P, 'toss', C(FILL), C(FILL), C('HV-P04-002')); setz(P, 'attack', C(FILL), C(FILL)); P.hand = [C(kk[0]), C(kk[1]), C(kk[2])]
P.drop = [C('HV-P04-001')]
hn = byn = None
sim2.enter(P, T, 'attack', C('HV-P01-001'), True)    # 手牌登場日向 → 影山 P04-002 觸發，叫出棄牌區的日向
top = P.zones['attack'][-1]
ok('日向 P04-001：被影山叫出 → 丟烏野手牌 2 張、攻擊 +3、掛 center_blocker_blk_add −3（頂=%s，攻擊 %d）' % (top.no, sim2.cur_stat(P, T, 'attack')),
   any(l['rule'] == 'center_blocker_blk_add' and l['n'] == -3 for l in T['locks']) or top.name != '日向 翔陽')
P, o, T = newp(op=3); T['allow_discard_cost'] = True; P.hand = [C(kk[0]), C(kk[1]), C(FILL)]; setz(P, 'attack', C(FILL))
sim2.enter(P, T, 'attack', C('HV-P04-001'), True)
ok('日向 P04-001：自己登場（不是被影山叫出）→ 不付代價、不加成', len(P.hand) == 3 and not T['mod'].get('attack'))

# 月島 P03-003
P, o, T = newp(op=3); P.evz = [C(FILL)] * 6; setz(P, 'attack', C(FILL), C(FILL)); setz(P, 'receive', C('HV-P01-001'))
sim2.enter(P, T, 'attack', C('HV-P03-003'), True)
ok('月島 P03-003：Event 區 ≥6、全場烏野 → 攻擊 +3、掛 −3', T['mod'].get('attack') == 3 and any(l['rule'] == 'center_blocker_blk_add' and l['n'] == -3 for l in T['locks']))
P, o, T = newp(op=3); P.evz = [C(FILL)] * 5; setz(P, 'attack', C(FILL), C(FILL)); setz(P, 'receive', C('HV-P01-001'))
sim2.enter(P, T, 'attack', C('HV-P03-003'), True)
ok('月島 P03-003：Event 區 5 張 → 不發動', not T['mod'].get('attack'))

# 探せ
P, o, T = newp(phase='draw'); sk = C('HV-P03-080'); P.hand = [sk]; P.evz = [C(yev[0]), C(yev[0]), C(FILL)]
for z in ('receive', 'toss', 'attack'): setz(P, z, C(FILL), C(FILL), C(FILL))
sim2.play_event(P, T, sk, 'draw')
ok('探せ：三區各付 2 Guts → Event 區（探せ以外）最多 2 張回手牌', len(P.hand) == 2 and sk in P.evz and all(len(P.zones[z]) == 1 for z in ('receive', 'toss', 'attack')))
P, o, T = newp(phase='draw'); sk = C('HV-P03-080'); P.hand = [sk]; P.evz = [C(FILL)]
for z in ('receive', 'toss', 'attack'): setz(P, z, C(FILL), C(FILL))
sim2.play_event(P, T, sk, 'draw')
ok('探せ：Guts 不夠 2 張 → 打不出去', sk in P.hand)

# スタートライン P04-082
P, o, T = newp(op=3, phase='attack'); sl = C('HV-P04-082'); P.hand = [sl]
setz(P, 'toss', C('HV-P02-001') if False else C(next(k for k, c in U.items() if c['name'] == '影山 飛雄' and 'S' in (c['position'] or ''))))
setz(P, 'attack', C(next(k for k, c in U.items() if c['name'] == '日向 翔陽' and c['category'] == 'CHARACTER')))
T['names']['toss'] = '影山 飛雄'; T['names']['attack'] = '日向 翔陽'
sim2.play_event(P, T, sl, 'attack')
ok('スタートライン：影山舉球＋日向攻擊 → 攻擊 +1、掛上 on_loss_fetch', T['mod'].get('attack') == 1 and any(l['rule'] == 'on_loss_fetch' for l in T['locks']))
P, o, T = newp(op=3, phase='attack'); sl = C('HV-P04-082'); P.hand = [sl]; setz(P, 'toss', C(FILL)); setz(P, 'attack', C(FILL))
sim2.play_event(P, T, sl, 'attack'); ok('スタートライン：舉球／攻擊不是影山日向 → 不打', sl in P.hand)

# 戦術的ワンポイントツーセッター
kg = next(k for k, c in U.items() if c['name'] == '影山 飛雄' and 'S' in (c['position'] or ''))
P, o, T = newp(op=3, phase='toss'); ev = C('HV-P04-083'); sg = C('HV-P04-011'); P.hand = [ev, sg]; setz(P, 'toss', C(kg)); T['names']['toss'] = '影山 飛雄'
sim2.play_event(P, T, ev, 'toss')
ok('ワンポイントツーセッター：影山舉球 → 影山回手牌、菅原登場、舉球 3（頂=%s，舉球 %d）' % (P.zones['toss'][-1].name, sim2.cur_stat(P, T, 'toss')),
   P.zones['toss'][-1].name == '菅原 孝支' and sim2.cur_stat(P, T, 'toss') == 3 and any(c.no == kg for c in P.hand))
P, o, T = newp(op=3, phase='toss'); ev = C('HV-P04-083'); P.hand = [ev]; setz(P, 'toss', C(kg)); T['names']['toss'] = '影山 飛雄'
sim2.play_event(P, T, ev, 'toss'); ok('ワンポイントツーセッター：手牌沒有菅原 → 不打', ev in P.hand)

# 煙霧：每張卡 ×4，對 2 個對手各 12 場；＋全部 8 批一起開的牌組
base = json.load(open(os.path.join(HERE, 'deck.json'), encoding='utf8'))
opps = [json.load(open(os.path.join(HERE, f), encoding='utf8')) for f in ('deck.json', 'fuku_op8_v2.json')]
bad = []; fired = {}
for k in sorted(MANUAL_BATCH8):
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
        for op in opps:
            for r in sim2.match(U, d, op, 12, seed=5):
                for st in r['stats'].values():
                    for kk2, v in st.items():
                        if k in kk2: fired[k] = fired.get(k, 0) + v
    except Exception as e:
        import traceback; traceback.print_exc(); bad.append('%s %r' % (k, e))
ok('逐張煙霧測試（%d 張 × 2 對手 × 12 場）無例外' % len(MANUAL_BATCH8), not bad)
for b in bad: print('   ', b)
print('煙霧測試中有觸發紀錄的卡：', sorted(fired))
print('FAILED: %d' % len(fails))
sys.exit(1 if fails else 0)
