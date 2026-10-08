"""對局模擬器 v1：只模擬「自己這一方」，對手用攻擊曲線與防守門檻代表。
技能由 manual_cards.MANUAL 的結構化資料驅動（不是逐卡寫死），所以模擬結果也在檢驗結構化是否正確。

尚未經使用者確認的假設集中在 ASSUME，報告時一併列出。"""
import json, random, os, sys, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from manual_cards import MANUAL

ASSUME = dict(
    opp_serve=[(1, .3), (2, .3), (3, .3), (5, .1)],  # 對手發球點數分布
    opp_attack=5,              # 對手一般攻擊
    opp_spike=9,               # 對手大招（8～11 取中間）
    opp_spike_every=4,         # 對手第 4、8、12… 次攻擊是大招
    opp_def=[8, 9, 10],        # 我方進攻值 ≥ 此值，對手接不住（得分）；每拍從中隨機取一個【使用者：8～10 點才接不住】
    lock_def_minus=1,          # 我方封鎖效果生效時，對手防守門檻 −1
    opp_max_receives=2,        # 對手一個 Rally 最多接 2 次，第 3 次手牌不夠（與我方同樣的手牌經濟推算）
    loser_set_after_refill=True,  # 失分方先補到 6 張，再拿 Set 牌（共 7 張）
    a_pass_as_toss=1,          # Aパス(1) 當作本回合舉球 +1
    opp_hand_le3_from_turn=2,  # Rally 中我方第 2 拍起，視為對手手牌 ≤3（岩泉條件）
    opp_event_ge5=False,       # 烏養追加條件（對手 Event 區防守事件 ≥5）視為不成立
)

ROLE_STAT = dict(receive='rcv', toss='tos', attack='atk')


def load_cards(path):
    s = open(path, encoding='utf-8').read()
    d = json.loads(s[s.index('{'):s.rstrip().rstrip(';').rindex('}') + 1])
    u = {}
    for c in d['cards']:
        u.setdefault(c['card_no'], c)
    return u


class Card:
    __slots__ = ('no', 'name', 'ev', 'pos', 'school', 'b', 'skills', 'phases', 'uid')

    def __init__(self, raw, uid):
        self.no = raw['card_no']; self.name = raw['name']; self.ev = raw['category'] == 'EVENT'
        self.pos = set(p.strip() for p in (raw['position'] or '').split(','))
        self.school = set(raw.get('school_tags') or [raw['school']])
        self.b = {k: (raw.get(k) or 0) for k in ('srv', 'blk', 'rcv', 'tos', 'atk')}
        self.skills = MANUAL.get(self.no, [])
        self.phases = set(p for s in self.skills for p in s.get('phases', [])) if self.ev else set()
        self.uid = uid

    def __repr__(self): return f'{self.no}'


# ── 卡片價值（決策用的啟發式：越高越想留在手上）──────────────
def keep_value(c):
    if c.ev: return 4
    v = max(c.b['tos'] * 1.5, c.b['atk'])
    for s in c.skills:
        z = s.get('zones', [])
        if 'toss' in z or 'attack' in z: v += 2.5
    return v


def hand_score(hand):
    """整手牌的價值：除了單卡價值，還要保住「下一拍接得住」與「舉球、攻擊都有人」。"""
    ch = [c for c in hand if not c.ev]
    s = sum(keep_value(c) for c in hand) + 3 * len(hand)
    rc = sorted((c.b['rcv'] for c in ch), reverse=True)
    if rc and rc[0] >= 5: s += 8
    if len(rc) > 1 and rc[1] >= 5: s += 3
    if any(c.b['tos'] >= 1 for c in ch): s += 2
    if any(c.b['atk'] >= 3 for c in ch): s += 2
    return s


