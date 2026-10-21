"""混校研究（DH_MIXED=1）：11 張草稿技能卡與新機制（別々の所屬、翻牌、ドシャット、ブロックアウト、星海棄 Event）。"""
import os, sys, random
os.environ.setdefault('DH_MIXED', '1')
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
ok = lambda name, v: print(('OK  ' if v else 'FAIL') + ' ' + name)
rng = random.Random(1)
FILL = 'HV-P02-022'  # 稲荷崎 治（無關緊要的填充角色，本身有技能但不會被這些測試觸發）
FILL2 = 'HV-P01-050'  # 梟谷 小見（無技能）


def pl(deck=None):
    return sim2.Player(deck or [C(FILL2)] * 10, rng, 'X')


def newp(op=3, src='attack', phase=None, opp=None):
    P = pl(); o = opp or pl(); T = sim2.newT(o, op, src)
    if phase: T['phase'] = phase
    return P, o, T


# ── 別々の所屬 ────────────────────────────────────────
P = pl()
P.zones['serve'] = [C('HV-P02-003')]      # 烏野
P.zones['receive'] = [C('HV-P04-075')]    # 烏野／ユース（可選ユース）
P.zones['toss'] = [C('HV-P03-042')]       # 稲荷崎
P.zones['attack'] = [C('HV-P01-050')]     # 梟谷
ok('別々の所屬：烏野、烏野／ユース、稲荷崎、梟谷 = 4（雙所屬卡選ユース）', sim2.distinct_affil(P) == 4)
P.zones['receive'] = [C('HV-P03-052')]    # 烏野
ok('別々の所屬：烏野、烏野、稲荷崎、梟谷 = 3', sim2.distinct_affil(P) == 3)
P.zones['receive'] = [C('HV-P03-018')]    # 白水館／疑似ユース
ok('別々の所屬：4 種學校、含雙所屬卡 = 4', sim2.distinct_affil(P) == 4)

# ── 星海 P01-066 ─────────────────────────────────────
def hoshiumi(opp_evz, guts=3, court=True):
    P, o, T = newp(phase='attack')
    o.evz = [C('HV-P02-087')] * opp_evz
    P.zones['serve'] = [C('HV-P02-003')]
    P.zones['receive'] = [C('HV-P04-075')]
    P.zones['toss'] = [C('HV-P03-042')]
    if not court: P.zones['serve'] = []
    P.zones['attack'] = [C(FILL2)] * guts
    sim2.enter(P, T, 'attack', C('HV-P01-066'), from_hand=True)
    o.restrict = []
    rest = sim2.apply_now(T['locks'], o)
    return P, o, T, rest

P, o, T, rest = hoshiumi(4)
ok('星海：4 個不同所屬、付 3 Guts、對手 Event 區 4 張 → 棄 2 張剩 2 張，攻擊 2+3+1=6（實得 %d）、對手剩 %d 張' % (
    sim2.cur_stat(P, T, 'attack'), len(o.evz)), sim2.cur_stat(P, T, 'attack') == 6 and len(o.evz) == 2 and len(P.zones['attack']) == 1)
P, o, T, rest = hoshiumi(5)
ok('星海：對手 Event 區 5 張 → 棄 2 張剩 3 張，只有 +3（實得 %d）' % sim2.cur_stat(P, T, 'attack'),
   sim2.cur_stat(P, T, 'attack') == 5 and len(o.evz) == 3)
P, o, T, rest = hoshiumi(0)
ok('星海：對手 Event 區 0 張 → 攻擊 2+3+1=6', sim2.cur_stat(P, T, 'attack') == 6)
P, o, T, rest = hoshiumi(4, guts=2)
ok('星海：Guts 只有 2（不夠付 3）→ 不發動，攻擊維持 2（實得 %d）' % sim2.cur_stat(P, T, 'attack'), sim2.cur_stat(P, T, 'attack') == 2)
P, o, T, rest = hoshiumi(4, court=False)  # 只有 3 個不同所屬（接球烏野／ユース、舉球稲荷崎、攻擊鴎台）
ok('星海：只有 3 個不同所屬、也不是全鴎台 → 不發動（實得 %d）' % sim2.cur_stat(P, T, 'attack'), sim2.cur_stat(P, T, 'attack') == 2)
P, o, T = newp(phase='attack'); P.zones['attack'] = [C(FILL2)] * 3
sim2.enter(P, T, 'attack', C('HV-P01-066'), from_hand=True)
ok('星海：場上只有星海自己（全部鴎台）→ 發動，攻擊 ≥5（實得 %d）' % sim2.cur_stat(P, T, 'attack'), sim2.cur_stat(P, T, 'attack') >= 5)

