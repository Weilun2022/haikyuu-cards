"""單人連續抽牌模擬（抽牌器）：不需要真的對手，依實戰節奏一路抽牌、接球、舉球、攻擊，
量測「指定組合技」的達成率與攻守穩定度。技能照 manual_cards 結構化效果執行（沿用 sim2 引擎）。

對手以使用者描述的節奏代表：發球 1～3 點為主、偶爾 5 點；攻擊一般 5 點，每第 4 次攻擊 9 點；
我方進攻 ≥ 8～10（隨機）就得分；對手一分最多接我方 2 次攻擊（手牌經濟推算）。
"""
import random, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2

OPP = dict(serve=[(1, .3), (2, .3), (3, .3), (5, .1)], attack=5, spike=9, spike_every=4,
           defend=[8, 9, 10], max_receives=2, hand=4)


def _dummy_opp(rng):
    o = sim2.Player([], rng, 'O')
    blank = sim2.Card(dict(card_no='DUMMY', name='對手', category='CHARACTER', position='-', school='-',
                           school_tags=['-'], srv=0, blk=0, rcv=0, tos=0, atk=0))
    o.hand = [blank] * OPP['hand']; o.setz = [blank, blank]
    return o


def combo_hit(P, T, op, goal):
    if not goal: return False
    tz, az = P.zones['toss'], P.zones['attack']
    if goal.get('toss') and (not tz or tz[-1].name != goal['toss']): return False
    if goal.get('attack') and (not az or az[-1].name != goal['attack']): return False
    return op >= goal.get('op', 0) and T.get('two_attack') is None


def line_options(Pd, opp, op_in, src, goal):
    """列舉接球→舉球→攻擊（含二段攻擊）的所有合法打法。"""
    out = []
    ch = [c for c in Pd.hand if not c.ev]
    rc = [c for c in ch if sim2.can_enter(Pd, 'receive', c)]
    rc.sort(key=lambda c: (sim2.keep_value(c), -c.b['rcv']))
    seen = set()
    for r in rc[:4]:
        for t in ch:
            if t is r or t.name == r.name: continue
            modes = [('two', None)]
            modes += [(m, a) for a in ch if a is not r and a is not t and a.name != t.name for m in (True, False)]
            for mode, a in modes:
                key = (r.no, t.no, a.no if a else None, mode)
                if key in seen: continue
                seen.add(key)
                P2 = Pd.clone(); T = sim2.newT(opp, op_in, src)
                op = sim2.do_receive_line(P2, T, r, t, a, mode)
                if op is None: continue
                out.append((P2, T, op, combo_hit(P2, T, op, goal)))
    return out


def choose(options, goal):
    # 優先：打出指定組合 → 進攻值高（≥8 視為得分機會）→ 保留手牌
    return max(options, key=lambda o: (o[3], o[2] >= 8, sim2.hand_score(o[0].hand) + o[2]))


def my_turn(P, opp, op_in, src, goal):
    P.restrict, P.trap = P.pending_restrict, P.pending_trap
    P.pending_restrict, P.pending_trap = [], False
    opts = []
    Pd = P.clone(); Pd.draw(1)
    opts += [o + ('receive',) for o in line_options(Pd, opp, op_in, src, goal)]
    if not opts and op_in >= 4:  # 接不住時才用一觸
        chars = [c for c in P.hand if not c.ev]
        for c in {x.no: x for x in chars if sim2.onetouch_n(x)}.values():
            P2 = P.clone(); T = sim2.newT(opp, op_in, src); T['phase'] = 'block'
            P2.hand.remove(c); sim2.enter(P2, T, 'block', c, from_hand=True)
            if T.get('onetouch'):
                P2.draw(1)
                opts += [o + ('onetouch',) for o in line_options(P2, opp, op_in - T['onetouch'], src, goal)]
    if not opts: return None
    P2, T, op, hit, act = choose(opts, goal)
    P2.bump('行動:' + act)
    return P2, T, op, hit


def play(cards, rng, goal, max_points=5):
    P = sim2.Player(cards, rng, 'A'); opp = _dummy_opp(rng)
    sim2.mulligan(P)
    P.setz = [P.deck.pop(0), P.deck.pop(0)]
    rec = dict(attacks=[], hits=[], rcv5=[], rallies=[])
    lost = won = 0; opp_attacks = 0
    while lost < 3 and won < 3 and (P.deck or P.hand):
        beat = 0; first_hit = None; rally_hits = 0
        op_in = rng.choices([v for v, _ in OPP['serve']], [w for _, w in OPP['serve']])[0]; src = 'serve'
        opp_left = OPP['max_receives']; result = None
        while True:
            beat += 1
            r = my_turn(P, opp, op_in, src, goal)
            if src == 'attack' and op_in == OPP['attack']: rec['rcv5'].append(r is not None)
            if r is None: result = 'lost'; break
            P, T, op, hit = r
            rec['attacks'].append(op); rec['hits'].append(hit)
            if hit:
                rally_hits += 1
                if first_hit is None: first_hit = beat
            need = rng.choice(OPP['defend']) - (1 if T['locks'] else 0)
            if op >= need: result = 'won'; break
            opp_left -= 1
            if opp_left < 0: result = 'won'; break
            opp_attacks += 1
            op_in = OPP['spike'] if opp_attacks % OPP['spike_every'] == 0 else OPP['attack']; src = 'attack'
            P.pending_restrict = []  # 對手的限制效果不模擬
        rec['rallies'].append(dict(hit=rally_hits > 0, first=first_hit, result=result, beats=beat))
        while len(P.hand) < 6 and P.deck: P.draw(1)
        if result == 'lost':
            lost += 1
            if P.setz: P.hand.append(P.setz.pop(0))
        else: won += 1
    rec['deck_left'] = len(P.deck); rec['stats'] = P.stats
    return rec


def evaluate(U, deck, goal, N=200, seed=1):
    rng = random.Random(seed)
    cards = sim2.build(U, deck)
    R = [play(cards, rng, goal) for _ in range(N)]
    att = [a for r in R for a in r['attacks']]
    hits = [h for r in R for h in r['hits']]
    rv = [x for r in R for x in r['rcv5']]
    ral = [x for r in R for x in r['rallies']]
    firsts = [x['first'] for x in ral if x['first']]
    return dict(
        combo_rate=sum(hits) / max(1, len(hits)),
        rally_combo=sum(x['hit'] for x in ral) / max(1, len(ral)),
        first_beat=sum(firsts) / max(1, len(firsts)) if firsts else None,
        mean_op=sum(att) / max(1, len(att)),
        op8=sum(a >= 8 for a in att) / max(1, len(att)),
        rcv5=sum(rv) / max(1, len(rv)),
        point_win=sum(x['result'] == 'won' for x in ral) / max(1, len(ral)),
        n_attacks=len(att),
    )


if __name__ == '__main__':
    U = sim2.load_cards(sys.argv[1]); deck = json.load(open(sys.argv[2]))
    goal = json.loads(sys.argv[3]) if len(sys.argv) > 3 else dict(toss='赤葦 京治', attack='木兎 光太郎', op=8)
    import time; t0 = time.time()
    print(json.dumps(evaluate(U, deck, goal, int(os.environ.get('N', 200))), ensure_ascii=False), round(time.time() - t0, 1), 's')
