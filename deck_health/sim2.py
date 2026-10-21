"""雙人對打模擬器 v2：兩副牌依官方規則實際對打（総合ルール 5-2、5-3、規則表）。
- 每局第 1 回合：發球方只發球（不抽牌）
- 之後每回合：攔網（不抽、出 1～3 張不同名、合計 ≥ 進攻值，成功則回 0 點球）或接球（抽 1 → 接球 → 舉球 → 攻擊）
- LOSS → 局間：雙方補到 6 張，LOSS 方拿 1 張 Set 牌（沒有就輸掉比賽）；贏的一方下一局發球
技能由 manual_cards.MANUAL 驅動。出牌決策是啟發式（見 evaluate），雙方使用同一套決策。"""
import json, random, os, sys, itertools, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from manual_cards import MANUAL, NAME_CHOICE

CFG = dict(
    freeball_receive=True,     # 面對攔回來的 0 點球一律選接球（能接就接）【判斷】
    blocked_ball_src='block',  # 攔回來的球不算「發球」也不算「攻擊」（赤木、澤村條件不成立）【判斷】
    a_pass_as_toss=1,          # Aパス(1) 當作本回合舉球 +1【假設，待第 9 章】
    max_turns_per_set=80,
    fetch_then_attack=True,    # 赤葦 P01-045 撿回木兎後，同一拍可以拿來攻擊；付 Guts 時調成奇數（2026-10-11 修正）
    onetouch_attack_only=True, # 一觸只能減對手「攻擊」的進攻值，發球、攔網回來的球不行（所有卡通用）【使用者 2026-10-13】
    li_restrict=True,          # 數值為「-」的區域不能登場（Li 不能發球、攔網）【使用者 2026-10-11】
    hand_bottom_policy='default',  # 「手牌放牌庫底」代價（治 D03-002）的打法，只套用在 A 方：default／lethal（付了能讓對手接不起來才付）／never
                                   # ／smart（同拍會被どんぴしゃり叫出的治蓋掉就不付）／lethal_smart（兩個條件都要）
    verify_block=True,         # 攔網組合選好後，用登場技能實際結算的攔網值驗證（付不起代價、條件不成立的加值不算）
    w_cost=4.0, w_op=0.2,      # 評估權重：對手回應成本、送出的進攻值
)
ZSTAT = dict(serve='srv', block='blk', receive='rcv', toss='tos', attack='atk')


def load_cards(path):
    s = open(path, encoding='utf-8').read()
    d = json.loads(s[s.index('{'):s.rstrip().rstrip(';').rindex('}') + 1])
    u = {}
    for c in d['cards']:
        u.setdefault(c['card_no'], c)
    return u


class Card:
    __slots__ = ('no', 'name', 'ev', 'pos', 'school', 'b', 'skills', 'phases', 'alts', 'nozones', 'aff', 'noskill', 'affs')

    def __init__(self, raw):
        self.no = raw['card_no']; self.name = raw['name']; self.ev = raw['category'] == 'EVENT'
        self.pos = set(p.strip() for p in (raw['position'] or '').split(','))
        self.school = set(raw.get('school_tags') or [raw['school']])
        self.b = {k: (raw.get(k) or 0) for k in ('srv', 'blk', 'rcv', 'tos', 'atk')}
        self.skills = MANUAL.get(self.no, [])
        self.phases = set(p for s in self.skills for p in s.get('phases', [])) if self.ev else set()
        self.alts = NAME_CHOICE.get(self.no, [self.name])  # 雙名卡：出場時可選的名字
        self.nozones = {z for z, k in (('serve', 'srv'), ('block', 'blk'), ('receive', 'rcv'), ('toss', 'tos'), ('attack', 'atk'))
                        if raw.get(k) is None} if not self.ev else set()  # 數值為「-」的區域
        self.aff = raw.get('affiliation') or ''
        # 所屬（QA 1189／1817）：affiliation 欄位去掉學年後依「/」拆開；school_tags 會漏掉像「町内会」這種所屬，別々の所屬與翻牌比對改用這個
        self.affs = set(x for x in re.sub(r'[·・･]\d年$', '', self.aff).split('/') if x and x != '-')
        self.noskill = (raw.get('skill_jp') or '-').strip() in ('', '-')

    def __repr__(self): return self.no


def keep_value(c):
    if c.ev: return 4
    v = max(c.b['tos'] * 1.5, c.b['atk'], c.b['rcv'] * 0.8)
    for s in c.skills:
        z = s.get('zones', [])
        if 'toss' in z or 'attack' in z: v += 2.5
    return v


def hand_score(hand):
    ch = [c for c in hand if not c.ev]
    s = sum(keep_value(c) for c in hand) + 3 * len(hand)
    rc = sorted((c.b['rcv'] for c in ch), reverse=True)
    if rc and rc[0] >= 5: s += 8
    if len(rc) > 1 and rc[1] >= 5: s += 3
    if any(c.b['tos'] >= 1 for c in ch): s += 2
    if any(c.b['atk'] >= 3 for c in ch): s += 2
    return s


class Player:
    def __init__(self, cards, rng, label):
        self.rng = rng; self.label = label
        self.deck = cards[:]; rng.shuffle(self.deck)
        self.hand, self.drop, self.evz, self.setz = [], [], [], []
        self.zones = {z: [] for z in ZSTAT}
        self.pending_restrict, self.pending_trap = [], False   # 對手施加、在我下一回合生效
        self.restrict, self.trap = [], False                   # 本回合生效中
        self.stats = {}

    def bump(self, k, n=1): self.stats[k] = self.stats.get(k, 0) + n

    def draw(self, n=1):
        k = 0
        for _ in range(n):
            if self.deck: self.hand.append(self.deck.pop(0)); k += 1
        return k

    def add_nondraw(self, card):
        self.hand.append(card)
        if self.trap:  # 二口：對手下回合以抽牌以外方式加入手牌時，削牌庫頂 3 張
            for _ in range(3):
                if self.deck: self.drop.append(self.deck.pop(0))
            self.bump('被二口削牌')

    def guts(self, zone): return self.zones[zone][:-1]

    def pay_guts(self, zone, n):
        st = self.zones[zone]
        if len(st) - 1 < n: return False
        for _ in range(n): self.drop.append(st.pop(0))
        return True

    def clone(self):
        o = Player.__new__(Player)
        o.rng = self.rng; o.label = self.label
        o.deck = self.deck[:]; o.hand = self.hand[:]; o.drop = self.drop[:]; o.evz = self.evz[:]; o.setz = self.setz[:]
        o.zones = {k: v[:] for k, v in self.zones.items()}
        o.pending_restrict = self.pending_restrict[:]; o.pending_trap = self.pending_trap
        o.restrict = self.restrict[:]; o.trap = self.trap
        o.stats = dict(self.stats)
        return o


def newT(opp, op_in, src):
    return dict(opp=opp, op_in=op_in, src=src, mod={}, locks=[], trap=False, aura=None, set_toss=None,
                toss_cap=None, names={}, phase=None, allow_discard_cost=False, want_hinata=False, last_target_zone=None)


def cloneT(T):
    t = dict(T); t['mod'] = dict(T['mod']); t['locks'] = [dict(l) for l in T['locks']]; t['names'] = dict(T['names'])
    if 'negated' in T: t['negated'] = set(T['negated'])
    if 'captured' in T: t['captured'] = dict(T['captured'])
    return t


# ── 限制（對手施加在我身上的）────────────────────────────
def can_enter(P, zone, card, from_hand=True):
    if CFG['li_restrict'] and zone in card.nozones: return False
    for l in P.restrict:
        if (l['rule'] == 'cannot_enter_pos_from_hand' and from_hand and l['role'] == zone
                and l['position'] in card.pos): return False
        if l['rule'] == 'cannot_enter' and l['role'] == zone and card.b['rcv'] >= l['base_rcv_ge']: return False
        if l['rule'] == 'blockout' and zone == 'block' and card.b['blk'] <= l['n']: return False  # 佐久早 P01-068：出了原本攔網值 ≤N 的攔網角色就 LOSS，所以不會出
    return True


def max_blockers(restrict):
    m = 3
    for l in restrict:
        if l['rule'] in ('max_enter', 'max_block_from_hand') and l['role'] == 'block': m = min(m, l['max'])
    return m


def onetouch_nullified(restrict):  # 一觸無效：稲荷崎 P02-016（連同接球手牌技能）或 P03-092／伊達工業 P03-009（只有一觸）
    return any(l['rule'] in ('nullify_onetouch_and_receive_hand', 'nullify_onetouch') for l in restrict)


def block_need(restrict, op):  # 伊達工業 二口 P02-039：攔網值 ≤n 時攔網失敗 → 需要 n+1
    for l in restrict:
        if l['rule'] == 'block_fail_le': op = max(op, l['n'] + 1)
    return op


def nullified(restrict):  # 稲荷崎 P02-016：一觸與「接球階段・手牌」技能無效
    return any(l['rule'] == 'nullify_onetouch_and_receive_hand' for l in restrict)


def name_ok(T, zone, name):
    if zone == 'toss': return T['names'].get('receive') != name and T['names'].get('attack') != name
    if zone == 'attack': return T['names'].get('toss') != name
    if zone == 'receive': return T['names'].get('toss') != name
    return True


# ── 雙名卡（PR-013 木兎・赤葦、PR-062 灰羽・木兎）：出場時選名字，到回合結束有效 ──
ZPREF = dict(attack={'木兎 光太郎', '宮 治'}, toss={'赤葦 京治', '宮 侑'})  # 同樣合法時的偏好（PR-031 條件、木兎攻擊；稲荷崎雙子）


def alt_ok(T, zone, card): return any(name_ok(T, zone, n) for n in card.alts)


def choose_name(T, zone, card):
    ok = [n for n in card.alts if name_ok(T, zone, n)] or card.alts
    return min(ok, key=lambda n: n not in ZPREF.get(zone, ()))


def can_differ(x, y): return any(a != b for a in x.alts for b in y.alts)


def assign_distinct(cards):
    """同時登場（攔網）必須不同名：回傳每張卡的名字；做不到回傳 None。"""
    if all(len(c.alts) == 1 for c in cards):
        names = [c.name for c in cards]
        return names if len(set(names)) == len(names) else None
    for combo in itertools.product(*[c.alts for c in cards]):
        if len(set(combo)) == len(combo): return list(combo)
    return None


def line_names(r, t, a):
    """接球→舉球→攻擊三人的名字：接≠舉、舉≠攻（ABA 可以），依 ZPREF 偏好。"""
    best = None
    for nr in r.alts:
        for nt in t.alts:
            if nt == nr: continue
            for na in (a.alts if a is not None else [None]):
                if na is not None and na == nt: continue
                sc = (nt not in ZPREF['toss']) + (na is not None and na not in ZPREF['attack'])
                if best is None or sc < best[0]: best = (sc, (nr, nt, na))
    return best and best[1]


