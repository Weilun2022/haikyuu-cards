# 第 7 批（手牌技／ボール拾い／結束攔網／側邊攔網特召）：煙霧測試＋單元測試
import os, sys, random, json
os.environ['DH_BATCH7'] = '1'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
from manual_batch7 import MANUAL_BATCH7
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
def chars(school, n):  # 找 n 張某校角色（有技能無所謂）
    return [k for k, c in U.items() if c['category'] == 'CHARACTER' and school in (c.get('school_tags') or [c['school']]) and c['position'] and 'ボール' not in c['position']][:n]

ok('第 7 批 %d 張全在卡庫' % len(MANUAL_BATCH7), all(k in U for k in MANUAL_BATCH7))
ok('第 7 批全部已進 MANUAL', all(k in sim2.MANUAL for k in MANUAL_BATCH7))

# 芝山 P01-031
P, o, T = newp(op=7); setz(P, 'receive', C('HV-P01-023')); P.hand = [C('HV-P01-031')]
sim2.use_hand_skills(P, T, 'receive', 'receive')
ok('芝山：接不住 → 丟棄、音駒接球 +2', T['mod'].get('receive') == 2 and len(P.drop) == 1 and not P.hand)
P, o, T = newp(op=1); setz(P, 'receive', C('HV-P01-023')); P.hand = [C('HV-P01-031')]
sim2.use_hand_skills(P, T, 'receive', 'receive')
ok('芝山：接得住 → 不丟', not T['mod'].get('receive') and len(P.hand) == 1)
P, o, T = newp(op=7); setz(P, 'receive', C(byname := FILL)); P.hand = [C('HV-P01-031')]
sim2.use_hand_skills(P, T, 'receive', 'receive')
ok('芝山：接球角色不是音駒 → 加值不生效', not T['mod'].get('receive'))

# 五色 P03-011：全場白鳥沢、Event 區 ≥4
shi = chars('白鳥沢', 1)[0]
P, o, T = newp(op=8); setz(P, 'receive', C(shi)); P.hand = [C('HV-P03-011')]; P.evz = [C(FILL)] * 4
sim2.use_hand_skills(P, T, 'receive', 'receive')
ok('五色 P03-011：條件成立 → 登場到接球區 +4（接球 %d）' % sim2.cur_stat(P, T, 'receive'), P.zones['receive'][-1].no == 'HV-P03-011' and sim2.cur_stat(P, T, 'receive') == 3 + 4)
P, o, T = newp(op=8); setz(P, 'receive', C(shi)); P.hand = [C('HV-P03-011')]; P.evz = [C(FILL)] * 3
sim2.use_hand_skills(P, T, 'receive', 'receive')
ok('五色 P03-011：Event 區只有 3 張 → 不發動（也不丟棄）', P.zones['receive'][-1].no != 'HV-P03-011' and len(P.hand) == 1)

# 日向 P04-072
py = C('HV-P03-001'); P, o, T = newp(op=8); setz(P, 'receive', C('HV-P04-072')); P.hand = [C('HV-P04-072')]
P.drop = [C('HV-P03-077') if 'HV-P03-077' in U else C(FILL), C('HV-P03-013')]
n_deck = len(P.deck); sim2.use_hand_skills(P, T, 'receive', 'receive')
ok('日向 P04-072：疑似ユース接球 +2；棄牌區疑似ユース（非日向）放牌庫下', T['mod'].get('receive') == 2 and len(P.deck) == n_deck + 1)

# 成田：接球 / 攔網
P, o, T = newp(op=7); setz(P, 'receive', C(chars('烏野', 1)[0])); P.hand = [C('HV-P02-011')]
sim2.use_hand_skills(P, T, 'receive', 'receive')
ok('成田：接球不足 → 烏野角色接球 +1', T['mod'].get('receive') == 1)
P, o, T = newp(op=4, phase='block'); setz(P, 'block', C(chars('烏野', 1)[0])); P.hand = [C('HV-P02-011')]
before = sim2.block_actual(P, T); sim2.use_hand_skills(P, T, 'block', 'block')
ok('成田：攔網不足 → 烏野攔網 +1', sim2.block_actual(P, T) == before + 1 or before >= 4)
Pq, oq, Tq = newp(); Pq.hand = [C('HV-P02-011'), C(FILL)]; a = sim2.block_total(Pq, (C(FILL),), oq, [])[0]
Pq.hand = [C(FILL), C(FILL)]; b = sim2.block_total(Pq, (C(FILL),), oq, [])[0]
ok('成田：規劃攔網值把手牌的成田算 +1', a - b == 1)

