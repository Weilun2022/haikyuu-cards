"""P01-043 卡手分析：每拍開始時手上 P01-043 張數 → 該拍 LOSS 率；P01-043 上場攻擊時拿到 +5 的比例。
用法：python -I clog043.py <cards_data.js> <對手.json> <N> <牌組1.json> [牌組2.json ...]"""
import sys, os, json, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2
U = None
NO = 'HV-P01-043'
_tt = sim2.take_turn
_enter = sim2.enter


def tt(P, opp, op_in, src):
    k = min(sum(1 for c in P.hand if c.no == NO), 3)
    res = _tt(P, opp, op_in, src)
    Pn = res[1]; Pn.bump('拍:%d' % k)
    if res[0] == 'loss': Pn.bump('LOSS:%d' % k)
    return res


def enter(P, T, zone, card, from_hand, as_side_blocker=False, name=None):
    before = P.stats.get('技能:' + NO, 0)
    r = _enter(P, T, zone, card, from_hand, as_side_blocker, name)
    if card.no == NO and not as_side_blocker:
        P.bump('上場:' + zone)
        if zone == 'attack': P.bump('攻擊+5' if P.stats.get('技能:' + NO, 0) > before else '攻擊沒+5')
    return r


sim2.take_turn = tt; sim2.enter = enter


def init(path):
    global U
    U = sim2.load_cards(path)


def job(a):
    d, o, n, seed = a
    gs = sim2.match(U, d, o, n, seed=seed); st = {}
    for g in gs:
        for k, v in g['stats']['A'].items():
            if k.startswith(('拍:', 'LOSS:', '上場:', '攻擊')): st[k] = st.get(k, 0) + v
    return sum(g['winner'] == 'A' for g in gs), n, st


if __name__ == '__main__':
    path, oppf, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
    opp = json.load(open(oppf)); out = {}
    with mp.Pool(2, initializer=init, initargs=(path,)) as pool:
        for f in sys.argv[4:]:
            d = json.load(open(f))
            rs = pool.map(job, [(d, opp, N // 2, 11), (d, opp, N - N // 2, 23)])
            st = {}
            for r in rs:
                for k, v in r[2].items(): st[k] = st.get(k, 0) + v
            w = sum(r[0] for r in rs); n = sum(r[1] for r in rs)
            out[f] = dict(win=w / n, n=n, stats=st); print(f, round(w / n, 4), flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clog043_raw.json'), 'w'), ensure_ascii=False, indent=1)