# ── 條件 / 代價 / 效果 ─────────────────────────────────
def cond_ok(c, P, T):
    t = c['type']; opp = T['opp']
    if t == 'set_total_le': return len(P.setz) + len(opp.setz) <= c['n']
    if t in ('opp_op_le', 'opp_op_ge'):
        if c['of'] != 'any':
            ok_src = dict(serve={'serve'}, attack={'attack'}, serve_or_attack={'serve', 'attack'})[c['of']]
            if T['src'] not in ok_src: return False
        return T['op_in'] <= c['n'] if t == 'opp_op_le' else T['op_in'] >= c['n']
    if t == 'opp_hand_le': return len(opp.hand) <= c['n']
    if t == 'self_is_role': return True
    if t == 'self_role_name':
        st = P.zones[c['role']]
        if not st: return False
        return T['names'].get(c['role'], st[-1].name) == c['name']  # 本回合登場的用選定名字
    if t == 'event_zone_count_le': return sum(1 for e in P.evz if e.name == c['card_name']) <= c['n']
    if t == 'event_zone_phase_count_ge':
        ph = set(c['phases']); ez = P.evz if c.get('who') == 'self' else opp.evz
        return sum(1 for e in ez if e.phases & ph and (not c.get('school') or c['school'] in e.school)) >= c['n']
    if t == 'entered_by': return T.get('entered_by') == c['card_name']
    if t == 'opp_event_count_ge': return len(opp.evz) >= c['n']  # 月島 P02-003
    if t == 'drop_distinct_names_ge':  # 侑 P02-017、角名 P02-027：棄牌區不同卡名的某校角色卡種類數
        return len({x.name for x in P.drop if not x.ev and c['school'] in x.school}) >= c['n']
    if t == 'self_role_name_in':
        st = P.zones[c['role']]
        return bool(st) and T['names'].get(c['role'], st[-1].name) in c['names']
    if t == 'entered_by_skill': return T.get('entered_by') is not None
    if t == 'self_hand_le': return len(P.hand) <= c['n']
    if t == 'captured_school':
        cap = T.get('captured', {}).get(c['key'])
        if cap is None or c['school'] not in cap.school: return False
        return c.get('category') != 'CHARACTER' or not cap.ev
    if t == 'entered_from_hand': return T.get('entering_from_hand', False)
    if t == 'event_zone_school_count_ge':  # 北 P04-070：自己 Event 區某校的牌 ≥n 張
        ez = P.evz if c.get('who', 'self') == 'self' else opp.evz
        return sum(1 for e in ez if c['school'] in e.school) >= c['n']
    if t == 'enter_on_top_name':  # 侑 P04-068：疊在某人名角色上登場
        u = T.get('under'); return u is not None and not u.ev and u.name == c['name']
    if t == 'all_own_chars_affil':  # 町内会 這類不在 school_tags 的所屬
        tops = [st[-1] for z, st in P.zones.items() if z in ZSTAT and st]
        return all(c['affil'] in x.affs for x in tops)
    if t == 'all_own_chars_school':
        tops = [st[-1] for z, st in P.zones.items() if z in ZSTAT and st]
        return all(c['school'] in x.school for x in tops)
    if t == 'zone_guts_odd': return (len(P.zones[c['zone']]) - 1) % 2 == 1
    if t == 'paid_guts_all_pos':
        pg = T.get('paid_guts') or []
        return bool(pg) and all(c['position'] in x.pos for x in pg)
    if t == 'enter_on_top_school':
        u = T.get('under'); return u is not None and c['school'] in u.school
    if t == 'self_role_school_pos':
        st = P.zones[c['role']]
        return bool(st) and c['school'] in st[-1].school and c['position'] in st[-1].pos
    if t == 'opp_role_base_le':  # P03-067：對手攻擊角色原本攻擊值 ≤n（只在對手這一拍是攻擊時）
        st = opp.zones[c['role']]
        return T['src'] == 'attack' and bool(st) and st[-1].b[c['stat']] <= c['n']
    if t == 'self_role_base':
        st = P.zones[c['role']]
        return bool(st) and st[-1].b[c['stat']] == c['n']
    if t == 'any_of': return any(cond_ok(x, P, T) for x in c['conds'])  # 星海 P01-066：「全部鴎台」或「別々の所屬 4 人以上」
    if t == 'opp_hand_ge': return len(opp.hand) >= c['n']  # 及川 P01-033
    if t == 'distinct_affil_ge': return distinct_affil(P) >= c['n']  # 星海 P01-066、佐久早 P01-068（QA 1189／1193）
    if t == 'court_has_name':  # 自分のコートに某人名的角色（山口 忠 等；用本回合登場時選定的名字）
        return any(T['names'].get(z, st[-1].name) == c['name'] for z, st in P.zones.items() if z in ZSTAT and st)
    if t == 'drop_has_name': return any(not x.ev and x.name == c['name'] for x in P.drop)
    if t == 'paid_guts_all_school':
        pg = T.get('paid_guts') or []
        return bool(pg) and all(c['school'] in x.school for x in pg)
    if t == 'paid_guts_school_excl_name':  # 木兎 P04-063：付的 Guts 全是某校、不含某人名、且卡名各不相同
        pg = T.get('paid_guts') or []
        return bool(pg) and all(c['school'] in x.school and x.name != c['exclude_name'] for x in pg) and len({x.name for x in pg}) == len(pg)
    if t == 'paid_guts_distinct_school':  # 縁下 P04-007：付的 Guts 全是某校、且卡名各不相同
        pg = T.get('paid_guts') or []
        return bool(pg) and all(c['school'] in x.school for x in pg) and len({x.name for x in pg}) == len(pg)
    if t == 'opp_court_has_grade':  # 對手場上有 N 年級的角色（所屬字串結尾「·2年」）
        return any(st and st[-1].aff.endswith('·%s年' % c['grade']) for z, st in opp.zones.items() if z in ZSTAT)
    if t == 'enter_on_top_school_pos':  # 西谷 P04-005：疊在烏野的 S 角色上登場
        u = T.get('under'); return u is not None and not u.ev and c['school'] in u.school and c['position'] in u.pos
    if t == 'event_zone_name_count_ge':
        ez = P.evz if c.get('who', 'self') == 'self' else opp.evz
        return sum(1 for e in ez if e.name == c['name']) >= c['n']
    if t == 'zone_stat_le': return cur_stat(P, T, c['zone']) <= c['n']
    if t == 'phase_is': return T.get('phase') == c['phase']
    if t == 'receive_below_op': return cur_stat(P, T, 'receive') < T['op_in']  # 策略：接不住才用手牌代價
    if t == 'allow_discard': return bool(T.get('allow_discard_cost'))  # 策略：攻擊階段（有打算進攻）才付手牌代價
    if t == 'guts_has_name': return any((not x.ev) and x.name == c['name'] for x in P.guts(c['zone']))
    if t == 'guts_pair_same_school':  # 策略：自己某一區的 Guts 有 n 張同所屬才打「がんばれ」
        for zz, st in P.zones.items():
            if zz not in ZSTAT: continue
            g = [x for x in st[:-1] if not x.ev]
            if any(sum(1 for x in g if sch in x.school) >= c['n'] for sch in {t2 for x in g for t2 in x.school}): return True
        return False
    if t == 'self_hand_ge': return len(P.hand) >= c['n']
    if t == 'paid_guts_name':  # 理石 P02-031：付出的 Guts 是某人名
        pg = T.get('paid_guts') or []
        return bool(pg) and all((not x.ev) and x.name == c['name'] for x in pg)
    if t == 'block_comb_school_ge':  # 伊達工業：攔網區（含側邊攔網）有 n 個某校角色
        comb = T.get('block_comb') or [x for z, st in P.zones.items() if z == 'block' for x in st[-1:]]
        return sum(1 for x in comb if c['school'] in x.school) >= c['n']
    if t == 'is_side_blocker': return bool(T.get('entering_side'))
    if t == 'zone_char':  # 某區最上面的角色符合 school／grade／name
        st = P.zones[c['zone']]
        return bool(st) and (not c.get('school') or c['school'] in st[-1].school) and (not c.get('grade') or st[-1].aff.endswith('·%s年' % c['grade']))
    if t == 'zone_stat_ge': return cur_stat(P, T, c['zone']) >= c['n']  # 岩泉 P04-020、P04-088：這區現在的數值 ≥n
    if t == 'evz_total_ge': return len(P.evz) >= c['n']  # 金田一 P03-005、国見 P03-007
    if t == 'self_set_fewer': return len(P.setz) < len(opp.setz)  # 岩泉 D04-002
    if t == 'evz_total_le': return len(P.evz) <= c['n']
    raise ValueError(t)


def distinct_affil(P):
    """自己場上（各區最上面的角色）可以選出幾人，使他們各取 1 個所屬後互不重複（QA 1189）。雙所屬卡可選其一。"""
    court = [st[-1].affs for z, st in P.zones.items() if z in ZSTAT and st]
    match = {}  # 所屬 → 佔用它的角色編號

    def aug(i, seen):
        for tag in court[i]:
            if tag in seen: continue
            seen.add(tag)
            if tag not in match or aug(match[tag], seen):
                match[tag] = i; return True
        return False
    return sum(1 for i in range(len(court)) if aug(i, set()))


def pick_discard(P, T):
    if T.get('want_hinata') and not any(c.name == '日向 翔陽' for c in P.drop):
        hs = [c for c in P.hand if c.name == '日向 翔陽']
        if hs: return max(hs, key=lambda c: c.b['atk'])
    return max(P.hand, key=lambda c: hand_score([x for x in P.hand if x is not c]))


def filt_ok(x, f):
    if f.get('category') == 'CHARACTER' and x.ev: return False
    if f.get('school') and f['school'] not in x.school: return False
    if f.get('no_skill') and not x.noskill: return False
    if f.get('affiliation') and f['affiliation'] not in x.aff.split('/'): return False
    if f.get('exclude_name') and x.name == f['exclude_name']: return False
    if f.get('grade') and not x.aff.endswith('·%s年' % f['grade']): return False
    if f.get('name') and x.name != f['name']: return False
    if f.get('positions') and not (x.pos & set(f['positions'])): return False
    return True