# ── 佐久早 P01-068 ───────────────────────────────────
def sakusa(hand_n, distinct=4):
    P, o, T = newp(phase='attack')
    P.zones['serve'] = [C('HV-P02-003')]; P.zones['receive'] = [C('HV-P04-075')]; P.zones['toss'] = [C('HV-P03-042')]
    if distinct < 4: P.zones['toss'] = [C('HV-P03-052')]; P.zones['receive'] = [C('HV-P02-003')]
    P.hand = [C(FILL2)] * hand_n
    sim2.enter(P, T, 'attack', C('HV-P01-068'), from_hand=True)
    return P, o, T

P, o, T = sakusa(3)
ok('佐久早：手牌 3 張、4 個不同所屬 → 攻擊 2+2=4、ブロックアウト(2)（實得 %d）' % sim2.cur_stat(P, T, 'attack'),
   sim2.cur_stat(P, T, 'attack') == 4 and any(l['rule'] == 'blockout' and l['n'] == 2 for l in T['locks']))
P, o, T = sakusa(4)
ok('佐久早：手牌 4 張 → 不發動', sim2.cur_stat(P, T, 'attack') == 2 and not T['locks'])
P, o, T = sakusa(2, distinct=3)
ok('佐久早：只有 3 個不同所屬 → 不發動', sim2.cur_stat(P, T, 'attack') == 2 and not T['locks'])
# ブロックアウト：對手不能出原本攔網值 ≤2 的攔網角色
P, o, T = sakusa(3)
o.restrict = [l for l in T['locks'] if l['rule'] == 'blockout']
ok('ブロックアウト：對手不能出原本攔網值 2 的月島、可以出攔網 3 的田中',
   not sim2.can_enter(o, 'block', C('HV-P02-003')) and sim2.can_enter(o, 'block', C('HV-P03-052')))

# ── 事件 P01-092 ─────────────────────────────────────
def ev092(top_no, court_nos):
    P, o, T = newp(op=7, phase='receive')
    for z, no in zip(('serve', 'receive', 'toss'), court_nos): P.zones[z] = [C(no)]
    P.deck = [C(FILL2), C(top_no)] + [C(FILL2)] * 5  # 第 1 張被抽走，翻開的是第 2 張
    P.hand = [C('HV-P01-092')]
    sim2.play_event(P, T, P.hand[0], 'receive')
    return P, o, T

P, o, T = ev092('HV-P03-042', ['HV-P02-003', 'HV-P01-050', 'HV-P03-052'])  # 翻到稲荷崎、場上沒有 → 成立
ok('092：翻到稲荷崎、場上沒有稲荷崎 → 接球 +2，抽 1，翻開的牌放牌庫底（接球 %d）' % sim2.cur_stat(P, T, 'receive'),
   sim2.cur_stat(P, T, 'receive') == 6 + 2 and len(P.hand) == 1 and P.deck[-1].no == 'HV-P03-042' and len(P.deck) == 6)
P, o, T = ev092('HV-P03-042', ['HV-P02-003', 'HV-P01-050', 'HV-P03-042'])  # 場上有稲荷崎 → 不成立
ok('092：場上有稲荷崎 → 只有 +1（接球 %d）' % sim2.cur_stat(P, T, 'receive'), sim2.cur_stat(P, T, 'receive') == 6 + 1)
P, o, T = ev092('HV-P01-093', ['HV-P02-003', 'HV-P01-050', 'HV-P03-052'])  # 翻到事件：QA 1243 成立
ok('092：翻到事件牌 → 一定成立 +2（QA 1243）', sim2.cur_stat(P, T, 'receive') == 6 + 2)
P, o, T = ev092('HV-P04-075', ['HV-P02-003', 'HV-P01-050', 'HV-P03-052'])  # 翻到烏野／ユース，場上有烏野 → 不成立
ok('092：翻到烏野／ユース、場上有烏野 → 有任一同所屬就不成立', sim2.cur_stat(P, T, 'receive') == 6 + 1)
P, o, T = ev092('HV-P03-042', ['HV-P02-003', 'HV-P01-050', 'HV-P03-052'])
P.hand.append(C('HV-P01-092')); n0 = len(P.hand); sim2.play_event(P, T, P.hand[-1], 'receive')
ok('092：每回合 1 次，同回合第 2 張不能用', len(P.hand) == n0)

# ── 事件 P01-093 ─────────────────────────────────────
def ev093(top_no, court_nos):
    P, o, T = newp(op=5, phase='attack')
    for z, no in zip(('toss', 'attack'), court_nos): P.zones[z] = [C(no)]
    P.deck = [C(FILL2), C(top_no)] + [C(FILL2)] * 5
    P.hand = [C('HV-P01-093')]
    sim2.play_event(P, T, P.hand[0], 'attack')
    return P, o, T