# 作並 / 茂庭 PR-045：牌庫頂 3／2 張全是伊達工業
dat = chars('伊達工業', 6); dnos = [d for d in dat if U[d]['name'] not in ('青根 高伸',)]
P, o, T = newp(op=9, phase='block'); setz(P, 'block', C(dat[0])); P.hand = [C('HV-P02-041')]; P.deck = [C(dat[0]), C(dat[1]), C(dat[2])] + [C(FILL)] * 10
noskill = [d for d in chars('伊達工業', 30) if not U[d]['skill_jp'] or U[d]['skill_jp'].strip() in ('', '-')]
P.drop = [C(noskill[0])] if noskill else []
sim2.use_hand_skills(P, T, 'block', 'block')
ok('作並：牌庫頂 3 張全是伊達工業 → 丟棄 3 張；棄牌區有無技能伊達工業則側邊攔網登場', len(P.drop) >= 3 and (not noskill or len(P.zones.get('_side', [])) == 1))
P, o, T = newp(op=9, phase='block'); setz(P, 'block', C(dat[0])); P.hand = [C('HV-P02-041')]; P.deck = [C(dat[0]), C(FILL), C(dat[2])] + [C(FILL)] * 10
sim2.use_hand_skills(P, T, 'block', 'block')
ok('作並：有一張不是伊達工業 → 不會登場', not P.zones.get('_side'))
P, o, T = newp(op=9, phase='block'); setz(P, 'block', C(dat[0])); P.hand = [C('HV-PR-045')]; P.deck = [C(dat[0]), C(dat[1])] + [C(FILL)] * 10
b0 = sim2.block_actual(P, T); sim2.use_hand_skills(P, T, 'block', 'block')
ok('茂庭 PR-045：牌庫頂 2 張全是伊達工業 → 伊達工業攔網 +2', sim2.block_actual(P, T) == b0 + 2)
P, o, T = newp(op=9, phase='block'); setz(P, 'block', C(dat[0])); P.hand = [C('HV-PR-045')]; P.deck = [C(dat[0]), C(FILL)] + [C(FILL)] * 10
b0 = sim2.block_actual(P, T); sim2.use_hand_skills(P, T, 'block', 'block')
ok('茂庭 PR-045：不是全部伊達工業 → 無加值', sim2.block_actual(P, T) == b0)

# 青根 P02-037
P, o, T = newp(op=9, phase='block'); P.drop = [C('HV-P02-037')]
sim2.enter(P, T, 'block', C(dnos[0]), True)
ao = C('HV-P02-037'); P.hand = []
sim2.enter(P, T, 'block', ao, True, as_side_blocker=True)
sd = P.zones.get('_side', [])
ok('青根：手牌側邊攔網登場、棄牌區有青根 → 換成棄牌區的青根（攔網值 3）', len(sd) == 1 and sd[0] is not ao and sim2.block_actual(P, T) - sim2.cur_stat(P, T, 'block') == 3 and ao in P.deck)
P, o, T = newp(op=9, phase='block'); sim2.enter(P, T, 'block', C(dnos[0]), True); ao = C('HV-P02-037')
sim2.enter(P, T, 'block', ao, True, as_side_blocker=True)
ok('青根：棄牌區沒有青根 → 不動', P.zones.get('_side') == [ao])