def cost_pay(costs, P, T, zone):
    for c in costs:
        t = c['type']
        if t == 'guts' and len(P.zones[c.get('zone', zone)]) - 1 < c['n']: return False
        if t == 'guts_multi' and sum(max(0, len(P.zones[z]) - 1) for z in c['zones']) < c['n']: return False
        if t == 'guts_each' and any(len(P.zones[z]) - 1 < c['n'] for z in c['zones']): return False
        if t == 'mill' and len(P.deck) < c.get('n', 1): return False
        if t in ('discard_hand', 'hand_to_deck_bottom') and len(P.hand) < c['n']: return False
        if t == 'event_hand_to_evz' and sum(1 for x in P.hand if x.ev and filt_ok(x, c.get('filter', {}))) < c['n']: return False
        if t == 'discard_hand_filtered' and sum(1 for x in P.hand if filt_ok(x, c['filter'])) < c['n']: return False
        if t == 'discard_named' and sum(1 for x in P.hand if x.name == c['name']) < c['n']: return False
        if t == 'discard_filtered' and sum(1 for x in P.hand if filt_ok(x, c['filter'])) < c['n']: return False
        if t == 'drop_block_char':
            st = P.zones['block']
            if not st or c['school'] not in st[-1].school: return False
    for c in costs:
        t = c['type']
        if t == 'guts':
            gz = c.get('zone', zone)  # 事件可指定從哪一區付（音駒 P01-081：接球區）
            st = P.zones[gz]
            T['paid_guts'] = st[:c['n']]  # 白布：依實際疊的順序付，不刻意挑 S（使用者 2026-10-12）
            P.pay_guts(gz, c['n'])
        elif t == 'discard_filtered':
            for _ in range(c['n']):
                w = min([x for x in P.hand if filt_ok(x, c['filter'])], key=keep_value); P.hand.remove(w); P.drop.append(w)
        elif t == 'guts_multi' and T.get('aim_odd_attack') and set(c['zones']) == {'toss', 'attack'}:
            # 赤葦 P01-045：調整從攻擊區付的張數，讓之後出場的木兎 P01-043 底下 Guts 為奇數
            L = len(P.zones['attack']); gt = max(0, len(P.zones['toss']) - 1); ga = max(0, L - 1)
            ks = [k for k in range(max(0, c['n'] - gt), min(c['n'], ga) + 1) if (L - k) % 2 == 1]
            k = min(ks) if ks else c['n'] - min(c['n'], gt)
            if ks: P.bump('調奇數')
            P.pay_guts('toss', c['n'] - k); P.pay_guts('attack', k)
        elif t == 'guts_each':  # 每個區各付 n 張（小鹿野 P03-073、沼尻 P04-044）
            pg = []
            for z in c['zones']:
                pg += P.zones[z][:c['n']]; P.pay_guts(z, c['n'])
            T['paid_guts'] = pg
        elif t == 'guts_multi':  # 跨區合計付 Guts：先付舉球區，再付攻擊區
            left = c['n']
            for z in c['zones']:
                k = min(left, max(0, len(P.zones[z]) - 1)); P.pay_guts(z, k); left -= k
        elif t == 'mill':
            for i in range(c.get('n', 1)):
                m = P.deck.pop(0); P.drop.append(m)
                if i == 0 and c.get('capture'): T.setdefault('captured', {})[c['capture']] = m
        elif t == 'discard_hand':
            for _ in range(c['n']):
                w = pick_discard(P, T); P.hand.remove(w); P.drop.append(w)
        elif t == 'event_hand_to_evz':  # 月島：手牌事件放進自己 Event 區（不是「打出」）
            for _ in range(c['n']):
                w = min([x for x in P.hand if x.ev and filt_ok(x, c.get('filter', {}))], key=keep_value); P.hand.remove(w); P.evz.append(w)
        elif t == 'discard_hand_filtered':  # 尾白：棄手牌中某校的牌
            for _ in range(c['n']):
                cands = [x for x in P.hand if filt_ok(x, c['filter'])]
                w = max(cands, key=lambda q: hand_score([x for x in P.hand if x is not q])); P.hand.remove(w); P.drop.append(w)
        elif t == 'tap': pass  # 角名：斜放，沒有其他影響（使用者 2026-10-16）
        elif t == 'hand_to_deck_bottom':
            for _ in range(c['n']):
                w = pick_discard(P, T); P.hand.remove(w); P.deck.append(w)
        elif t == 'discard_named':
            for _ in range(c['n']):
                w = min([x for x in P.hand if x.name == c['name']], key=keep_value); P.hand.remove(w); P.drop.append(w)
        elif t == 'drop_block_char':
            P.drop.append(P.zones['block'].pop())
    return True