class Player:
    def __init__(self, deck_cards, rng):
        self.rng = rng
        self.deck = deck_cards[:]; rng.shuffle(self.deck)
        self.hand, self.drop, self.evz, self.setz = [], [], [], []
        self.zones = dict(receive=[], toss=[], attack=[])
        self.lost = 0
        self.stats = {}

    def draw(self, n=1):
        k = 0
        for _ in range(n):
            if self.deck: self.hand.append(self.deck.pop(0)); k += 1
        return k

    def guts(self, zone): return self.zones[zone][:-1]

    def pay_guts(self, zone, n):
        st = self.zones[zone]
        if len(st) - 1 < n: return False
        for _ in range(n): self.drop.append(st.pop(0))  # 從最底下開始付
        return True

    def bump(self, k, n=1): self.stats[k] = self.stats.get(k, 0) + n

    def clone(self):
        o = Player.__new__(Player)
        o.rng = self.rng; o.deck = self.deck[:]; o.hand = self.hand[:]; o.drop = self.drop[:]
        o.evz = self.evz[:]; o.setz = self.setz[:]; o.zones = {k: v[:] for k, v in self.zones.items()}
        o.lost = self.lost; o.stats = dict(self.stats)
        return o


# ── 條件 ────────────────────────────────────────────
def cond_ok(c, P, T):
    t = c['type']
    if t == 'set_total_le': return (len(P.setz) + T['opp_set']) <= c['n']
    if t in ('opp_op_le', 'opp_op_ge'):
        src = T['opp_src']
        if c['of'] == 'serve' and src != 'serve': return False
        if c['of'] == 'attack' and src != 'attack': return False
        return T['opp_op'] <= c['n'] if t == 'opp_op_le' else T['opp_op'] >= c['n']
    if t == 'opp_hand_le': return T['turn_in_rally'] >= ASSUME['opp_hand_le3_from_turn']
    if t == 'self_is_role': return True  # 由呼叫端保證此卡在該區頂端
    if t == 'self_role_name':
        top = P.zones[c['role']][-1] if P.zones[c['role']] else None
        return top is not None and top.name == c['name']
    if t == 'event_zone_count_le':
        n = sum(1 for e in P.evz if e.name == c['card_name'])
        return n <= c['n']  # 呼叫端已把這張放進 Event 區（含這張）
    if t == 'event_zone_phase_count_ge': return ASSUME['opp_event_ge5']
    raise ValueError(t)


def cost_ok_and_pay(costs, P, T, zone, card, pay=True):
    for c in costs:
        t = c['type']
        if t == 'guts' and len(P.zones[zone]) - 1 < c['n']: return False
        if t == 'mill' and not P.deck: return False
        if t == 'discard_hand' and len(P.hand) < c['n']: return False
    if not pay: return True
    for c in costs:
        t = c['type']
        if t == 'guts': P.pay_guts(zone, c['n'])
        elif t == 'mill': P.drop.append(P.deck.pop(0))
        elif t == 'discard_hand':
            for _ in range(c['n']):
                w = max(P.hand, key=lambda x: hand_score([y for y in P.hand if y is not x]))
                P.hand.remove(w); P.drop.append(w)
    return True