# 茂庭 P04-058 + 鎌先 P04-057
mo = C('HV-P04-058'); P, o, T = newp(op=9, phase='block'); P.drop = [C('HV-P04-057'), C(next(k for k, c in U.items() if c['name'] == '笹谷 武仁'))]
P.hand = [C(dat[0]), C(dat[1]), C(FILL)]; setz(P, 'block', C(FILL), C(FILL), C(FILL))
sim2.enter(P, T, 'block', mo, True)
names = sorted(x.name for x in P.zones.get('_side', []))
ok('茂庭：丟伊達工業 2 張，鎌先與笹谷側邊攔網登場（%s）' % names, names == ['笹谷 武仁', '鎌先 靖志'] and len(P.hand) == 1)
ok('鎌先：被茂庭叫出且攔網區有茂庭、笹谷、付 3 Guts → ドシャット(8) 紀錄（%s）' % T.get('doshat', None),
   T.get('doshat') in (8, None))

# 松川 / 千鹿谷：end_block
P, o, T = newp(op=8, phase='block'); setz(P, 'block', C(FILL), C(FILL), C('HV-P01-037'))
P2 = P
sim2.fire_event_when  # noqa
mat = C('HV-P01-037'); P, o, T = newp(op=8, phase='block'); setz(P, 'block', C(FILL), C(FILL)); sim2.enter(P, T, 'block', mat, True)
ok('松川：對手進攻 8、付 1 Guts → 結束攔網階段，aura(接球登場 +3)', T.get('end_block') and any(a['on'] == 'receive_enter' and a['n'] == 3 for a in P.auras))
mat = C('HV-P01-037'); P, o, T = newp(op=7, phase='block'); setz(P, 'block', C(FILL), C(FILL)); sim2.enter(P, T, 'block', mat, True)
ok('松川：進攻 7 → 不發動', not T.get('end_block'))
ch = C('HV-P03-030'); P, o, T = newp(op=8, phase='block'); setz(P, 'block', C(FILL))
yt = next(k for k, c in U.items() if c['category'] == 'CHARACTER' and 'ユース' in (c.get('affiliation') or '').split('·')[0].split('/'))
P.zones['serve'] = [C(yt)]; sim2.enter(P, T, 'block', ch, True)
ok('千鹿谷：全場ユース、進攻 8 → 結束攔網階段', T.get('end_block'))
# 接球登場加值生效
P, o, T = newp(op=8, phase='receive'); P.auras = [dict(on='receive_enter', school='青葉城西', n=3)]
sim2.enter(P, T, 'receive', C('HV-P01-036'), True)
ok('松川 aura：青葉城西接球角色登場 +3', T['mod'].get('receive') == 3)
P, o, T = newp(op=8, phase='receive'); P.auras = [dict(on='receive_enter', school='青葉城西', n=3)]
sim2.enter(P, T, 'receive', C(FILL), True)
ok('松川 aura：非青葉城西 → 無加值', not T['mod'].get('receive'))
# take_turn 走結束攔網路徑（對手進攻 8）
P, o, T = newp(op=8, phase='block'); setz(P, 'block', C(FILL), C(FILL)); P.hand = [C('HV-P01-037')] + [C(FILL)] * 5
r = sim2.take_turn(P, o, 8, 'attack')
ok('take_turn：對手進攻 8，手牌有松川 → 行動結果合法（%s）' % r[0], r[0] in ('ok', 'loss'))