def apply_effects(effs, P, T, zone):
    for e in effs:
        if e.get('if') and not all(cond_ok(c, P, T) for c in e['if']): continue
        t = e['type']
        if t == 'draw': P.draw(e['n'])
        elif t == 'discard_hand':
            for _ in range(min(e['n'], len(P.hand))):
                w = pick_discard(P, T); P.hand.remove(w); P.drop.append(w)
        elif t == 'stat_add':
            tg = e['target']
            if tg in ('this', 'that'): z = zone
            elif tg == 'same':
                z = T['last_target_zone']
                if z is None: continue  # 前面沒有選到角色 → 「さらに」的加值沒有對象
            elif e['stat'] == 'any' and T.get('phase') in ('serve', 'block'):  # 發球／攔網階段打的事件：任一數值 +1 → 加在該階段的區
                z = 'serve' if T['phase'] == 'serve' else 'block'
                if not P.zones[z] or (tg.get('school') and tg['school'] not in P.zones[z][-1].school): continue
            elif e['stat'] == 'any':  # どん ぴしゃり：任一數值 +1 → 加在攻擊或舉球（都算進攻值）
                z = next((z for z in ('attack', 'toss') if P.zones[z] and (not tg.get('school') or tg['school'] in P.zones[z][-1].school)), None)
                if z is None: continue
            elif e['stat'] == 'any_phase':  # 清水 P01-075 等：任一數值 +1 → 加在本階段有意義的區（接球階段加接球、舉球階段加舉球、攻擊階段加攻擊）
                order = dict(receive=('receive',), toss=('toss', 'attack'), attack=('attack', 'toss'),
                             serve=('serve',), block=('block',)).get(T.get('phase'), ('attack', 'toss'))
                z = next((z for z in order if P.zones[z] and (not tg.get('school') or tg['school'] in P.zones[z][-1].school)
                          and (not tg.get('grade') or P.zones[z][-1].aff.endswith('·%s年' % tg['grade']))
                          and (not tg.get('name') or T['names'].get(z, P.zones[z][-1].name) == tg['name'])), None)
                if z is None: continue
            else:
                z = dict(atk='attack', rcv='receive', tos='toss', blk='block', srv='serve')[e['stat']]
                st = P.zones[z]
                if not st or (tg.get('school') and tg['school'] not in st[-1].school): continue
                if tg.get('name') and T['names'].get(z, st[-1].name) != tg['name']: continue
                if tg.get('grade') and not st[-1].aff.endswith('·%s年' % tg['grade']): continue
                if tg.get('base_eq') is not None and st[-1].b[ZSTAT[z]] != tg['base_eq']: continue  # 追分 P02-090：攔網值剛好 3 的角色
            T['mod'][z] = T['mod'].get(z, 0) + e['n']; T['last_target_zone'] = z
        elif t == 'stat_set':
            st = P.zones['toss']
            if st and 'S' in st[-1].pos: T['set_toss'] = e['value']; T['mod']['toss'] = 0
        elif t == 'stat_cap': T['toss_cap'] = e['below'] - 1
        elif t == 'keyword':
            if e['name'] == 'Aパス': T['mod']['toss'] = T['mod'].get('toss', 0) + e['n']
            elif e['name'] == 'ワンタッチ':
                if not CFG['onetouch_attack_only'] or T['src'] == 'attack': T['onetouch'] = e['n']; P.bump('一觸')
            elif e['name'] == 'ツーアタック': T['two_attack'] = e['n']; P.bump('二段攻擊')
            elif e['name'] == 'ドシャット':
                if any(l['rule'] == 'nullify_doshat' for l in P.restrict): P.bump('ドシャット被無效')  # 東峰 P03-053
                else: T['doshat'] = e['n']; P.bump('ドシャット')  # 9-2：攔網成功的回合結束時，回給對手的進攻值變 N
            elif e['name'] == 'ブロックアウト':  # 9-5：對手下回合出原本攔網值 ≤N 的攔網角色就 LOSS
                T['locks'].append(dict(rule='blockout', n=e['n'], duration='next_opp_turn')); P.bump('ブロックアウト')
        elif t == 'mill':
            if P.deck and (not e.get('up_to') or T.get('allow_optional')):
                m = P.deck.pop(0); P.drop.append(m)
                if e.get('capture'): T.setdefault('captured', {})[e['capture']] = m
        elif t == 'optional':
            need_rcv = T.get('phase') == 'receive' and cur_stat(P, T, 'receive') < T['op_in']
            if (T.get('allow_optional') or need_rcv) and cost_pay(e.get('cost', []), P, T, zone):
                apply_effects(e['effects'], P, T, zone)
        elif t == 'optional_discard_else_zero':
            if len(P.hand) >= e['n']:
                for _ in range(e['n']):
                    w = pick_discard(P, T); P.hand.remove(w); P.drop.append(w)
                P.bump('棄2維持數值')
            else:
                T['zeroed'] = True
                st = P.zones.get(zone) or []
                if st: T['mod'][zone] = T['mod'].get(zone, 0) - st[-1].b[ZSTAT[zone]]
        elif t == 'opp_op_add':
            if T['src'] == 'attack': T['op_in'] += e['n']; P.bump('對手攻擊減值')
        elif t == 'reveal_top_take':
            if P.deck:
                top = P.deck.pop(0); P.bump('影山檢索')
                if top.name in e['names']: P.add_nondraw(top); P.bump('影山檢索命中')
                else: P.deck.append(top)
        elif t == 'aura_on_enter': T['aura'] = (e['name'], e['n'])
        elif t == 'drop_to_hand':
            f = e['filter']
            cands = [c for c in P.drop if (c.ev if f.get('category') == 'EVENT' else not c.ev) and filt_ok(c, f)]
            got = 0
            while cands and got < e.get('max', 1):
                best = max(cands, key=keep_value); cands.remove(best); P.drop.remove(best); P.add_nondraw(best); P.bump('棄牌區撈回'); got += 1
                if got == 1 and e.get('then'): apply_effects([e['then']], P, T, zone)
            T['took_n'] = got
        elif t == 'restrict_opp': T['locks'].append(dict(e)); P.bump('封鎖:' + e['rule'])
        elif t == 'on_opp_non_draw_add_mill': T['trap'] = True; P.bump('二口陷阱')
        elif t == 'no_stat_minus': pass  # P03-041：此回合數值不會被減（模擬中沒有對手在我方回合減攻擊值）
        elif t == 'drop_names_to_hand':  # P02-089：棄牌區各名字最多 1 張回手牌；全部拿到則棄 1
            got = 0
            for nm in e['names']:
                cands = [c for c in P.drop if not c.ev and c.name == nm]
                if cands:
                    b = max(cands, key=keep_value); P.drop.remove(b); P.add_nondraw(b); got += 1
            P.bump('P02-089撈回', got)
            if got == len(e['names']) and P.hand:
                w = pick_discard(P, T); P.hand.remove(w); P.drop.append(w)
        elif t == 'choose_one':  # P03-093：接球 +1 或 接球區 Guts 的北叫出（北比「現在 +1」高才叫）
            pick = 0
            for i, opt in enumerate(e['options']):
                o = opt[0]
                if o['type'] == 'guts_to_zone' and o['zone'] == 'receive':
                    g = [c for c in P.guts('receive') if not c.ev and c.name == o['filter']['name']
                         and can_enter(P, 'receive', c, from_hand=False)]
                    if g:
                        under = len(P.zones['receive']) - 1
                        T2 = dict(T); T2['allow_discard_cost'] = True
                        best = max(g, key=lambda c: pulled_value(P, T2, c, 'receive', under)[0])
                        if pulled_value(P, T2, best, 'receive', under)[0] > cur_stat(P, T, 'receive') + 1:
                            pick = i; e = dict(e); e['_best'] = best
            opt = e['options'][pick]
            if opt[0]['type'] == 'guts_to_zone':
                b = e['_best']; P.zones['receive'].remove(b)
                enter(P, T, 'receive', b, from_hand=False, name=b.name); P.bump('絶望叫出北')
            else:
                apply_effects(opt, P, T, zone)
        elif t == 'guts_to_zone' and e.get('filter', {}).get('name'):  # P02-096：攻擊區 Guts 的牛島拉上場（比現在強才拉）
            z = e['zone']
            g = [c for c in P.guts(z) if not c.ev and c.name == e['filter']['name'] and alt_ok(T, z, c)
                 and can_enter(P, z, c, from_hand=False)]
            if g:
                best = max(g, key=lambda c: summon_value(P, c, z) + 1)
                if summon_value(P, best, z) - 1 + 1 > cur_stat(P, T, z):
                    P.zones[z].remove(best); enter(P, T, z, best, from_hand=False); P.bump('Guts拉牛島')
                    if e.get('then'): apply_effects([e['then']], P, T, z)
        elif t == 'guts_to_zone':
            g = [c for c in P.guts(e['zone']) if not c.ev and (not e.get('filter') or e['filter'].get('position', '') in c.pos)
                 and alt_ok(T, e['zone'], c) and can_enter(P, e['zone'], c, from_hand=False)]
            if g:
                best = max(g, key=lambda c: c.b[ZSTAT[e['zone']]])
                P.zones[e['zone']].remove(best); enter(P, T, e['zone'], best, from_hand=False); P.bump('Guts拉上場')
        elif t == 'event_to_hand' and 'name' in e['filter']:  # 侑 D03-001：Event 區指定卡名 1 張回手牌，有拿就手牌 1 張放牌庫底
            cands = [c for c in P.evz if c.name == e['filter']['name']]
            if cands:
                P.evz.remove(cands[0]); P.add_nondraw(cands[0]); P.bump('撈回:' + e['filter']['name'])
                T['_keep'] = cands[0]  # 剛撈回的牌不放回牌庫底
                if e.get('then'): apply_effects([e['then']], P, T, zone)
                T['_keep'] = None
        elif t == 'hand_to_deck_bottom':  # 放最不需要的牌
            for _ in range(min(e['n'], len(P.hand))):
                cands = [x for x in P.hand if x is not T.get('_keep')] or P.hand
                w = max(cands, key=lambda c: hand_score([x for x in P.hand if x is not c]))
                P.hand.remove(w); P.deck.append(w)
        elif t == 'event_to_hand' and 'school' in e['filter']:  # 北 P02-024：Event 區的稲荷崎牌 1 張回手牌（不必是最上面）
            cands = [c for c in P.evz if e['filter']['school'] in c.school]
            dcands = [c for c in P.drop if c.ev and e['filter']['school'] in c.school] if e.get('include_drop') else []
            if cands or dcands:
                if cands: best = max(cands, key=event_value); P.evz.remove(best)
                else: best = max(dcands, key=event_value); P.drop.remove(best)
                P.add_nondraw(best); P.bump('北回收事件')
                if e.get('discard_after') and P.hand:
                    w = pick_discard(P, T); P.hand.remove(w); P.drop.append(w)
        elif t == 'guts_any_to_zone':  # どん ぴしゃり：任一區 Guts 的某人名 1 張登場（登場技能等這張事件全部解決完才處理）
            z = e['zone']; nm = e['filter']['name']
            if not name_ok(T, z, nm): continue
            g = [(zz, c) for zz, st in P.zones.items() if zz in ZSTAT for c in st[:-1]
                 if not c.ev and c.name == nm and can_enter(P, z, c, from_hand=False) and (z != 'toss' or toss_allowed(P, c))]
            if not g: continue
            def proj(item):
                zz, c = item
                under = len(P.zones[z]) - (1 if zz == z else 0)
                return pulled_value(P, T, c, z, under)
            zz, best = max(g, key=proj)
            v, extra = proj((zz, best))
            if (v, extra) > (cur_stat(P, T, z), 0):
                P.zones[zz].remove(best)
                enter(P, T, z, best, from_hand=False, name=nm, defer=e.get('by', 'どん ぴしゃり'))
                P.bump('どんぴしゃり叫出:' + z)
        elif t == 'event_to_hand' and 'exclude_name' in e['filter']:  # P03-090：Event 區這張以外的事件 1 張回手牌
            cands = [c for c in P.evz if c.name != e['filter']['exclude_name']]
            if cands:
                best = max(cands, key=event_value); P.evz.remove(best); P.add_nondraw(best); P.bump('回收事件')
        elif t == 'event_to_hand':
            cands = [c for c in P.evz if c.phases == {e['filter']['only_phase']}]
            if cands:
                best = max(cands, key=lambda c: (c.name == 'オープン攻撃', keep_value(c)))
                P.evz.remove(best); P.add_nondraw(best); P.bump('回收攻擊事件')
        elif t == 'negate_skills':  # 赤葦 P02-066：本回合自己的某人名角色技能無效
            T.setdefault('negated', set()).add(e['name']); P.bump('木兎技能無效')
        elif t == 'look_top_take':  # 闇路 P01-089（某校）／P04-099（指定卡名）：看牌庫頂 n 張，挑最多 max 張，其餘放牌庫底
            top = P.deck[:e['n']]; del P.deck[:e['n']]
            cands = [c for c in top if (c.name in e['names'] if e.get('names') else e['school'] in c.school)
                     and (not e.get('event_only') or c.ev) and (not e.get('char_only') or not c.ev)]
            if cands:
                best = max(cands, key=keep_value); top.remove(best); P.add_nondraw(best); P.bump('闇路檢索命中'); T['took'] = True
            P.deck += top
        elif t == 'drop_to_zone':
            if not name_ok(T, e['zone'], e['name']): continue
            hs = [c for c in P.drop if c.name == e['name']]
            if not hs: continue
            best = max(hs, key=lambda c: summon_value(P, c, e['zone']))
            P.drop.remove(best); enter(P, T, e['zone'], best, from_hand=False); P.bump('高球特召')
            if e.get('then'): apply_effects([e['then']], P, T, e['zone'])
        elif t == 'guts_move_to_zone':  # 白布：自己場上任一區的白鳥沢 Guts 1 張移到攻擊區當 Guts
            dst = P.zones[e['to']]
            if not dst: continue
            for z in ('block', 'serve', 'receive', 'toss'):
                g = [c for c in P.guts(z) if not c.ev and e['school'] in c.school]
                if g:
                    P.zones[z].remove(g[0]); dst.insert(0, g[0]); P.bump('白布搬Guts'); break
        elif t == 'drop_opp_zone_guts':  # 牛島 P02-046：對手接球區 Guts 最多 n 張（對手回合開始前執行）
            T['locks'].append(dict(rule='drop_zone_guts', zone=e['zone'], n=e['max'], duration='now'))
            P.bump('棄對手接球Guts')
        elif t == 'opp_discard':  # 及川 P01-033：對手從手牌棄 1 張（對手自己選，立即生效）
            T['locks'].append(dict(rule='drop_hand_card', n=e['n'], duration='now')); P.bump('及川逼棄牌')
        elif t == 'rcv_add_paid_blk':  # 縁下 P04-007：接球 + 付出的 Guts 的攔網值合計
            T['mod'][zone] = T['mod'].get(zone, 0) + sum(x.b['blk'] for x in (T.get('paid_guts') or []))
        elif t == 'guts_to_hand_same_school':  # 烏野 P01-076：自己某一區的 Guts 中，同所屬的 n 張加入手牌
            best = None
            for zz, st in P.zones.items():
                if zz not in ZSTAT: continue
                g = [c for c in st[:-1] if not c.ev]
                for sch in {t2 for c in g for t2 in c.school}:
                    cand = sorted([c for c in g if sch in c.school], key=keep_value, reverse=True)
                    if e.get('distinct'):  # 音駒 P01-021、P03-088：卡名各不相同
                        seen, uniq = set(), []
                        for c in cand:
                            if c.name not in seen: seen.add(c.name); uniq.append(c)
                        cand = uniq
                    cand = cand[:e['n']]
                    if len(cand) == e['n'] and (best is None or sum(map(keep_value, cand)) > best[0]): best = (sum(map(keep_value, cand)), zz, cand)
            if best:
                for c in best[2]: P.zones[best[1]].remove(c); P.add_nondraw(c)
                P.bump('Guts回手牌'); T['took'] = True
        elif t == 'guts_grade_to_hand':  # 烏野 PR-078：自己某一區的某年級的 Guts 最多 n 張加入手牌
            best = None
            for zz, st in P.zones.items():
                if zz not in ZSTAT: continue
                g = sorted([x for x in st[:-1] if not x.ev and x.aff.endswith('·%s年' % e['grade'])], key=keep_value, reverse=True)[:e['n']]
                if g and (best is None or sum(map(keep_value, g)) > best[0]): best = (sum(map(keep_value, g)), zz, g)
            if best:
                for c in best[2]: P.zones[best[1]].remove(c); P.add_nondraw(c)
                P.bump('Guts回手牌')
        elif t == 'this_event_to_hand_if_took':  # 清水 P03-094：有加入手牌的話，這張事件也回手牌
            ev = T.get('playing_ev')
            if T.get('took') and ev is not None and ev in P.evz: P.evz.remove(ev); P.add_nondraw(ev); P.bump('清水回手')
        elif t == 'drop_to_deck_bottom_if_took':  # 音駒 P03-088：（有加入手牌的話）棄牌區某校角色卡 1 張放牌庫底
            if T.get('took'):
                c2 = [x for x in P.drop if not x.ev and e['school'] in x.school]
                if c2:
                    w = min(c2, key=keep_value); P.drop.remove(w); P.deck.append(w); P.bump('棄牌區放牌庫底')
        elif t == 'rcv_best_of':  # 音駒 P01-082：二選一——音駒接球角色接球 +1，或接球 ≥5 的音駒接球角色接球變 7（選比較高的）
            st = P.zones['receive']
            if st and e['school'] in st[-1].school:
                cur = cur_stat(P, T, 'receive')
                to = e.get('set_to', 7)
                add = to - cur if cur >= e.get('min_cur', 5) and to - cur > 1 else 1
                T['mod']['receive'] = T['mod'].get('receive', 0) + add
        elif t == 'opp_reshuffle_draw':  # 及川 P01-034、PR-024：對手手牌全部洗回牌庫，再抽 n 張
            o = T['opp']; o.deck += o.hand; o.hand = []; o.rng.shuffle(o.deck); o.draw(e['n']); P.bump('對手手牌洗回重抽')
        elif t == 'reveal_top_take_school':  # 溫田 D04-013：公開牌庫頂，是某校就加入手牌（否則放牌庫底）；公開的是事件再抽 1
            if P.deck:
                top = P.deck.pop(0)
                if e['school'] in top.school: P.add_nondraw(top); T['took'] = True
                else: P.deck.append(top)
                if top.ev: P.draw(1)
        elif t == 'discard_if_took_n':  # 斉藤 P02-095：撈回了 n 張才要從手牌棄 1 張
            if T.get('took_n', 0) >= e['n'] and P.hand:
                w = pick_discard(P, T); P.hand.remove(w); P.drop.append(w)
        elif t == 'stat_set_zone':  # P03-091：這區的角色數值直接變成 value（發球階段、發球角色是宮侑）
            if P.zones[e['zone']]:
                cur = cur_stat(P, T, e['zone']); T['mod'][e['zone']] = T['mod'].get(e['zone'], 0) + (e['value'] - cur)
        elif t == 'coin':  # 天童 P02-048：丟硬幣，正面 heads、反面 tails
            P.bump('擲硬幣')
            apply_effects(e['heads'] if P.rng.random() < 0.5 else e['tails'], P, T, zone)
        elif t == 'mill_n':  # 自己牌庫頂 n 張丟棄
            for _ in range(min(e['n'], len(P.deck))): P.drop.append(P.deck.pop(0))
        elif t == 'mill_tiers':  # 條善寺／和久谷南：牌庫頂 n 張丟棄，依其中符合條件的張數套用分段效果（cumulative=False 只套最高一段）
            got = [P.deck.pop(0) for _ in range(min(e['n'], len(P.deck)))]
            P.drop.extend(got); P.bump('丟牌檢查')
            if e.get('count') == 'event': k = sum(1 for x in got if x.ev)
            else: k = sum(1 for x in got if (not x.ev) and e['school'] in x.school)
            tiers = [tr for tr in e['tiers'] if k >= tr['ge']]
            if tiers and not e.get('cumulative', True): tiers = [max(tiers, key=lambda tr: tr['ge'])]
            for tr in tiers: apply_effects(tr['effects'], P, T, zone)
        elif t == 'mill_take':  # 大平 P04-062：牌庫頂 n 張丟棄，其中符合 filter 的 1 張加入手牌
            top = P.deck[:e['n']]; del P.deck[:e['n']]
            cand = [x for x in top if filt_ok(x, e['filter'])]
            for x in top: P.drop.append(x)
            if cand:
                best = max(cand, key=keep_value); P.drop.remove(best); P.add_nondraw(best); P.bump('丟牌撈回')
        elif t == 'drop_distinct_school_to_hand':  # 滑津 P03-097：棄牌區卡名不同的某校角色 n 張加入手牌，再從手牌棄 1 張
            seen, pick = set(), []
            for x in sorted([x for x in P.drop if not x.ev and e['school'] in x.school], key=keep_value, reverse=True):
                if x.name not in seen and len(pick) < e['n']: seen.add(x.name); pick.append(x)
            for x in pick: P.drop.remove(x); P.add_nondraw(x)
            if P.hand:
                w = pick_discard(P, T); P.hand.remove(w); P.drop.append(w)
        elif t == 'look_top_two_picks':  # 疑似ユース P03-079：看牌庫頂 n 張，取符合 first 的 1 張；有取到再從剩下的取符合 second 的 1 張
            top = P.deck[:e['n']]; del P.deck[:e['n']]
            c1 = [x for x in top if filt_ok(x, e['first'])]
            if c1:
                b1 = max(c1, key=keep_value); top.remove(b1); P.add_nondraw(b1)
                c2 = [x for x in top if filt_ok(x, e['second'])]
                if c2:
                    b2 = max(c2, key=keep_value); top.remove(b2); P.add_nondraw(b2)
            P.deck += top
        elif t == 'draw_to':  # 国見 P02-058：抽到手牌剛好 n 張（已經 ≥n 張就不抽）
            P.draw(max(0, e['n'] - len(P.hand)))
        elif t == 'reveal_top_then':  # P01-092／093：公開牌庫頂；自己場上沒有與它同所屬的角色時，執行 then；公開的牌放牌庫底
            if not P.deck: continue
            top = P.deck.pop(0)
            court = set()
            for z, st in P.zones.items():
                if z in ZSTAT and st: court |= st[-1].affs
            if e.get('school'): hit = e['school'] in top.affs  # 山口 P01-010：公開的牌是某校的卡（事件也有學校，例：烏野事件算烏野）
            else: hit = not (court & top.affs)  # 事件牌沒有所屬 → 一定成立（QA 1243、1245：公開到自己也成立）
            P.deck.append(top); P.bump('翻牌成立' if hit else '翻牌不成立')
            if hit: apply_effects(e['then'], P, T, zone)
        elif t == 'drop_opp_events_then':  # 星海 P01-066：對手 Event 區最多 n 張棄牌；之後剩 ≤max_left 張則執行 then
            k = len(T['opp'].evz); d = min(e['n'], k)
            if d:
                T['locks'].append(dict(rule='drop_event_cards', n=d, duration='now')); P.bump('星海棄對手Event', d)
            if k - d <= e['max_left']: apply_effects(e['then'], P, T, zone)
        elif t == 'drop_opp_event_chars':  # P03-099：對手 Event 區的角色牌（模擬中不會出現）
            k = sum(1 for c in T['opp'].evz if not c.ev)
            if k:
                T['locks'].append(dict(rule='drop_event_chars', duration='now'))
                if k >= e['bonus_if_ge']: apply_effects([e['then']], P, T, zone)
        else:
            raise ValueError(t)