# ── 效果 ────────────────────────────────────────────
def apply_effects(effs, P, T, zone, card):
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
            elif tg == 'same': z = T.get('last_target_zone', 'attack')
            else:
                z = 'attack' if e['stat'] == 'atk' else ('receive' if e['stat'] == 'rcv' else 'toss')
                top = P.zones[z][-1] if P.zones[z] else None
                if top is None or (tg.get('school') and tg['school'] not in top.school): continue
            T['mod'][z] = T['mod'].get(z, 0) + e['n']; T['last_target_zone'] = z
        elif t == 'stat_set':
            top = P.zones['toss'][-1] if P.zones['toss'] else None
            if top and 'S' in top.pos:
                T['set_toss'] = e['value']; T['mod']['toss'] = 0
        elif t == 'stat_cap': T['toss_cap'] = e['below'] - 1
        elif t == 'keyword':
            if e['name'] == 'Aパス': T['mod']['toss'] = T['mod'].get('toss', 0) + ASSUME['a_pass_as_toss']
        elif t == 'reveal_top_take':
            if P.deck:
                top = P.deck.pop(0)
                if top.name in e['names']: P.hand.append(top); P.bump('影山檢索命中')
                else: P.deck.append(top)
                P.bump('影山檢索')
        elif t == 'aura_on_enter': T['aura'] = (e['name'], e['n']); P.bump('影山光環')
        elif t == 'drop_to_hand':
            f = e['filter']
            cands = [c for c in P.drop if not c.ev and (not f.get('school') or f['school'] in c.school)]
            if cands:
                best = max(cands, key=keep_value); P.drop.remove(best); P.hand.append(best)
        elif t == 'restrict_opp': T['locks'].append(e['rule']); P.bump('封鎖:' + e['rule'])
        elif t == 'on_opp_non_draw_add_mill': P.bump('二口登場')
        elif t == 'guts_to_zone':
            g = [c for c in P.guts(e['zone']) if not c.ev and (not e.get('filter') or e['filter'].get('position', '') in c.pos)]
            g = [c for c in g if legal_name(P, T, e['zone'], c)]
            if g:
                best = max(g, key=lambda c: c.b[ROLE_STAT[e['zone']]])
                promote(P, T, e['zone'], best)
        elif t == 'event_to_hand':
            cands = [c for c in P.evz if c.phases == {e['filter']['only_phase']}]
            if cands:
                best = max(cands, key=lambda c: (c.name == 'オープン攻撃', keep_value(c)))
                P.evz.remove(best); P.hand.append(best); P.bump('回收攻擊事件')
        elif t == 'drop_to_zone':
            if not legal_name_name(P, T, e['zone'], e['name']): continue
            hs = [c for c in P.drop if c.name == e['name']]
            if not hs: continue
            best = max(hs, key=lambda c: summon_value(P, c, e['zone']))
            P.drop.remove(best)
            enter(P, T, e['zone'], best, from_hand=False)
            P.bump('高球特召日向')
            if e.get('then'): apply_effects([e['then']], P, T, e['zone'], best)
        else:
            raise ValueError(t)


def legal_name_name(P, T, zone, name):
    if zone == 'attack': return T['toss_name'] != name
    if zone == 'toss': return T['recv_name'] != name and T.get('atk_name') != name
    return True


def legal_name(P, T, zone, c): return legal_name_name(P, T, zone, c.name)


def summon_value(P, c, zone):
    v = c.b['atk']
    for s in c.skills:
        if s['timing'] == 'on_enter' and zone in s.get('zones', []):
            for co in s.get('cost', []):
                if co['type'] == 'guts' and len(P.zones[zone]) >= co['n']: v += 4
    return v


def pick_discard(P, T):
    # 高球進攻：棄牌區沒有日向時，丟一張日向進去以便特召
    if T.get('want_hinata_in_drop') and not any(c.name == '日向 翔陽' for c in P.drop):
        hs = [c for c in P.hand if c.name == '日向 翔陽']
        if hs: return max(hs, key=lambda c: summon_value(P, c, 'attack'))
    return max(P.hand, key=lambda c: hand_score([x for x in P.hand if x is not c]))


def promote(P, T, zone, card):
    st = P.zones[zone]; st.remove(card)
    enter(P, T, zone, card, from_hand=False, place_only=False)
    P.bump('Guts拉上場')


