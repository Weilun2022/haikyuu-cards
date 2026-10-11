"""P03-061 濾牌公平性檢查：預設棄牌 vs 聰明棄牌（先棄 P01-044，再棄 P03-061，最後才棄 P01-043），並記錄 P03-061 上場狀況。
用法：python -I p03061.py <cards_data.js> <N>"""
import sys, os, json, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2
HERE = os.path.dirname(os.path.abspath(__file__))
U = None; SMART = False  # False / True / 'clog'（只在卡手時濾：手上還有 ≥2 張木兎才發動）
PRI = {'HV-P01-044': 0, 'HV-P03-061': 1, 'HV-P01-043': 2}
_cost_pay = sim2.cost_pay
_enter = sim2.enter


def cost_pay(costs, P, T, zone):
    dn = [c for c in costs if c['type'] == 'discard_named']
    if SMART and dn:
        c = dn[0]; hs = [x for x in P.hand if x.name == c['name']]
        if len(hs) < c['n']: return False
        if SMART == 'clog' and len(hs) < 2: return False
        rest = [x for x in costs if x is not c]
        P2 = P.clone()
        if not _cost_pay(rest, P2, T, zone): return False
        w = min(hs, key=lambda x: PRI.get(x.no, 1)); P.hand.remove(w); P.drop.append(w); P.bump('棄:' + w.no)
        return _cost_pay(rest, P, T, zone)
    if dn:
        hs = [x for x in P.hand if x.name == dn[0]['name']]
        if hs: P.bump('棄:' + min(hs, key=sim2.keep_value).no)
    return _cost_pay(costs, P, T, zone)


def enter(P, T, zone, card, from_hand, as_side_blocker=False, name=None):
    before = P.stats.get('技能:HV-P03-061', 0)
    r = _enter(P, T, zone, card, from_hand, as_side_blocker, name)
    if card.no == 'HV-P03-061' and not as_side_blocker:
        used = P.stats.get('技能:HV-P03-061', 0) > before
        P.bump('061:%s:%s' % (zone, '濾牌' if used else '沒濾'))
    if zone == 'attack' and not as_side_blocker:
        P.bump('攻擊值:%s:n' % card.no); P.bump('攻擊值:%s:sum' % card.no, sim2.cur_stat(P, T, 'attack'))
    return r


sim2.cost_pay = cost_pay; sim2.enter = enter


def init(path, smart):
    global U, SMART
    U = sim2.load_cards(path); SMART = smart


def job(a):
    deck, opp, n, seed = a
    gs = sim2.match(U, deck, opp, n, seed=seed); st = {}
    for g in gs:
        for k, v in g['stats']['A'].items():
            if k.startswith(('061:', '棄:', '攻擊值:', '技能:HV-P03-061')): st[k] = st.get(k, 0) + v
    return sum(g['winner'] == 'A' for g in gs), n, st


if __name__ == '__main__':
    path, N = sys.argv[1], int(sys.argv[2])
    v2 = json.load(open(os.path.join(HERE, 'fuku_op8_v2.json')))
    out = {}
    modes = sys.argv[3].split(',') if len(sys.argv) > 3 else ['default', 'smart']
    for k in (2, 4):
        d = dict(v2); d['HV-P01-044'] -= k; d['HV-P03-061'] = k
        if d['HV-P01-044'] == 0: d.pop('HV-P01-044')
        for mode in modes:
            smart = dict(default=False, smart=True, clog='clog')[mode]
            name = 'P03-061×%d %s' % (k, dict(default='預設棄牌', smart='聰明棄牌', clog='只在卡手時濾')[mode])
            with mp.Pool(2, initializer=init, initargs=(path, smart)) as pool:
                rs = pool.map(job, [(d, v2, N // 2, 11), (d, v2, N - N // 2, 23)])
            w = sum(r[0] for r in rs); n = sum(r[1] for r in rs); st = {}
            for r in rs:
                for kk, v in r[2].items(): st[kk] = st.get(kk, 0) + v
            out[name] = dict(win=w / n, n=n, stats=st); print(name, round(w / n, 4), flush=True)
    json.dump(out, open(os.path.join(HERE, 'p03061_%s_raw.json' % '_'.join(modes)), 'w'), ensure_ascii=False, indent=1)