def event_value(c):
    """回收事件時的偏好：攻擊事件（可打 8 點）> 接球事件 > 其他。"""
    return (2 if 'attack' in c.phases else 1 if 'receive' in c.phases else 0) + 0.1 * len(c.skills)


def summon_value(P, c, zone):
    v = c.b['atk']
    for s in c.skills:
        if s['timing'] == 'on_enter' and zone in s.get('zones', []):
            for co in s.get('cost', []):
                if co['type'] == 'guts' and len(P.zones[zone]) >= co['n']: v += 4
    return v


def pulled_value(P, T, c, zone, under):
    """被叫出的角色在該區預估的數值（含付得起的登場技能），以及附帶好處（抽牌、封鎖）。"""
    v = c.b[ZSTAT[zone]]; extra = 0
    for s in c.skills:
        if s['timing'] != 'on_enter' or zone not in s.get('zones', []): continue
        if not all(c['type'] in ('entered_by', 'entered_by_skill') or cond_ok(c, P, T) for c in s.get('conditions', [])): continue
        ok = True
        for co in s.get('cost', []):
            if co['type'] == 'guts' and under < co['n']: ok = False
            if co['type'] in ('discard_hand', 'hand_to_deck_bottom') and (len(P.hand) < co['n'] or not T.get('allow_discard_cost')): ok = False
        if not ok: continue
        for e in s['effects']:
            if e['type'] == 'stat_add' and e['target'] == 'this' and e['stat'] == ZSTAT[zone]: v += e['n']
            elif e['type'] in ('draw', 'restrict_opp'): extra = 1
    return v, extra


def will_be_replaced(P, T, zone, v_after):
    """同一拍手上有能叫出攻擊手的事件（どん ぴしゃり），而 Guts 裡有叫出來會比 v_after 高的角色 → 這張會被蓋掉、加值消失。"""
    for ev in P.hand:
        if not ev.ev: continue
        for sk in ev.skills:
            for e in sk['effects']:
                if e['type'] != 'guts_any_to_zone' or e['zone'] != zone: continue
                if e.get('if') and not all(c['type'] == 'self_role_name' or cond_ok(c, P, T) for c in e['if']): continue
                nm = e['filter']['name']
                for zz, st in P.zones.items():
                    if zz not in ZSTAT: continue
                    for c in st[:-1]:
                        if not c.ev and c.name == nm:
                            under = len(P.zones[zone]) - (1 if zz == zone else 0)
                            if pulled_value(P, T, c, zone, under)[0] > v_after: return True
    return False


def has_attack_skill(card):
    return any(s['timing'] == 'on_enter' and 'attack' in s.get('zones', []) for s in card.skills)


def enter(P, T, zone, card, from_hand, as_side_blocker=False, name=None, defer=None):
    nm = name or choose_name(T, zone, card)
    under = None
    if as_side_blocker:
        P.zones.setdefault('_side', []).append(card)
    else:
        under = P.zones[zone][-1] if P.zones[zone] else None
        if under is not None and under is T.get('bottom_paid_on'): P.bump('D03-002加值被蓋掉')
        P.zones[zone].append(card)
        T['mod'][zone] = 0
        if zone == 'toss': T['set_toss'] = None; T['toss_cap'] = None
        if under is not None:  # 木葉 P01-047：疊在這張攻擊角色上的梟谷角色攻擊 +1（棄手牌 1 張）
            for s in under.skills:
                tr = s.get('trigger')
                if (s['timing'] == 'trigger' and tr and tr['event'] == 'enter_on_top' and tr['zone'] == zone
                        and tr['school'] in card.school and T.get('allow_discard_cost')
                        and cost_pay(s.get('cost', []), P, T, zone)):
                    P.bump('木葉觸發'); apply_effects(s['effects'], P, T, zone)
    T['names'][zone] = nm
    if defer:  # QA 1368：先把事件效果全部解決，再處理叫出來角色的登場技能
        T.setdefault('deferred', []).append((zone, card, from_hand, under, nm, defer)); return
    enter_skills(P, T, zone, card, from_hand, under if not as_side_blocker else None, nm, as_side_blocker)


def run_deferred(P, T):
    while T.get('deferred'):
        zone, card, from_hand, under, nm, by = T['deferred'].pop(0)
        T['entered_by'] = by
        enter_skills(P, T, zone, card, from_hand, under, nm, False)
        T['entered_by'] = None