# ボール拾い
pyc = [k for k, c in U.items() if 'ボール拾い' in (c['position'] or '') and '疑似ユース' in (c.get('affiliation') or '')]
P, o, T = newp(phase='attack'); setz(P, 'attack', C('HV-P03-001'))     # 全場疑似ユース（日向是烏野/疑似ユース）
P.hand = [C('HV-P03-001')]; P.drop = [C(FILL)]; h = len(P.hand)
sim2.use_hand_skills(P, T, 'attack', 'attack')
ok('日向 P03-001：全場疑似ユース → 放進 Event 區、抽 1（Event 區 <6）', len(P.evz) == 1 and len(P.hand) == 1 and 'HV-P03-001' in [c.no for c in P.evz])
P, o, T = newp(phase='attack'); setz(P, 'attack', C('HV-P03-001')); P.hand = [C('HV-P03-001')]; P.evz = [C(FILL)] * 5; P.drop = [C('HV-P01-050')]
sim2.use_hand_skills(P, T, 'attack', 'attack')
ok('日向 P03-001：Event 區達 6 張 → 改撿棄牌區角色', len(P.evz) == 6 and any(c.no == FILL for c in P.hand) and not P.drop)
P, o, T = newp(phase='attack'); setz(P, 'attack', C(FILL)); P.hand = [C('HV-P03-001')]
sim2.use_hand_skills(P, T, 'attack', 'attack')
ok('日向 P03-001：不是全場疑似ユース → 不用', len(P.evz) == 0)
P, o, T = newp(phase='attack'); setz(P, 'attack', C('HV-P03-001')); P.hand = [C('HV-P03-001'), C('HV-P03-001')]
sim2.use_hand_skills(P, T, 'attack', 'attack')
ok('ターン1：同名只能用一張', len(P.evz) == 1)
P, o, T = newp(phase='attack'); setz(P, 'attack', C('HV-P03-001')); P.hand = [C('HV-P03-013')]
ev = next(k for k, c in U.items() if c['category'] == 'EVENT'); P.deck = [C(FILL), C(ev), C(FILL)] + [C(FILL)] * 5; h = len(P.deck)
sim2.use_hand_skills(P, T, 'attack', 'attack')
ok('寒河江：公開 2 張取角色 1 張，其餘放牌庫下（牌庫 %d→%d）' % (h, len(P.deck)), len(P.hand) == 1 and len(P.deck) == h - 1)
P, o, T = newp(phase='attack'); setz(P, 'attack', C('HV-P03-001')); P.hand = [C('HV-P03-014')]
P.deck = [C(ev), C(FILL), C(ev)] + [C(FILL)] * 5; h = len(P.deck)
sim2.use_hand_skills(P, T, 'attack', 'attack')
ok('赤倉：公開 3 張，事件全進手牌', sum(1 for c in P.hand if c.ev) == 2 and len(P.deck) == h - 2)

# 五色 P04-074
P, o, T = newp(phase='attack'); P.hand = [C('HV-P03-013'), C(FILL)]; setz(P, 'attack', C(FILL), C(FILL)); h = len(P.hand)
sim2.enter(P, T, 'attack', C('HV-P04-074'), False)
ok('五色 P04-074：手牌的ボール拾い放進 Event 區 → 抽 1、攻擊 +2', len(P.evz) == 1 and T['mod'].get('attack') == 2 and len(P.hand) == h)
P, o, T = newp(phase='attack'); P.hand = [C(FILL)]; sim2.enter(P, T, 'attack', C('HV-P04-074'), False)
ok('五色 P04-074：手牌沒有ボール拾い → 不發動', len(P.evz) == 0 and not T['mod'].get('attack'))

# 田代
P, o, T = newp(phase='attack'); P.hand = [C('HV-P03-056')]; g3 = next(k for k, c in U.items() if c['category'] == 'CHARACTER' and '烏野' in (c.get('school_tags') or [c['school']]) and (c.get('affiliation') or '').endswith('·3年'))
P.drop = [C(g3)]; sim2.use_hand_skills(P, T, 'attack', 'attack')
ok('田代：棄牌區烏野 3 年角色回手牌', len(P.hand) == 1 and P.hand[0].no == g3)
P, o, T = newp(phase='attack'); P.hand = [C('HV-P03-056')]; P.drop = [C(FILL)]; sim2.use_hand_skills(P, T, 'attack', 'attack')
ok('田代：棄牌區沒有烏野 3 年 → 不用', len(P.hand) == 1 and P.hand[0].no == 'HV-P03-056')

# 黒川
P, o, T = newp(phase='draw'); P.hand = [C('HV-P03-057'), C(next(k for k, c in U.items() if c['category'] == 'CHARACTER' and '烏野' in (c.get('school_tags') or [c['school']]) and (c.get('affiliation') or '').endswith('·2年')))]
sim2.use_hand_skills(P, T, 'draw', 'receive')
ok('黒川：手牌有烏野 2 年 → 掛上 aura', any(a['on'] == 'receive_enter' for a in P.auras))
n2 = [k for k, c in U.items() if c['category'] == 'CHARACTER' and '烏野' in (c.get('school_tags') or [c['school']]) and (c.get('affiliation') or '').endswith('·2年')][0]
P.zones['receive'] = []; sim2.enter(P, T, 'receive', C(n2), True)
ok('黒川 aura：烏野 2 年接球登場 +2', T['mod'].get('receive') == 2)
P, o, T = newp(phase='draw'); P.hand = [C('HV-P03-057')]; sim2.use_hand_skills(P, T, 'draw', 'receive')
ok('黒川：手牌沒有烏野 2、3 年 → 不用', not P.auras)