P, o, T = ev093('HV-P03-042', ['HV-P01-050', 'HV-P03-052'])
ok('093：翻到稲荷崎、場上沒有 → 攻擊 +1（實得 %d）、對手下回合不能打舉球／攻擊事件' % sim2.cur_stat(P, T, 'attack'),
   sim2.cur_stat(P, T, 'attack') == 3 + 1 and any(l['rule'] == 'no_toss_attack_events' for l in T['locks']))
o.restrict = list(T['locks'])
ev_atk = C('HV-PR-031'); ev_rcv = C('HV-P01-091')
ok('093 封鎖：對手不能打攻擊事件 PR-031，但可以打接球事件 P01-091',
   not sim2.event_playable(o, T, ev_atk) and sim2.event_playable(o, T, ev_rcv))
P, o, T = ev093('HV-P03-042', ['HV-P03-042', 'HV-P03-052'])
ok('093：場上有稲荷崎 → 只抽 1，沒有 +1 也沒有封鎖', sim2.cur_stat(P, T, 'attack') == 3 and not T['locks'])

# ── 金田一 D04-005：ドシャット(6) ───────────────────────
P, o, T = newp(op=2, src='attack', phase='block')
sim2.enter(P, T, 'block', C('HV-D04-005'), from_hand=True)
ok('金田一：對手進攻 2 → ドシャット(6)', T.get('doshat') == 6)
P, o, T = newp(op=3, src='attack', phase='block')
sim2.enter(P, T, 'block', C('HV-D04-005'), from_hand=True)
ok('金田一：對手進攻 3 → 不發動', T.get('doshat') is None)
# 實際回合：手上只有金田一和接不起 2 點球的角色 → 攔網成功，回給對手 6 點
P = pl(); o = pl()
P.hand = [C('HV-D04-005'), C(FILL2), C(FILL2)]  # 小見是 Li（不能攔網），而且兩張同名接不起來 → 只有金田一能擋
res = sim2.take_turn(P, o, 2, 'attack')
ok('金田一：take_turn 攔下 2 點球後回給對手 6 點（結果 %s）' % ((res[:1] + res[2:4]),), res[0] == 'ok' and res[2] == 6 and res[6].startswith('block'))

# ── 芝山 D02-009、国見 P02-058 ───────────────────────────
P, o, T = newp(op=5, phase='receive'); P.zones['receive'] = [C(FILL2)] * 2; P.deck = [C(FILL2)] * 5
sim2.enter(P, T, 'receive', C('HV-D02-009'), from_hand=True)
ok('芝山：付 2 Guts 抽 1', len(P.hand) == 1 and len(P.zones['receive']) == 1)
P, o, T = newp(op=5, phase='receive'); P.zones['receive'] = [C(FILL2)] * 2; P.deck = [C(FILL2)] * 5; P.hand = [C(FILL2)]
sim2.enter(P, T, 'receive', C('HV-P02-058'), from_hand=True)
ok('国見：付 2 Guts，手牌 1 張 → 抽到 3 張（實得 %d）' % len(P.hand), len(P.hand) == 3)
P, o, T = newp(op=5, phase='receive'); P.zones['receive'] = [C(FILL2)] * 2; P.deck = [C(FILL2)] * 5; P.hand = [C(FILL2)] * 4
sim2.enter(P, T, 'receive', C('HV-P02-058'), from_hand=True)
ok('国見：手牌已有 4 張 → 不抽也不棄（實得 %d）' % len(P.hand), len(P.hand) == 4)

# ── 白布 P03-069 ───────────────────────────────────────
P, o, T = newp(op=5, phase='toss'); P.zones['toss'] = [C(FILL2)] * 2; P.deck = [C(FILL2)] * 5
sim2.enter(P, T, 'toss', C('HV-P03-069'), from_hand=True)
ok('白布 P03-069：付 2 Guts，舉球 1+1=2、抽 1（實得 %d）' % sim2.cur_stat(P, T, 'toss'),
   sim2.cur_stat(P, T, 'toss') == 2 and len(P.hand) == 1)

# ── 田中 P03-052：發球 ───────────────────────────────────
P = pl(); o = pl(); P.deck = [C(FILL2)] * 5
P.hand = [C('HV-P03-052'), C(FILL2), C(FILL2)]
res = sim2.serve_turn(P, o)
P2 = res[1]
ok('田中：發球 0+5=5、手牌 1 張放牌庫底、抽 1（發球 %s、手牌 %d、牌庫 %d）' % (res[2], len(P2.hand), len(P2.deck)),
   res[2] == 5 and len(P2.hand) == 2 and len(P2.deck) == 5)