def enter(P, T, zone, card, from_hand, place_only=False):
    """角色出場：放到該區頂端（原頂端成為 Guts），清掉該區暫時加值，處理登場技能、光環、研磨。"""
    P.zones[zone].append(card)
    T['mod'][zone] = 0
    if zone == 'toss': T['set_toss'] = None; T['toss_name'] = card.name
    if zone == 'attack': T['atk_name'] = card.name
    if zone == 'receive': T['recv_name'] = card.name
    if zone == 'attack' and T.get('aura') and card.name == T['aura'][0]:
        T['mod']['attack'] += T['aura'][1]
    for s in card.skills:
        if s['timing'] != 'on_enter' or zone not in s.get('zones', []): continue
        if not all(cond_ok(c, P, T) for c in s.get('conditions', [])): continue
        costs = s.get('cost', [])
        # 棄手牌換加攻：只在需要時才用（由 T['allow_discard_cost'] 控制）
        if any(c['type'] == 'discard_hand' for c in costs) and not T.get('allow_discard_cost'): continue
        if not cost_ok_and_pay(costs, P, T, zone, card): continue
        P.bump('技能:' + card.no)
        apply_effects(s['effects'], P, T, zone, card)
    # 研磨：自己從手牌出場原本攻擊值 3 的攻擊角色時
    if zone == 'attack' and from_hand:
        tt = P.zones['toss'][-1] if P.zones['toss'] else None
        if tt:
            for s in tt.skills:
                tr = s.get('trigger')
                if s['timing'] == 'trigger' and tr and tr['event'] == 'enter' and card.b['atk'] == tr['base_atk']:
                    g = [c for c in P.guts('attack') if c is not card and not c.ev and legal_name(P, T, 'attack', c)]
                    # 只有在 Guts 裡有更好的打手時才發動（否則只換來舉球 +1 與自磨 1 張，也划算 → 一律發動）
                    if not P.deck: continue
                    P.drop.append(P.deck.pop(0))
                    T['mod']['toss'] = T['mod'].get('toss', 0) + 1
                    P.bump('研磨觸發')
                    if g:
                        best = max(g, key=lambda c: summon_value(P, c, 'attack') + (T['aura'][1] if T.get('aura') and c.name == T['aura'][0] else 0))
                        cur = card.b['atk'] + T['mod']['attack']
                        newv = summon_value(P, best, 'attack') + (T['aura'][1] if T.get('aura') and best.name == T['aura'][0] else 0)
                        if newv > cur:
                            P.zones['attack'].remove(best)
                            enter(P, T, 'attack', best, from_hand=False)
                            P.bump('研磨拉Guts打手')


def play_event(P, T, ev, zone_hint):
    P.hand.remove(ev); P.evz.append(ev)
    # P03-047 影山：攻擊階段從手牌打出事件時舉球 +1（上限 3）
    if T['phase'] == 'attack':
        tt = P.zones['toss'][-1] if P.zones['toss'] else None
        if tt:
            for s in tt.skills:
                tr = s.get('trigger')
                if s['timing'] == 'trigger' and tr and tr['event'] == 'play_event':
                    T['mod']['toss'] = T['mod'].get('toss', 0) + 1; T['toss_cap'] = 3; P.bump('影山P03-047觸發')
    skills = ev.skills
    main = [s for s in skills if not s.get('part_of_same_card')]
    extra = [s for s in skills if s.get('part_of_same_card')]
    for s in main:
        if ev.name == 'オープン攻撃': T['want_hinata_in_drop'] = True
        apply_effects(s['effects'], P, T, zone_hint, ev)
        T['want_hinata_in_drop'] = False
    for s in extra:  # 你的打法：回收攻擊事件（代價：此卡放牌庫底）
        has_atk_ev_in_hand = any(c.ev and c.phases == {'attack'} for c in P.hand)
        has_target = any(c.phases == {'attack'} for c in P.evz)
        if has_target and not has_atk_ev_in_hand:
            P.evz.remove(ev); P.deck.append(ev)
            apply_effects(s['effects'], P, T, zone_hint, ev)
    P.bump('事件:' + ev.no)