def enter_skills(P, T, zone, card, from_hand, under, nm, as_side_blocker):
    T['entering_from_hand'] = from_hand
    T['entering_side'] = as_side_blocker
    T['under'] = under
    if zone == 'toss' and from_hand and 'S' in card.pos:  # 對手侑 P04-068：從手牌出場 S 的舉球角色，舉球 −1
        for l in P.restrict:
            if l['rule'] == 'opp_s_toss_add': T['mod']['toss'] = T['mod'].get('toss', 0) + l['n']; P.bump('S舉球被侑P04-068減值')
    if zone == 'receive' and 'Li' in card.pos:  # 對手瀬見 P03-072：Li 接球角色每次出場 −1
        for l in P.restrict:
            if l['rule'] == 'li_receive_add': T['mod']['receive'] = T['mod'].get('receive', 0) + l['n']; P.bump('Li被瀬見減值')
    if zone == 'attack':  # 音駒 研磨 D02-001：對手的攻擊角色每次出場 −2
        for l in P.restrict:
            if l['rule'] == 'opp_atk_add': T['mod']['attack'] = T['mod'].get('attack', 0) + l['n']; P.bump('攻擊被研磨減值')
    if zone == 'receive':  # 青葉城西 P04-088：對手的接球角色每次登場接球 −1
        for l in P.restrict:
            if l['rule'] == 'opp_rcv_add' and card.b['rcv'] >= l.get('base_ge', 0): T['mod']['receive'] = T['mod'].get('receive', 0) + l['n']; P.bump('接球被減值')
    if zone == 'toss':  # 烏野 山口 P01-010／嶋田 P03-054
        for l in P.restrict:
            if l['rule'] == 'opp_toss_add': T['mod']['toss'] = T['mod'].get('toss', 0) + l['n']; P.bump('舉球被山口減值')
            if l['rule'] == 'opp_s_toss_set' and from_hand and 'S' in card.pos: T['set_toss'] = l['value']; P.bump('S舉球被嶋田變1')
    if zone == 'receive' and card.noskill:  # 稲荷崎応援団 P02-086：沒有技能的接球角色每次登場 −1
        for l in P.restrict:
            if l['rule'] == 'opp_noskill_rcv_add': T['mod']['receive'] = T['mod'].get('receive', 0) + l['n']; P.bump('無技能接球被減值')
    if (zone in ('receive', 'toss') and any(l['rule'] == 'nullify_receive_toss_skills' for l in P.restrict)) or (
            zone == 'receive' and any(l['rule'] == 'nullify_receive_skills' for l in P.restrict)):
        P.bump('接球舉球技能被無效'); return  # 手白 P01-032
    if zone == 'block' and not as_side_blocker and any(l['rule'] == 'nullify_center_skills' for l in P.restrict):
        P.bump('中間攔網技能被無效'); return  # 東峰 P04-013
    if nm in T.get('negated', ()):
        P.bump('技能被無效'); return
    if zone == 'attack' and T.get('aura') and nm == T['aura'][0]:
        T['mod']['attack'] = T['mod'].get('attack', 0) + T['aura'][1]
    if zone == 'block' and not as_side_blocker:  # 對手 PR-031：中間攔網登場時攔網值 −2
        for l in P.restrict:
            if l['rule'] == 'center_blocker_blk_add': T['mod']['block'] = T['mod'].get('block', 0) + l['n']
    for s in card.skills:
        if s['timing'] != 'on_enter' or zone not in s.get('zones', []): continue
        if zone == 'block' and (as_side_blocker or T.get('decline_onetouch')) and any(
                e['type'] == 'keyword' and e['name'] == 'ワンタッチ' for e in s['effects']):
            continue  # 一觸只能中間攔網用；多張一起攔網時不發動（會跳過攔網判定，白丟其他攔網角色）【使用者 2026-10-15】
        if not all(cond_ok(c, P, T) for c in s.get('conditions', [])): continue
        if not all(cond_ok(c, P, T) for c in s.get('use_if', [])): continue  # 策略條件（不是卡片文字）：值得付代價才用
        costs = s.get('cost', [])
        T['paid_guts'] = None
        if any(c['type'] in ('discard_hand', 'hand_to_deck_bottom', 'discard_hand_filtered') for c in costs) and not (
                T.get('allow_discard_cost') or s.get('auto_cost') or (zone == 'receive' and card.b['rcv'] < T['op_in'])
                or any(e['type'] == 'event_to_hand' and 'school' in e['filter']
                       and any(e['filter']['school'] in x.school and 'attack' in x.phases for x in P.evz)
                       for e in s['effects'])): continue
        if any(c['type'] == 'hand_to_deck_bottom' for c in costs) and P.label == 'A' and CFG['hand_bottom_policy'] != 'default':
            pol = CFG['hand_bottom_policy']
            if pol == 'never': continue
            gain = sum(e['n'] for e in s['effects'] if e['type'] == 'stat_add' and e['target'] == 'this')
            if pol in ('smart', 'lethal_smart') and will_be_replaced(P, T, zone, cur_stat(P, T, zone) + gain): continue
            op_if = cur_stat(P, T, 'toss') + cur_stat(P, T, 'attack') + gain
            if pol in ('lethal', 'lethal_smart') and response_cost(T['opp'], op_if, T['locks'], False, attacker=P) is not None: continue
        neg = [e['name'] for e in s['effects'] if e['type'] == 'negate_skills']
        pa = T.get('plan_attack')
        if neg and pa and pa[1] in neg and has_attack_skill(pa[0]): continue  # 會廢掉本回合木兎攻擊技能時不用
        if (any(c['type'] == 'drop_block_char' for c in costs) and zone == 'receive'
                and cur_stat(P, T, 'receive') >= T['op_in']): continue  # P03-067：接得住就不棄攔網角色
        if not cost_pay(costs, P, T, zone): continue
        if any(c['type'] == 'hand_to_deck_bottom' for c in costs): T['bottom_paid_on'] = card
        P.bump('技能:' + card.no)
        apply_effects(s['effects'], P, T, zone)
    if zone == 'attack' and from_hand:  # 研磨：自己從手牌出場原本攻擊值 3 的攻擊角色時
        st = P.zones['toss']
        tt = st[-1] if st else None
        if tt:
            for s in tt.skills:
                tr = s.get('trigger')
                if s['timing'] == 'trigger' and tr and tr['event'] == 'enter' and card.b['atk'] == tr['base_atk'] and P.deck:
                    P.drop.append(P.deck.pop(0))
                    T['mod']['toss'] = T['mod'].get('toss', 0) + 1; P.bump('研磨觸發')
                    g = [c for c in P.guts('attack') if c is not card and not c.ev and alt_ok(T, 'attack', c)]
                    if g:
                        aura = lambda c: T['aura'][1] if T.get('aura') and c.name == T['aura'][0] else 0
                        best = max(g, key=lambda c: summon_value(P, c, 'attack') + aura(c))
                        if summon_value(P, best, 'attack') + aura(best) > cur_stat(P, T, 'attack'):
                            P.zones['attack'].remove(best); enter(P, T, 'attack', best, from_hand=False)
                            P.bump('研磨拉Guts打手')


# 使用者打法：某些卡只在條件成立時才拿來舉球（2026-10-16：侑 D03-001 只在 Event 區有「今日 何をする？」時才用）
TOSS_ONLY_IF_EVZ = {'HV-D03-001': '今日 何をする？'}


def toss_allowed(P, c):
    need = TOSS_ONLY_IF_EVZ.get(c.no)
    return need is None or any(e.name == need for e in P.evz)


def event_playable(P, T, ev):
    """事件的「使える」條件（例：今日 何をする？ 要舉球是侑或治）。"""
    if ev.phases & {'toss', 'attack'} and any(l['rule'] == 'no_toss_attack_events' for l in P.restrict): return False  # P01-093：QA 1247
    return all(cond_ok(c, P, T) for s in ev.skills if not s.get('part_of_same_card') for c in s.get('conditions', []) + s.get('use_if', []))


def play_event(P, T, ev, zone_hint):
    if not event_playable(P, T, ev): return
    if any(s.get('once_per_turn') for s in ev.skills):
        used = T.setdefault('once_used', set())
        if ev.name in used: return
        used.add(ev.name)
    P.hand.remove(ev); P.evz.append(ev); T['playing_ev'] = ev; T['took'] = False; T['last_target_zone'] = None  # 每張事件從頭算「同一個角色」
    if 'attack' in ev.phases and any(l['rule'] == 'nullify_attack_event_skills' for l in P.restrict):
        P.bump('攻擊事件技能被無效'); return  # 伊達工業 青根 P03-063：事件放進 Event 區但技能無效
    if T['phase'] == 'attack':  # P03-047 影山：攻擊階段從手牌打出事件時
        st = P.zones['toss']
        if st:
            for s in st[-1].skills:
                tr = s.get('trigger')
                if s['timing'] == 'trigger' and tr and tr['event'] == 'play_event':
                    T['mod']['toss'] = T['mod'].get('toss', 0) + 1; T['toss_cap'] = 3; P.bump('影山P03-047觸發')
    for s in ev.skills:
        if s.get('part_of_same_card') and any(c['type'] == 'drop_block_char' for c in s.get('cost', [])):
            # P01-091：接不住時才棄置攔網角色換對手攻擊 −1
            if T['src'] == 'attack' and cur_stat(P, T, 'receive') < T['op_in'] and cost_pay(s['cost'], P, T, zone_hint):
                apply_effects(s['effects'], P, T, zone_hint)
            continue
        if s.get('part_of_same_card'):
            has_atk_ev_in_hand = any(c.ev and c.phases == {'attack'} for c in P.hand)
            if ev in P.evz and any(c.phases == {'attack'} for c in P.evz) and not has_atk_ev_in_hand:
                P.evz.remove(ev); P.deck.append(ev)
                apply_effects(s['effects'], P, T, zone_hint)
            continue
        if ev.name == 'オープン攻撃': T['want_hinata'] = True
        apply_effects(s['effects'], P, T, zone_hint)
        run_deferred(P, T)
        T['want_hinata'] = False
    P.bump('事件:' + ev.no)


def cur_stat(P, T, zone):
    st = P.zones[zone]
    if not st: return 0
    top = st[-1]
    if zone == 'toss':
        base = T['set_toss'] if T.get('set_toss') is not None else top.b['tos']
        v = base + T['mod'].get('toss', 0)
        if T.get('toss_cap') is not None: v = min(v, max(T['toss_cap'], base))
        return v
    return top.b[ZSTAT[zone]] + T['mod'].get(zone, 0)


# ── 對手回應成本（決策用的估計，不含對手事件牌）────────────
def rcv_potential(opp, c):
    v = c.b['rcv']; g = len(opp.zones['receive'])
    for s in c.skills:
        if s['timing'] == 'on_enter' and 'receive' in s.get('zones', []):
            if all(co['type'] != 'guts' or g >= co['n'] for co in s.get('cost', [])):
                for e in s['effects']:
                    if e['type'] == 'stat_add' and e['target'] == 'this' and e['stat'] == 'rcv': v += e['n']
    return v


def onetouch_n(c):
    for s in c.skills:
        if s['timing'] == 'on_enter' and 'block' in s.get('zones', []):
            for e in s['effects']:
                if e['type'] == 'keyword' and e['name'] == 'ワンタッチ': return e['n']
    return 0


def hand_trap(c):
    """接球階段從手牌棄掉這張、某校角色接球 +n 的卡 → (學校, n)；不是就回傳 None。"""
    for s in c.skills:
        if s['timing'] == 'from_hand' and 'receive' in s.get('phases', []) and \
                any(co['type'] == 'discard_this_from_hand' for co in s.get('cost', [])):
            for e in s['effects']:
                if e['type'] == 'stat_add' and e['stat'] == 'rcv' and isinstance(e['target'], dict):
                    return e['target'].get('school'), e['n']
    return None


def trap_bonus(P, r):
    """手牌中可用在接球角色 r 的手坑加值合計：手坑沒特別註明就能有幾張用幾張（使用者 2026-10-16）。"""
    if nullified(P.restrict): return 0
    return sum(ht[1] for c in P.hand if c is not r for ht in [hand_trap(c)] if ht and (ht[0] is None or ht[0] in r.school))


def _can_receive(opp, chars, op):
    li = sum(l['n'] for l in opp.restrict if l['rule'] == 'li_receive_add')
    for r in chars:
        if not can_enter(opp, 'receive', r): continue
        if rcv_potential(opp, r) + trap_bonus(opp, r) + (li if 'Li' in r.pos else 0) < op: continue
        rest = [c for c in chars if c is not r]
        if any(can_differ(t, r) and any(a is not t and can_differ(a, t) for a in rest) for t in rest):
            return True
    return False


def blk_potential(B, c, attacker, events_free):
    """攔網角色 c 的預估攔網值：原本攔網值 ＋ 條件成立、付得起的登場技能加值（月島 P02-003：+6，要 1 張手牌事件）。"""
    v = c.b['blk']; need = 0
    for s in c.skills:
        if s['timing'] != 'on_enter' or 'block' not in s.get('zones', []): continue
        conds = s.get('conditions', [])
        if any(x['type'] == 'opp_event_count_ge' and len(attacker.evz) < x['n'] for x in conds): continue
        ev_cost = sum(co['n'] for co in s.get('cost', []) if co['type'] == 'event_hand_to_evz')
        if ev_cost > events_free - need: continue
        add = sum(e['n'] for e in s['effects'] if e['type'] == 'stat_add' and e['target'] == 'this' and e['stat'] == 'blk')
        if add: v += add; need += ev_cost
    return v, need