# ── 及川 P01-033 ────────────────────────────────────────
P, o, T = newp(op=3, phase='toss'); P.hand = [C('HV-P02-058')]; o.hand = [C(FILL2)] * 4
sim2.enter(P, T, 'toss', C('HV-P01-033'), from_hand=True)
ok('及川：棄青葉城西的牌 1 張，舉球 1+1=2；對手手牌 4 張 → 逼對手棄 1 張（舉球 %d）' % sim2.cur_stat(P, T, 'toss'),
   sim2.cur_stat(P, T, 'toss') == 2 and not P.hand and any(l['rule'] == 'drop_hand_card' for l in T['locks']))
rest = sim2.apply_now(T['locks'], o)
ok('及川：對手實際少 1 張手牌（%d 張）' % len(o.hand), len(o.hand) == 3)
P, o, T = newp(op=3, phase='toss'); P.hand = [C('HV-P02-058')]; o.hand = [C(FILL2)] * 3
sim2.enter(P, T, 'toss', C('HV-P01-033'), from_hand=True)
ok('及川：對手手牌只有 3 張 → 只有 +1，不逼棄牌', sim2.cur_stat(P, T, 'toss') == 2 and not T['locks'])
P, o, T = newp(op=3, phase='toss'); P.hand = [C(FILL2)]
sim2.enter(P, T, 'toss', C('HV-P01-033'), from_hand=True)
ok('及川：手牌沒有青葉城西的牌 → 不發動', sim2.cur_stat(P, T, 'toss') == 1 and len(P.hand) == 1)

# ── 牛島 P01-056 ────────────────────────────────────────
P, o, T = newp(op=3, phase='attack'); P.hand = [C('HV-P01-092'), C(FILL2)]; P.deck = [C(FILL2)] * 5
sim2.enter(P, T, 'attack', C('HV-P01-056'), from_hand=True)
ok('牛島：把事件放進 Event 區，抽 1，攻擊 2+2=4（實得 %d），事件在 Event 區 %d 張' % (sim2.cur_stat(P, T, 'attack'), len(P.evz)),
   sim2.cur_stat(P, T, 'attack') == 4 and len(P.evz) == 1 and len(P.hand) == 2)
P, o, T = newp(op=3, phase='attack'); P.hand = [C(FILL2)]
sim2.enter(P, T, 'attack', C('HV-P01-056'), from_hand=True)
ok('牛島：手牌沒有事件 → 不發動', sim2.cur_stat(P, T, 'attack') == 2)

# ── 整體：使用者的混校牌組可以對打完整場，沒有例外 ───────────────────
import json
L = lambda f: json.load(open(os.path.join(HERE, f), encoding='utf8'))
mixed = L('mixed_user.json')
n_events = sum(n for no, n in mixed.items() if U[no]['category'] == 'EVENT')
ok('混校牌組：40 張、事件 %d 張（≤8）' % n_events, sum(mixed.values()) == 40 and n_events <= 8)
for opp_f in ('deck.json', 'fuku_op8_v2.json', 'ina_v4b.json', 'shira_final.json', 'mixed_user.json'):
    try:
        r = sim2.match(U, mixed, L(opp_f), 20, seed=3)
        ok('混校牌組 vs %s：20 場打完（A 勝 %d）' % (opp_f, sum(1 for x in r if x['winner'] == 'A')), len(r) == 20)
    except Exception as e:
        ok('混校牌組 vs %s：例外 %r' % (opp_f, e), False)

# ── 混校卡池（optimize.pool_for）────────────────────────────
import optimize
p_w = optimize.pool_for(U, '*', True)
ok('卡池：全部學校＋無技能卡，含已啟用的草稿卡 P01-092、星海 P01-066', 'HV-P01-092' in p_w and 'HV-P01-066' in p_w)
p_k = optimize.pool_for(U, '梟谷')
p_k2 = optimize.pool_for(U, ['梟谷'])
ok('卡池：單校（字串）與單校清單相同；全部學校卡池更大', p_k == p_k2 and len(p_w) > len(p_k))
p_x = optimize.pool_for(U, '烏野', True)
ok('卡池：烏野＋他校無技能卡 包含小見 P01-050（梟谷無技能）', 'HV-P01-050' in p_x and 'HV-P01-050' not in optimize.pool_for(U, '烏野'))
import gen_variants
V = gen_variants.make(U, mixed, p_w)
bad = [n for n, v in V.items() if sum(1 for k2 in list(v['in']) if U[k2]['category'] == 'EVENT') + n_events
       - sum(1 for k2 in v['out'] if U[k2]['category'] == 'EVENT') > 8]
ok('變體產生器：%d 個方案，沒有事件超過 8 張' % len(V), len(V) > 1000 and not bad)
