"""雙人對打模擬器 v2：兩副牌依官方規則實際對打（総合ルール 5-2、5-3、規則表）。
- 每局第 1 回合：發球方只發球（不抽牌）
- 之後每回合：攔網（不抽、出 1～3 張不同名、合計 ≥ 進攻值，成功則回 0 點球）或接球（抽 1 → 接球 → 舉球 → 攻擊）
- LOSS → 局間：雙方補到 6 張，LOSS 方拿 1 張 Set 牌（沒有就輸掉比賽）；贏的一方下一局發球
技能由 manual_cards.MANUAL 驅動。出牌決策是啟發式（見 evaluate），雙方使用同一套決策。"""
import json, random, os, sys, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from manual_cards import MANUAL

CFG = dict(
    freeball_receive=True,     # 面對攔回來的 0 點球一律選接球（能接就接）【判斷】
    blocked_ball_src='block',  # 攔回來的球不算「發球」也不算「攻擊」（赤木、澤村條件不成立）【判斷】
    a_pass_as_toss=1,          # Aパス(1) 當作本回合舉球 +1【假設，待第 9 章】
    max_turns_per_set=80,
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
    __slots__ = ('no', 'name', 'ev', 'pos', 'school', 'b', 'skills', 'phases')

    def __init__(self, raw):
        self.no = raw['card_no']; self.name = raw['name']; self.ev = raw['category'] == 'EVENT'
        self.pos = set(p.strip() for p in (raw['position'] or '').split(','))
        self.school = set(raw.get('school_tags') or [raw['school']])
        self.b = {k: (raw.get(k) or 0) for k in ('srv', 'blk', 'rcv', 'tos', 'atk')}
        self.skills = MANUAL.get(self.no, [])
        self.phases = set(p for s in self.skills for p in s.get('phases', [])) if self.ev else set()

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
    return t


# ── 限制（對手施加在我身上的）────────────────────────────
def can_enter(P, zone, card):
    for l in P.restrict:
        if l['rule'] == 'cannot_enter' and l['role'] == zone and card.b['rcv'] >= l['base_rcv_ge']: return False
    return True


def max_blockers(restrict):
    m = 3
    for l in restrict:
        if l['rule'] == 'max_enter' and l['role'] == 'block': m = min(m, l['max'])
    return m


def name_ok(T, zone, name):
    if zone == 'toss': return T['names'].get('receive') != name and T['names'].get('attack') != name
    if zone == 'attack': return T['names'].get('toss') != name
    if zone == 'receive': return T['names'].get('toss') != name
    return True


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
        return bool(st) and st[-1].name == c['name']
    if t == 'event_zone_count_le': return sum(1 for e in P.evz if e.name == c['card_name']) <= c['n']
    if t == 'event_zone_phase_count_ge':
        ph = set(c['phases']); return sum(1 for e in opp.evz if e.phases & ph) >= c['n']
    if t == 'captured_school':
        cap = T.get('captured', {}).get(c['key'])
        if cap is None or c['school'] not in cap.school: return False
        return c.get('category') != 'CHARACTER' or not cap.ev
    if t == 'entered_from_hand': return T.get('entering_from_hand', False)
    if t == 'all_own_chars_school':
        tops = [st[-1] for z, st in P.zones.items() if z in ZSTAT and st]
        return all(c['school'] in x.school for x in tops)
    if t == 'zone_guts_odd': return (len(P.zones[c['zone']]) - 1) % 2 == 1
    raise ValueError(t)


def pick_discard(P, T):
    if T.get('want_hinata') and not any(c.name == '日向 翔陽' for c in P.drop):
        hs = [c for c in P.hand if c.name == '日向 翔陽']
        if hs: return max(hs, key=lambda c: c.b['atk'])
    return max(P.hand, key=lambda c: hand_score([x for x in P.hand if x is not c]))


def cost_pay(costs, P, T, zone):
    for c in costs:
        t = c['type']
        if t == 'guts' and len(P.zones[zone]) - 1 < c['n']: return False
        if t == 'guts_multi' and sum(max(0, len(P.zones[z]) - 1) for z in c['zones']) < c['n']: return False
        if t == 'mill' and not P.deck: return False
        if t == 'discard_hand' and len(P.hand) < c['n']: return False
        if t == 'discard_named' and sum(1 for x in P.hand if x.name == c['name']) < c['n']: return False
        if t == 'drop_block_char':
            st = P.zones['block']
            if not st or c['school'] not in st[-1].school: return False
    for c in costs:
        t = c['type']
        if t == 'guts': P.pay_guts(zone, c['n'])
        elif t == 'guts_multi':  # 跨區合計付 Guts：先付舉球區，再付攻擊區
            left = c['n']
            for z in c['zones']:
                k = min(left, max(0, len(P.zones[z]) - 1)); P.pay_guts(z, k); left -= k
        elif t == 'mill':
            m = P.deck.pop(0); P.drop.append(m)
            if c.get('capture'): T.setdefault('captured', {})[c['capture']] = m
        elif t == 'discard_hand':
            for _ in range(c['n']):
                w = pick_discard(P, T); P.hand.remove(w); P.drop.append(w)
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
            elif tg == 'same': z = T['last_target_zone'] or 'attack'
            else:
                z = dict(atk='attack', rcv='receive', tos='toss', blk='block', srv='serve')[e['stat']]
                st = P.zones[z]
                if not st or (tg.get('school') and tg['school'] not in st[-1].school): continue
            T['mod'][z] = T['mod'].get(z, 0) + e['n']; T['last_target_zone'] = z
        elif t == 'stat_set':
            st = P.zones['toss']
            if st and 'S' in st[-1].pos: T['set_toss'] = e['value']; T['mod']['toss'] = 0
        elif t == 'stat_cap': T['toss_cap'] = e['below'] - 1
        elif t == 'keyword':
            if e['name'] == 'Aパス': T['mod']['toss'] = T['mod'].get('toss', 0) + e['n']
            elif e['name'] == 'ワンタッチ': T['onetouch'] = e['n']; P.bump('一觸')
            elif e['name'] == 'ツーアタック': T['two_attack'] = e['n']; P.bump('二段攻擊')
        elif t == 'mill':
            if P.deck and (not e.get('up_to') or T.get('allow_optional')):
                m = P.deck.pop(0); P.drop.append(m)
                if e.get('capture'): T.setdefault('captured', {})[e['capture']] = m
        elif t == 'optional':
            if T.get('allow_optional') and cost_pay(e.get('cost', []), P, T, zone):
                apply_effects(e['effects'], P, T, zone)
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
            cands = [c for c in P.drop if not c.ev and (not f.get('school') or f['school'] in c.school)
                     and (not f.get('name') or c.name == f['name'])]
            if cands:
                best = max(cands, key=keep_value); P.drop.remove(best); P.add_nondraw(best); P.bump('棄牌區撈回')
        elif t == 'restrict_opp': T['locks'].append(dict(e)); P.bump('封鎖:' + e['rule'])
        elif t == 'on_opp_non_draw_add_mill': T['trap'] = True; P.bump('二口陷阱')
        elif t == 'guts_to_zone':
            g = [c for c in P.guts(e['zone']) if not c.ev and (not e.get('filter') or e['filter'].get('position', '') in c.pos)
                 and name_ok(T, e['zone'], c.name) and can_enter(P, e['zone'], c)]
            if g:
                best = max(g, key=lambda c: c.b[ZSTAT[e['zone']]])
                P.zones[e['zone']].remove(best); enter(P, T, e['zone'], best, from_hand=False); P.bump('Guts拉上場')
        elif t == 'event_to_hand':
            cands = [c for c in P.evz if c.phases == {e['filter']['only_phase']}]
            if cands:
                best = max(cands, key=lambda c: (c.name == 'オープン攻撃', keep_value(c)))
                P.evz.remove(best); P.add_nondraw(best); P.bump('回收攻擊事件')
        elif t == 'drop_to_zone':
            if not name_ok(T, e['zone'], e['name']): continue
            hs = [c for c in P.drop if c.name == e['name']]
            if not hs: continue
            best = max(hs, key=lambda c: summon_value(P, c, e['zone']))
            P.drop.remove(best); enter(P, T, e['zone'], best, from_hand=False); P.bump('高球特召')
            if e.get('then'): apply_effects([e['then']], P, T, e['zone'])
        else:
            raise ValueError(t)


def summon_value(P, c, zone):
    v = c.b['atk']
    for s in c.skills:
        if s['timing'] == 'on_enter' and zone in s.get('zones', []):
            for co in s.get('cost', []):
                if co['type'] == 'guts' and len(P.zones[zone]) >= co['n']: v += 4
    return v


def enter(P, T, zone, card, from_hand, as_side_blocker=False):
    if as_side_blocker:
        P.zones.setdefault('_side', []).append(card)
    else:
        P.zones[zone].append(card)
        T['mod'][zone] = 0
        if zone == 'toss': T['set_toss'] = None; T['toss_cap'] = None
    T['names'][zone] = card.name
    T['entering_from_hand'] = from_hand
    if zone == 'attack' and T.get('aura') and card.name == T['aura'][0]:
        T['mod']['attack'] = T['mod'].get('attack', 0) + T['aura'][1]
    if zone == 'block' and not as_side_blocker:  # 對手 PR-031：中間攔網登場時攔網值 −2
        for l in P.restrict:
            if l['rule'] == 'center_blocker_blk_add': T['mod']['block'] = T['mod'].get('block', 0) + l['n']
    for s in card.skills:
        if s['timing'] != 'on_enter' or zone not in s.get('zones', []): continue
        if not all(cond_ok(c, P, T) for c in s.get('conditions', [])): continue
        costs = s.get('cost', [])
        if any(c['type'] == 'discard_hand' for c in costs) and not (
                T.get('allow_discard_cost') or (zone == 'receive' and card.b['rcv'] < T['op_in'])): continue
        if not cost_pay(costs, P, T, zone): continue
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
                    g = [c for c in P.guts('attack') if c is not card and not c.ev and name_ok(T, 'attack', c.name)]
                    if g:
                        aura = lambda c: T['aura'][1] if T.get('aura') and c.name == T['aura'][0] else 0
                        best = max(g, key=lambda c: summon_value(P, c, 'attack') + aura(c))
                        if summon_value(P, best, 'attack') + aura(best) > cur_stat(P, T, 'attack'):
                            P.zones['attack'].remove(best); enter(P, T, 'attack', best, from_hand=False)
                            P.bump('研磨拉Guts打手')


def play_event(P, T, ev, zone_hint):
    P.hand.remove(ev); P.evz.append(ev)
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


def _can_receive(opp, chars, op):
    enosh = 2 if any(c.no == 'HV-P01-013' for c in opp.hand) else 0
    for r in chars:
        if not can_enter(opp, 'receive', r): continue
        if rcv_potential(opp, r) + (enosh if '烏野' in r.school else 0) < op: continue
        rest = [c for c in chars if c is not r]
        if any(t.name != r.name and any(a is not t and a.name != t.name for a in rest) for t in rest):
            return True
    return False


def response_cost(opp, op, locks, trap):
    """對手要淨花幾張牌才接得住；接不住回傳 None。"""
    restrict = opp.restrict  # 暫存：用我施加的限制來判斷
    opp.restrict = locks
    chars = [c for c in opp.hand if not c.ev]
    best = None
    mb = max_blockers(locks)
    for k in range(1, mb + 1):
        found = False
        for comb in itertools.combinations(chars, k):
            if len({c.name for c in comb}) < k: continue
            if sum(c.b['blk'] for c in comb) >= op: found = True; break
        if found: best = k; break
    if _can_receive(opp, chars, op):
        best = 2 if best is None else min(best, 2)
    elif op >= 4:  # 一觸：1 張中間攔網削弱後再接球（淨花 3 張）
        for c in chars:
            n = onetouch_n(c)
            if n and _can_receive(opp, [x for x in chars if x is not c], op - n):
                best = 3 if best is None else min(best, 3); break
    opp.restrict = restrict
    if op == 0 and CFG['freeball_receive'] and best is not None:
        # 0 點球：對手能接就一定接（淨花 2 張），接不了才用 1 張攔網
        can_receive = any(True for r in chars if can_enter(opp, 'receive', r)) and len(chars) >= 3
        best = 2 if can_receive else best
    return best


def evaluate(P, op_sent, locks, trap, opp):
    cost = response_cost(opp, op_sent, locks, trap)
    s = hand_score(P.hand)
    if cost is None: return 1000 + s
    return s + CFG['w_cost'] * cost + CFG['w_op'] * op_sent


# ── 一個回合 ──────────────────────────────────────────
def do_receive_line(P, T, r, t, a, aggressive):
    T['phase'] = 'receive'
    P.hand.remove(r); enter(P, T, 'receive', r, from_hand=True)
    for ev in [e for e in P.hand if e.ev and 'receive' in e.phases]:
        play_event(P, T, ev, 'receive')
    if cur_stat(P, T, 'receive') < T['op_in']:
        for h in [x for x in P.hand if x.no == 'HV-P01-013']:
            if '烏野' in P.zones['receive'][-1].school and cur_stat(P, T, 'receive') + 2 >= T['op_in']:
                P.hand.remove(h); P.drop.append(h); T['mod']['receive'] = T['mod'].get('receive', 0) + 2; P.bump('緣下手坑'); break
    if cur_stat(P, T, 'receive') < T['op_in']: return None
    if t not in P.hand or (a is not None and a not in P.hand): return None
    if not name_ok(T, 'toss', t.name): return None
    T['phase'] = 'toss'
    P.hand.remove(t); T['allow_optional'] = aggressive == 'two'
    enter(P, T, 'toss', t, from_hand=True)
    if T.get('two_attack') is not None:  # 二段攻擊：進攻值固定 N，跳到結束階段，對手下回合不能攔網
        T['locks'].append(dict(rule='max_enter', role='block', max=0, duration='next_opp_turn'))
        return T['two_attack']
    if aggressive == 'two': return None
    for ev in [e for e in P.hand if e.ev and 'toss' in e.phases]:
        if 'S' in t.pos and cur_stat(P, T, 'toss') < 2: play_event(P, T, ev, 'toss')
    if a not in P.hand or not name_ok(T, 'attack', a.name): return None
    T['phase'] = 'attack'
    P.hand.remove(a); T['allow_discard_cost'] = bool(aggressive)
    enter(P, T, 'attack', a, from_hand=True)
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
            if t is r or t.name == r.name: continue
            modes = [('two', None)] if two_ok else []
            modes += [(m, a) for a in dchars if a is not r and a is not t and a.name != t.name for m in (True, False)]
            for aggressive, a in modes:
                P2 = Pd.clone(); T = newT(opp, op_in, src)
                op = do_receive_line(P2, T, r, t, a, aggressive)
                if op is None: continue
                v = evaluate(P2, op, T['locks'], T['trap'], opp)
                act = 'receive2' if aggressive == 'two' else 'receive'
                if rec_best is None or v > rec_best[0]:
                    rec_best = (v, P2, op, 'attack', T['locks'], T['trap'], act)
    return rec_best


def take_turn(P, opp, op_in, src):
    """回傳 ('loss', P) 或 ('ok', P_after, op_sent, src_sent, locks, trap, action)"""
    P.restrict, P.trap = P.pending_restrict, P.pending_trap
    P.pending_restrict, P.pending_trap = [], False
    best = None

    def consider(P2, op_sent, src_sent, locks, trap, action):
        nonlocal best
        v = evaluate(P2, op_sent, locks, trap, opp)
        if best is None or v > best[0]: best = (v, P2, op_sent, src_sent, locks, trap, action)

    chars = [c for c in P.hand if not c.ev]
    # 攔網（不抽牌）
    freeball = op_in == 0 and CFG['freeball_receive']
    mb = max_blockers(P.restrict)
    adj = sum(l['n'] for l in P.restrict if l['rule'] == 'center_blocker_blk_add')
    blocks = []
    for k in range(1, mb + 1):
        for comb in itertools.combinations(chars, k):
            if len({c.name for c in comb}) < k: continue
            if sum(c.b['blk'] for c in comb) + adj >= op_in:
                blocks.append(comb)
        if len(blocks) >= 6: break
    # 一觸：只放 1 張中間攔網，觸發後直接抽牌、接球（使用者確認）
    if mb >= 1 and not freeball:
        for c in {x.no: x for x in chars if onetouch_n(x)}.values():
            P2 = P.clone(); T = newT(opp, op_in, src); T['phase'] = 'block'
            P2.hand.remove(c); enter(P2, T, 'block', c, from_hand=True)
            if T.get('onetouch'):
                P2.draw(1)
                rb = receive_best(P2, opp, op_in - T['onetouch'], src)
                if rb and (best is None or rb[0] > best[0]):
                    best = (rb[0], rb[1], rb[2], rb[3], rb[4], rb[5], 'onetouch')
            elif c.b['blk'] + adj >= op_in:
                consider(P2, 0, CFG['blocked_ball_src'], T['locks'], T['trap'], 'block1')
    blocks.sort(key=lambda cb: (len(cb), sum(keep_value(c) for c in cb)))
    for comb in blocks[:4]:
        P2 = P.clone(); T = newT(opp, op_in, src); T['phase'] = 'block'
        center = min(comb, key=keep_value)
        for c in comb:
            P2.hand.remove(c)
            enter(P2, T, 'block', c, from_hand=True, as_side_blocker=c is not center)
        P2.drop += P2.zones.pop('_side', [])
        consider(P2, 0, CFG['blocked_ball_src'], T['locks'], T['trap'], 'block%d' % len(comb))
    # 接球（抽 1）
    Pd = P.clone(); Pd.draw(1)
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
    for c in [x for x in P.hand if not x.ev]:
        P2 = P.clone(); T = newT(opp, 0, None); T['phase'] = 'serve'
        P2.hand.remove(c); enter(P2, T, 'serve', c, from_hand=True)
        op = cur_stat(P2, T, 'serve')
        v = evaluate(P2, op, T['locks'], T['trap'], opp)
        if best is None or v > best[0]: best = (v, P2, op, T['locks'], T['trap'])
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
            pl[other(cur)].pending_restrict, pl[other(cur)].pending_trap = locks, trap
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
                pl[other(cur)].pending_restrict, pl[other(cur)].pending_trap = locks, trap
            turns_log.append(dict(set=set_no, beat=beats, who=cur, act='LOSS', op=0))
        winner = other(loser); sets[winner] += 1
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