def cur_stat(P, T, zone):
    top = P.zones[zone][-1]
    if zone == 'toss':
        base = T['set_toss'] if T.get('set_toss') is not None else top.b['tos']
        v = base + T['mod'].get('toss', 0)
        if T.get('toss_cap') is not None: v = min(v, max(T['toss_cap'], base))
        return v
    return top.b[ROLE_STAT[zone]] + T['mod'].get(zone, 0)


# ── 一個接球回合 ──────────────────────────────────────
def new_T(opp_op, opp_src, turn_in_rally, opp_set):
    return dict(opp_op=opp_op, opp_src=opp_src, turn_in_rally=turn_in_rally, opp_set=opp_set,
                mod={}, locks=[], aura=None, set_toss=None, toss_cap=None,
                recv_name=None, toss_name=None, atk_name=None, phase='receive')


def do_receive(P, T, c):
    P.hand.remove(c); enter(P, T, 'receive', c, from_hand=True)
    for ev in [e for e in P.hand if e.ev and 'receive' in e.phases]:
        play_event(P, T, ev, 'receive')
    if cur_stat(P, T, 'receive') < T['opp_op']:
        for h in [x for x in P.hand if x.no == 'HV-P01-013']:  # 從手牌發動的接球加值
            if '烏野' in P.zones['receive'][-1].school and cur_stat(P, T, 'receive') + 2 >= T['opp_op']:
                P.hand.remove(h); P.drop.append(h); T['mod']['receive'] += 2; P.bump('緣下手坑'); break
    return cur_stat(P, T, 'receive') >= T['opp_op']


def finish_attack(P, T, t, a, need, try_score):
    T['phase'] = 'toss'
    P.hand.remove(t); enter(P, T, 'toss', t, from_hand=True)
    for ev in [e for e in P.hand if e.ev and 'toss' in e.phases]:
        if 'S' in t.pos and cur_stat(P, T, 'toss') < 2: play_event(P, T, ev, 'toss')
    T['phase'] = 'attack'
    P.hand.remove(a)
    T['allow_discard_cost'] = try_score
    enter(P, T, 'attack', a, from_hand=True)
    if try_score:
        for ev in sorted([e for e in P.hand if e.ev and 'attack' in e.phases], key=lambda e: e.name != 'オープン攻撃'):
            if cur_stat(P, T, 'toss') + cur_stat(P, T, 'attack') >= need: break
            if ev in P.hand: play_event(P, T, ev, 'attack')
    return cur_stat(P, T, 'toss') + cur_stat(P, T, 'attack')


def my_turn(P, opp_op, opp_src, turn_in_rally, opp_set, need):
    """回傳 (結果, P_after, op, locks)；結果：'rcv_fail' / 'no_chars' / 'ok'"""
    P.draw(1)
    chars = [c for c in P.hand if not c.ev]
    if len(chars) < 3: return 'no_chars', P, 0, []
    # 依留牌價值由低到高嘗試接球者
    best = None
    for rc in sorted(chars, key=lambda c: (keep_value(c), -c.b['rcv']))[:4]:
        P1 = P.clone(); T1 = new_T(opp_op, opp_src, turn_in_rally, opp_set)
        if not do_receive(P1, T1, rc): continue
        hand_chars = [c for c in P1.hand if not c.ev]
        for t in hand_chars:
            if t.name == T1['recv_name']: continue
            for a in hand_chars:
                if a is t or a.name == t.name: continue
                for try_score in (True, False):
                    P2 = P1.clone(); T2 = copy.deepcopy(T1)
                    op = finish_attack(P2, T2, t, a, need, try_score)
                    eff_need = need - (ASSUME['lock_def_minus'] if T2['locks'] else 0)
                    scored = op >= eff_need
                    left = hand_score(P2.hand)
                    key = (scored, left, op)
                    if best is None or key > best[0]: best = (key, P2, op, T2['locks'])
    if best is None:
        # 接不住：看是否有任何角色能接到（只是沒有合法的舉球/攻擊組合）
        any_rcv = False
        for rc in chars:
            P1 = P.clone(); T1 = new_T(opp_op, opp_src, turn_in_rally, opp_set)
            if do_receive(P1, T1, rc): any_rcv = True; break
        return ('no_chars' if any_rcv else 'rcv_fail'), P, 0, []
    return 'ok', best[1], best[2], best[3]