def block_event_boost(B):
    tot = 0
    for ev in B.hand:
        if not ev.ev or 'block' not in ev.phases: continue
        for sk in ev.skills:
            for e in sk['effects']:
                if e['type'] == 'stat_add' and e.get('stat') in ('blk', 'any_phase', 'any') and isinstance(e.get('target'), dict): tot += e['n']
    return tot


def block_actual(P2, T):
    """攔網區現在實際的攔網值合計：中間攔網（含技能加值）＋側邊攔網的原本攔網值。"""
    return cur_stat(P2, T, 'block') + sum(x.b['blk'] for x in P2.zones.get('_side', []))


def play_block_events(P2, T, need):
    """登場後打攔網階段事件：會抽牌的事件一律打（手牌不變、多一個效果）；其他的只在還不夠擋時才打。"""
    T['phase'] = 'block'
    evs = [e for e in P2.hand if e.ev and 'block' in e.phases]
    evs.sort(key=lambda e: not any(x['type'] == 'draw' for sk in e.skills for x in sk['effects']))
    for ev in evs:
        if ev not in P2.hand: continue
        cantrip = any(x['type'] == 'draw' for sk in ev.skills for x in sk['effects'])
        if cantrip or block_actual(P2, T) < need: play_event(P2, T, ev, 'block')


def block_total(B, comb, attacker, restrict, include_adj=True):
    """一組攔網角色的攔網值合計與中間攔網人選。角名 P02-027 生效時，中間攔網的攔網值當作 0（選攔網值最低的當中間）。"""
    ev_free = sum(1 for x in B.hand if x.ev)
    pots = []
    for c in comb:
        v, need = blk_potential(B, c, attacker, ev_free) if attacker is not None else (c.b['blk'], 0)
        ev_free -= need; pots.append(v)
    adj = sum(l['n'] for l in restrict if l['rule'] == 'center_blocker_blk_add') if include_adj else 0
    boost = block_event_boost(B)  # 手牌的攔網階段事件（最樂觀估計；真的組合會再驗證）
    if any(l['rule'] == 'center_no_blk' for l in restrict):
        i = min(range(len(comb)), key=lambda j: pots[j])
        return sum(pots) - pots[i] + boost, comb[i]
    return sum(pots) + adj + boost, None


def response_cost(opp, op, locks, trap, src='attack', attacker=None):
    """對手要淨花幾張牌才接得住；接不住回傳 None。"""
    restrict = opp.restrict  # 暫存：用我施加的限制來判斷
    opp.restrict = locks
    chars = [c for c in opp.hand if not c.ev]
    best = None
    mb = max_blockers(locks)
    for k in range(1, mb + 1):
        found = False
        for comb in itertools.combinations(chars, k):
            if assign_distinct(comb) is None or not all(can_enter(opp, 'block', c) for c in comb): continue
            if block_total(opp, comb, attacker, locks, include_adj=False)[0] >= block_need(locks, op): found = True; break  # 舊版估計不含 PR-031 調整，保留
        if found: best = k; break
    if _can_receive(opp, chars, op):
        best = 2 if best is None else min(best, 2)
    elif op >= 4 and not onetouch_nullified(locks) and (src == 'attack' or not CFG['onetouch_attack_only']):  # 一觸：1 張中間攔網削弱後再接球（淨花 3 張）
        for c in chars:
            n = onetouch_n(c)
            if n and can_enter(opp, 'block', c) and _can_receive(opp, [x for x in chars if x is not c], op - n):
                best = 3 if best is None else min(best, 3); break
    opp.restrict = restrict
    if op == 0 and CFG['freeball_receive'] and best is not None:
        # 0 點球：對手能接就一定接（淨花 2 張），接不了才用 1 張攔網
        can_receive = any(True for r in chars if can_enter(opp, 'receive', r)) and len(chars) >= 3
        best = 2 if can_receive else best
    return best


def evaluate(P, op_sent, locks, trap, opp, src='attack'):
    cost = response_cost(opp, op_sent, locks, trap, src, attacker=P)
    s = hand_score(P.hand)
    if cost is None: return 1000 + s
    return s + CFG['w_cost'] * cost + CFG['w_op'] * op_sent


# ── 一個回合 ──────────────────────────────────────────
def wants_odd(c): return any(cd['type'] == 'zone_guts_odd' for s in c.skills for cd in s.get('conditions', []))


def do_receive_line(P, T, r, t, a, aggressive, stop_after_toss=False):
    T['phase'] = 'receive'
    ln = line_names(r, t, a)
    if ln is None: return None
    nr, nt, na = ln
    T['plan_attack'] = (a, na) if a is not None else None
    if a is not None: T['aim_odd_attack'] = wants_odd(a)
    elif stop_after_toss:  # 攻擊手等舉球後再決定：手牌、棄牌區或攻擊區 Guts 有 P01-043 這類卡就調奇數
        T['aim_odd_attack'] = any(wants_odd(c) for c in P.hand + P.drop + P.zones['attack'] if c is not r and c is not t)
    P.hand.remove(r); enter(P, T, 'receive', r, from_hand=True, name=nr)
    for ev in [e for e in P.hand if e.ev and 'receive' in e.phases]:
        if ev in P.hand: play_event(P, T, ev, 'receive')  # 絶望叫出的北可能棄掉手牌中的其他接球事件
    if cur_stat(P, T, 'receive') < T['op_in'] and not nullified(P.restrict):
        # 手坑可以有幾張用幾張（使用者 2026-10-16）；用到剛好接得住為止，接不住就一張都不用
        rc = P.zones['receive'][-1]
        traps = [h for h in P.hand if hand_trap(h) and (hand_trap(h)[0] is None or hand_trap(h)[0] in rc.school)]
        traps.sort(key=lambda h: -hand_trap(h)[1])
        need = T['op_in'] - cur_stat(P, T, 'receive'); use = []
        for h in traps:
            if need <= 0: break
            use.append(h); need -= hand_trap(h)[1]
        if need <= 0:
            for h in use:
                P.hand.remove(h); P.drop.append(h); T['mod']['receive'] = T['mod'].get('receive', 0) + hand_trap(h)[1]
                P.bump('緣下手坑' if h.no == 'HV-P01-013' else '手坑:' + h.no)
    if cur_stat(P, T, 'receive') < T['op_in']: return None
    if t not in P.hand or (a is not None and a not in P.hand): return None
    if not name_ok(T, 'toss', nt): return None
    T['phase'] = 'toss'
    P.hand.remove(t); T['allow_optional'] = aggressive == 'two'
    enter(P, T, 'toss', t, from_hand=True, name=nt)
    if T.get('two_attack') is not None:  # 二段攻擊：進攻值固定 N，跳到結束階段，對手下回合不能攔網
        T['locks'].append(dict(rule='max_enter', role='block', max=0, duration='next_opp_turn'))
        return T['two_attack']
    if aggressive == 'two': return None
    for ev in [e for e in P.hand if e.ev and 'toss' in e.phases]:
        cantrip = any(e['type'] == 'draw' for sk in ev.skills for e in sk['effects'])  # 今日 何をする？：會抽牌的舉球事件一律打
        if ev in P.hand and (cantrip or ('S' in t.pos and cur_stat(P, T, 'toss') < 2)): play_event(P, T, ev, 'toss')
    if stop_after_toss: return 'TOSSED'
    return attack_part(P, T, a, na, aggressive)


def attack_part(P, T, a, na, aggressive):
    if a not in P.hand or not name_ok(T, 'attack', na): return None
    T['phase'] = 'attack'
    P.hand.remove(a); T['allow_discard_cost'] = bool(aggressive)
    enter(P, T, 'attack', a, from_hand=True, name=na)
    if aggressive:
        for ev in sorted([e for e in P.hand if e.ev and 'attack' in e.phases], key=lambda e: e.name != 'オープン攻撃'):
            if ev in P.hand: play_event(P, T, ev, 'attack')
    return cur_stat(P, T, 'toss') + cur_stat(P, T, 'attack')


def receive_best(Pd, opp, op_in, src):
    """已抽完牌的狀態下，列舉接球→舉球→攻擊的所有組合，回傳最佳 (評分, P, 進攻值, src, locks, trap, 行動)。"""
    dchars = [c for c in Pd.hand if not c.ev]
    rec_best = None
    if len(dchars) < 2: return None
    rcands = [c for c in dchars if can_enter(Pd, 'receive', c)]
    rcands.sort(key=lambda c: (keep_value(c), -c.b['rcv']))
    two_ok = any(any(e['type'] == 'optional' for e in s['effects']) for c in dchars for s in c.skills
                 if s['timing'] == 'on_enter' and 'toss' in s.get('zones', []))
    for r in rcands[:5]:
        for t in dchars:
            if t is r or not can_differ(t, r) or not toss_allowed(Pd, t): continue
            modes = [('two', None)] if two_ok else []
            modes += [(m, a) for a in dchars if a is not r and a is not t and can_differ(a, t) for m in (True, False)]
            for aggressive, a in modes:
                P2 = Pd.clone(); T = newT(opp, op_in, src)
                op = do_receive_line(P2, T, r, t, a, aggressive)
                if op is None: continue
                v = evaluate(P2, op, T['locks'], T['trap'], opp)
                act = 'receive2' if aggressive == 'two' else 'receive'
                if rec_best is None or v > rec_best[0]:
                    rec_best = (v, P2, op, 'attack', T['locks'], T['trap'], act)
            if CFG['fetch_then_attack'] and has_fetch(t):
                P2 = Pd.clone(); T = newT(opp, op_in, src)
                if do_receive_line(P2, T, r, t, None, False, stop_after_toss=True) != 'TOSSED': continue
                for a in {id(c): c for c in P2.hand if not c.ev}.values():
                    if not alt_ok(T, 'attack', a): continue
                    for aggressive in (True, False):
                        P3 = P2.clone(); T3 = cloneT(T)
                        op = attack_part(P3, T3, a, choose_name(T3, 'attack', a), aggressive)
                        if op is None: continue
                        v = evaluate(P3, op, T3['locks'], T3['trap'], opp)
                        if rec_best is None or v > rec_best[0]:
                            P3.bump('舉球後選攻擊手')
                            if any(a is c for c in Pd.drop + Pd.zones['attack'] + Pd.zones['toss']): P3.bump('撿回立刻攻擊')
                            rec_best = (v, P3, op, 'attack', T3['locks'], T3['trap'], 'receive')
    return rec_best


def has_fetch(t):
    return any(e['type'] == 'drop_to_hand' for s in t.skills if s['timing'] == 'on_enter' and 'toss' in s.get('zones', [])
               for e in s['effects'])