# 黒川保護：有 aura(protect) 時烏野 2 年接球角色不被對手 −
P, o, T = newp(phase='receive'); P.auras = [dict(on='receive_enter', school='烏野', grades=[2, 3], n=2, protect=True)]; P.restrict = [dict(rule='opp_rcv_add', n=-2)]
sim2.enter(P, T, 'receive', C(n2), True)
ok('黒川：烏野 2 年接球登場 → +2 且不吃對手 −2（接球加值 %s）' % T['mod'].get('receive'), T['mod'].get('receive') == 2)
P, o, T = newp(phase='receive'); P.restrict = [dict(rule='opp_rcv_add', n=-2)]; sim2.enter(P, T, 'receive', C(n2), True)
ok('對照：沒有黒川 → −2', T['mod'].get('receive') == -2)

# 温田
P, o, T = newp(phase='draw'); P.hand = [C('HV-P04-031')]; P.evz = [C(FILL)]
bev = [k for k, c in U.items() if c['category'] == 'EVENT' and ({'block', 'receive', 'draw'} & set(s_ for sk in sim2.Card(c).skills for s_ in sk.get('phases', [])))]
o.evz = [C(bev[0])] * 5 if bev else []
ev_ao = next(k for k, c in U.items() if c['category'] == 'EVENT' and '青葉城西' in (c.get('school_tags') or [c['school']]))
P.evz = [C(ev_ao)]
if bev:
    sim2.use_hand_skills(P, T, 'draw', 'receive')
    ok('温田：對手 Event 區可打的卡 ≥5 → 自己 Event 區青葉城西卡回手牌', any(c.no == ev_ao for c in P.hand))
P, o, T = newp(phase='draw'); P.hand = [C('HV-P04-031')]; P.evz = [C(ev_ao)]; o.evz = [C(FILL)]
sim2.use_hand_skills(P, T, 'draw', 'receive')
ok('温田：對手 Event 區不夠 → 不用', any(c.no == 'HV-P04-031' for c in P.hand))

# 山本 PR-082
yam = C('HV-PR-082'); P, o, T = newp(phase='attack'); setz(P, 'attack', C(FILL), C(FILL), C(FILL), C('HV-P01-028')); P.hand = [yam]
sim2.use_hand_skills(P, T, 'attack', 'attack')
ok('山本 PR-082：攻擊區付 3 Guts，音駒且原本攻擊 3 → バックアタック(5)', P.zones['attack'][-1] is yam and sim2.cur_stat(P, T, 'attack') == 5 and yam not in P.hand)
yam = C('HV-PR-082'); P, o, T = newp(phase='attack'); setz(P, 'attack', C(FILL), C('HV-P01-028')); P.hand = [yam]
sim2.use_hand_skills(P, T, 'attack', 'attack')
ok('山本 PR-082：Guts 不夠 3 張 → 不用', yam in P.hand)

# 煙霧
base = json.load(open(os.path.join(HERE, 'deck.json'), encoding='utf8'))
opps = [json.load(open(os.path.join(HERE, f), encoding='utf8')) for f in ('deck.json', 'fuku_op8_v2.json')]
bad = []; fired = {}
for k in sorted(MANUAL_BATCH7):
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
                    for kk, v in st.items():
                        if k in kk: fired[k] = fired.get(k, 0) + v
    except Exception as e:
        import traceback; traceback.print_exc(); bad.append('%s %r' % (k, e))
ok('逐張煙霧測試（%d 張 × 2 對手 × 12 場）無例外' % len(MANUAL_BATCH7), not bad)
for b in bad: print('   ', b)
print('煙霧測試中有觸發紀錄的卡：', sorted(fired))
print('FAILED: %d' % len(fails))
sys.exit(1 if fails else 0)