# ── 一場比賽 ──────────────────────────────────────────
def refill(P):
    while len(P.hand) < 6 and P.deck: P.draw(1)


def play_game(deck_cards, rng, log=None):
    P = Player(deck_cards, rng)
    P.draw(6)
    if not any((not c.ev) and c.b['rcv'] >= 5 for c in P.hand):  # 重抽：沒有接球 ≥5 就全換
        P.deck += P.hand; P.hand = []; rng.shuffle(P.deck); P.draw(6); P.bump('重抽')
    P.setz = [P.deck.pop(0), P.deck.pop(0)]
    opp_lost, opp_attacks, i_serve = 0, 0, False
    rally_no, turns = 0, []
    while P.lost < 3 and opp_lost < 3 and rally_no < 12:
        rally_no += 1
        if i_serve and P.hand:  # 我發球：打出一張最不重要的角色
            ch = [c for c in P.hand if not c.ev]
            if ch:  # 發球：選打出後剩下手牌價值最高的那張
                s = max(ch, key=lambda c: hand_score([x for x in P.hand if x is not c]))
                P.hand.remove(s); P.zones.setdefault('serve', []).append(s)
        # 不論誰發球，對手的手牌經濟都只夠接我方 2 次攻擊（見 ASSUME 說明）
        opp_rcv_left = ASSUME['opp_max_receives']
        first = True; k = 0; result = None
        while True:
            k += 1
            if first and not i_serve:
                op = rng.choices([v for v, _ in ASSUME['opp_serve']], [w for _, w in ASSUME['opp_serve']])[0]; src = 'serve'
            else:
                opp_attacks += 1
                op = ASSUME['opp_spike'] if opp_attacks % ASSUME['opp_spike_every'] == 0 else ASSUME['opp_attack']; src = 'attack'
            first = False
            dflt = ASSUME['opp_def']
            opp_d = rng.choice(dflt) if isinstance(dflt, list) else dflt
            res, P, myop, locks = my_turn(P, op, src, k, 2 - min(opp_lost, 2), opp_d)
            turns.append(dict(rally=rally_no, k=k, opp=op, src=src, res=res, op=myop, locks=bool(locks),
                              scored=res == 'ok' and myop >= opp_d - (ASSUME['lock_def_minus'] if locks else 0)))
            if log is not None: log.append((rally_no, k, src, op, res, myop, [c.no for c in P.hand], {z: [c.no for c in v[-1:]] for z, v in P.zones.items()}))
            if res != 'ok': result = 'me_lost:' + res; break
            need = opp_d - (ASSUME['lock_def_minus'] if locks else 0)
            if myop >= need: result = 'opp_lost:attack'; break
            opp_rcv_left -= 1
            if opp_rcv_left < 0: result = 'opp_lost:exhaust'; break
        refill(P)
        if result.startswith('me_lost'):
            P.lost += 1; i_serve = False
            if P.setz: P.hand.append(P.setz.pop(0))
        else:
            opp_lost += 1; i_serve = True
        P.bump(result)
    return dict(win=opp_lost >= 3, my_lost=P.lost, opp_lost=opp_lost, rallies=rally_no,
                deck_left=len(P.deck), turns=turns, stats=P.stats)


def build_deck(U, deck):
    L = []; uid = 0
    for no, n in deck.items():
        for _ in range(n): L.append(Card(U[no], uid)); uid += 1
    assert len(L) == 40, len(L)
    return L


def run(U, deck, N=2000, seed=7):
    rng = random.Random(seed); L = build_deck(U, deck)
    games = [play_game(L, rng) for _ in range(N)]
    return games