def draw_phase_events(P, opp, op_in, src):
    """抽牌階段只能打的事件（P03-090）：Event 區有可回收的事件時才打。"""
    T = newT(opp, op_in, src); T['phase'] = 'draw'
    for ev in [e for e in P.hand if e.ev and e.phases == {'draw'}]:
        if any(s.get('draw_policy') == 'always' for s in ev.skills):  # 混校批次的抽牌階段事件：條件成立就打
            if ev in P.hand: play_event(P, T, ev, 'draw')
            continue
        dn = [x for s in ev.skills for x in s['effects'] if x['type'] == 'drop_names_to_hand']
        if dn:
            if ev in P.hand and any(not c.ev and c.name in dn[0]['names'] for c in P.drop): play_event(P, T, ev, 'draw')
        elif ev in P.hand and any(c.name != ev.name for c in P.evz): play_event(P, T, ev, 'draw')
    # 闇路 P01-089 這類「看牌庫頂撿牌」且抽牌階段可打的事件：抽完牌就先打，撿到的牌本回合的接球／舉球／攻擊都能用
    # （使用者 2026-10-14 指出；原本被延到接球階段，撿到的牌這拍用不到）
    for ev in [e for e in P.hand if e.ev and 'draw' in e.phases and e.phases != {'draw'}
               and any(x['type'] == 'look_top_take' for s in e.skills for x in s['effects'])]:
        if ev in P.hand: play_event(P, T, ev, 'draw')


def apply_now(locks, target):
    """立即生效的效果（對手區域的 Guts、Event 區角色牌），回傳剩下的持續效果。"""
    rest = []
    for l in locks:
        if l['rule'] == 'drop_zone_guts':
            st = target.zones[l['zone']]
            for _ in range(min(l['n'], max(0, len(st) - 1))): target.drop.append(st.pop(0))
        elif l['rule'] == 'drop_hand_card':  # 對手自己選：棄掉棄後手牌評分最高的那張（最沒用的牌）
            for _ in range(min(l['n'], len(target.hand))):
                w = max(target.hand, key=lambda c: hand_score([x for x in target.hand if x is not c]))
                target.hand.remove(w); target.drop.append(w)
        elif l['rule'] == 'drop_event_cards':  # 星海 P01-066：棄對手 Event 區的牌（選有用的事件）
            for c in sorted(target.evz, key=event_value, reverse=True)[:l['n']]:
                target.evz.remove(c); target.drop.append(c)
        elif l['rule'] == 'drop_event_chars':
            ch = [c for c in target.evz if not c.ev]
            for c in ch: target.evz.remove(c); target.drop.append(c)
        else: rest.append(l)
    return rest


def take_turn(P, opp, op_in, src):
    """回傳 ('loss', P) 或 ('ok', P_after, op_sent, src_sent, locks, trap, action)"""
    P.restrict, P.trap = P.pending_restrict, P.pending_trap
    P.pending_restrict, P.pending_trap = [], False
    best = None

    def consider(P2, op_sent, src_sent, locks, trap, action):
        nonlocal best
        v = evaluate(P2, op_sent, locks, trap, opp, src_sent)
        if best is None or v > best[0]: best = (v, P2, op_sent, src_sent, locks, trap, action)

    chars = [c for c in P.hand if not c.ev]
    # 攔網（不抽牌）
    freeball = op_in == 0 and CFG['freeball_receive']
    mb = max_blockers(P.restrict)
    adj = sum(l['n'] for l in P.restrict if l['rule'] == 'center_blocker_blk_add')
    blocks = []; centers = {}
    for k in range(1, mb + 1):
        for comb in itertools.combinations([c for c in chars if can_enter(P, 'block', c)], k):
            if assign_distinct(comb) is None: continue
            tot, cen = block_total(P, comb, opp, P.restrict)
            if tot >= block_need(P.restrict, op_in):
                blocks.append(comb); centers[id(comb)] = cen
        if len(blocks) >= 6: break
    # 一觸：只放 1 張中間攔網，觸發後直接抽牌、接球（使用者確認）
    if mb >= 1 and not freeball and not onetouch_nullified(P.restrict):
        for c in {x.no: x for x in chars if onetouch_n(x) and can_enter(P, 'block', x)}.values():
            P2 = P.clone(); T = newT(opp, op_in, src); T['phase'] = 'block'; T['block_comb'] = (c,)
            P2.hand.remove(c); enter(P2, T, 'block', c, from_hand=True)
            if T.get('onetouch'):
                P2.draw(1); draw_phase_events(P2, opp, op_in - T['onetouch'], src)
                rb = receive_best(P2, opp, op_in - T['onetouch'], src)
                if rb and (best is None or rb[0] > best[0]):
                    best = (rb[0], rb[1], rb[2], rb[3], rb[4], rb[5], 'onetouch')
            elif c.b['blk'] + adj >= block_need(P.restrict, op_in):
                consider(P2, T.get('doshat', 0), CFG['blocked_ball_src'], T['locks'], T['trap'], 'block1')
    blocks.sort(key=lambda cb: (len(cb), sum(keep_value(c) for c in cb)))
    for comb in blocks[:4]:
        P2 = P.clone(); T = newT(opp, op_in, src); T['phase'] = 'block'; T['decline_onetouch'] = True; T['block_comb'] = comb  # 這條路是靠攔網值合計攔下來
        center = centers.get(id(comb)) or min(comb, key=keep_value)
        for c in comb: P2.hand.remove(c)  # 同時登場：先全部拿出手牌，再依序處理登場效果
        for c, nm in zip(comb, assign_distinct(comb)):
            enter(P2, T, 'block', c, from_hand=True, as_side_blocker=c is not center, name=nm)
        if CFG['verify_block'] and not any(l['rule'] == 'center_no_blk' for l in P.restrict):
            play_block_events(P2, T, op_in)
            if block_actual(P2, T) < block_need(P.restrict, op_in): P2.zones.pop('_side', None); continue  # 技能沒發動成功，這個組合擋不住
        P2.drop += P2.zones.pop('_side', [])
        if T.get('zeroed'): continue  # 有角色數值歸 0，原本的攔網合計不成立
        consider(P2, T.get('doshat', 0), CFG['blocked_ball_src'], T['locks'], T['trap'], 'block%d' % len(comb))
    # 接球（抽 1）
    Pd = P.clone(); Pd.draw(1); draw_phase_events(Pd, opp, op_in, src)
    rec_best = receive_best(Pd, opp, op_in, src)
    if freeball and rec_best is not None:
        best = rec_best
    elif rec_best is not None and (best is None or rec_best[0] > best[0]):
        best = rec_best
    if best is None: return ('loss', P)
    _, P2, op_sent, src_sent, locks, trap, action = best
    P2.bump('行動:' + action)
    P2.restrict, P2.trap = [], False
    return ('ok', P2, op_sent, src_sent, locks, trap, action)


def serve_turn(P, opp):
    P.restrict, P.trap = P.pending_restrict, P.pending_trap
    P.pending_restrict, P.pending_trap = [], False
    best = None
    for c in [x for x in P.hand if not x.ev and can_enter(P, 'serve', x)]:
        P2 = P.clone(); T = newT(opp, 0, None); T['phase'] = 'serve'
        P2.hand.remove(c); enter(P2, T, 'serve', c, from_hand=True)
        variants = [(P2, T)]
        for ev in {e.name: e for e in P2.hand if e.ev and 'serve' in e.phases}.values():  # 發球階段事件：打或不打，選評分高的
            P3 = P2.clone(); T3 = cloneT(T); T3['phase'] = 'serve'
            ev3 = next((x for x in P3.hand if x.name == ev.name), None)
            if ev3 is not None:
                play_event(P3, T3, ev3, 'serve'); variants.append((P3, T3))
        for i, (Pv, Tv) in enumerate(variants):
            op = cur_stat(Pv, Tv, 'serve')
            v = evaluate(Pv, op, Tv['locks'], Tv['trap'], opp, 'serve')
            if best is None or v > best[0] or (i > 0 and v >= best[0]): best = (v, Pv, op, Tv['locks'], Tv['trap'])  # 同分時打事件（會抽牌）
    if best is None: return ('loss', P)
    _, P2, op, locks, trap = best
    P2.restrict, P2.trap = [], False
    return ('ok', P2, op, 'serve', locks, trap, 'serve')


def mulligan(P):
    P.draw(6)
    if not any((not c.ev) and c.b['rcv'] >= 5 for c in P.hand):
        P.deck += P.hand; P.hand = []; P.rng.shuffle(P.deck); P.draw(6); P.bump('重抽')


def play_game(cardsA, cardsB, rng, log=None):
    pl = {'A': Player(cardsA, rng, 'A'), 'B': Player(cardsB, rng, 'B')}
    server = rng.choice('AB')
    other = lambda x: 'B' if x == 'A' else 'A'
    mulligan(pl[server]); mulligan(pl[other(server)])
    for k in 'AB': pl[k].setz = [pl[k].deck.pop(0), pl[k].deck.pop(0)]
    sets = {'A': 0, 'B': 0}; set_no = 0; turns_log = []
    while True:
        set_no += 1
        cur = server
        res = serve_turn(pl[cur], pl[other(cur)])
        loser = None
        if res[0] == 'loss': loser = cur
        else:
            _, pl[cur], op, src, locks, trap, act = res
            pl[other(cur)].pending_restrict, pl[other(cur)].pending_trap = apply_now(locks, pl[other(cur)]), trap
            beats = 0
            while True:
                cur = other(cur); beats += 1
                res = take_turn(pl[cur], pl[other(cur)], op, src)
                if res[0] == 'loss' or beats > CFG['max_turns_per_set']:
                    loser = cur; pl[cur].bump('LOSS'); break
                _, pl[cur], op, src, locks, trap, act = res
                turns_log.append(dict(set=set_no, beat=beats, who=cur, act=act, op=op))
                if log is not None:
                    log.append((set_no, beats, cur, act, op, len(pl[cur].hand), len(pl[cur].deck)))
                pl[other(cur)].pending_restrict, pl[other(cur)].pending_trap = apply_now(locks, pl[other(cur)]), trap
            turns_log.append(dict(set=set_no, beat=beats, who=cur, act='LOSS', op=0))
        winner = other(loser); sets[winner] += 1
        if any(l['rule'] == 'owner_draw_to_on_loss' for l in pl[loser].restrict):  # P01-090：對手 LOSS 時抽到 7 張
            n7 = max(l['n'] for l in pl[loser].restrict if l['rule'] == 'owner_draw_to_on_loss')
            k = pl[winner].draw(max(0, n7 - len(pl[winner].hand)))
            pl[winner].bump('P01-090抽到7', k)
        for k in 'AB':  # 局間：持續效果結束、補到 6 張
            pl[k].pending_restrict, pl[k].pending_trap, pl[k].restrict, pl[k].trap = [], False, [], False
            while len(pl[k].hand) < 6 and pl[k].deck: pl[k].draw(1)
        if not pl[loser].setz:
            return dict(winner=winner, sets=sets, set_no=set_no, turns=turns_log,
                        deck_left={k: len(pl[k].deck) for k in 'AB'}, stats={k: pl[k].stats for k in 'AB'})
        pl[loser].hand.append(pl[loser].setz.pop(0))
        server = winner


def build(U, deck):
    L = [Card(U[no]) for no, n in deck.items() for _ in range(n)]
    assert len(L) == 40, (len(L), deck)
    return L


def match(U, deckA, deckB, N, seed=1):
    rng = random.Random(seed)
    A, B = build(U, deckA), build(U, deckB)
    return [play_game(A, B, rng) for _ in range(N)]
