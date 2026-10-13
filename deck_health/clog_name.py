"""卡手分析（依人名）：每拍開始時手上某人名的張數 → 該拍 LOSS 率；另記開局（重抽後）手上張數。
用法：python -I clog_name.py <cards_data.js> <人名> <對手.json> <N> <牌組1.json> [牌組2.json ...]"""
import sys, os, json, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2
U = None; NAME = None
_tt = sim2.take_turn; _mull = sim2.mulligan


def tt(P, opp, op_in, src):
    k = min(sum(1 for c in P.hand if c.name == NAME), 4)
    res = _tt(P, opp, op_in, src)
    Pn = res[1]; Pn.bump('拍:%d' % k)
    if res[0] == 'loss': Pn.bump('LOSS:%d' % k)
    return res


def mull(P):
    _mull(P); P.bump('開局:%d' % min(sum(1 for c in P.hand if c.name == NAME), 4))


sim2.take_turn = tt; sim2.mulligan = mull


def init(path, name):
    global U, NAME
    U = sim2.load_cards(path); NAME = name


def job(a):
    d, o, n, seed = a
    gs = sim2.match(U, d, o, n, seed=seed); st = {}
    for g in gs:
        for k, v in g['stats']['A'].items():
            if k.startswith(('拍:', 'LOSS:', '開局:')): st[k] = st.get(k, 0) + v
    return sum(g['winner'] == 'A' for g in gs), n, st


if __name__ == '__main__':
    path, name, oppf, N = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    opp = json.load(open(oppf)); out = {}
    with mp.Pool(2, initializer=init, initargs=(path, name)) as pool:
        for f in sys.argv[5:]:
            d = json.load(open(f))
            rs = pool.map(job, [(d, opp, N // 2, 11), (d, opp, N - N // 2, 23)])
            st = {}
            for r in rs:
                for k, v in r[2].items(): st[k] = st.get(k, 0) + v
            T = sum(st.get('拍:%d' % k, 0) for k in range(5)); G = sum(st.get('開局:%d' % k, 0) for k in range(5))
            print(f, '勝率 %.1f%%' % (100 * sum(r[0] for r in rs) / N))
            for k in range(5):
                t = st.get('拍:%d' % k, 0); l = st.get('LOSS:%d' % k, 0)
                if t: print('  手上 %d 張%s：開局 %.1f%%｜佔 %.1f%% 的拍，那拍失分 %.1f%% ±%.1f%%' % (
                    k, '以上' if k == 4 else '', 100 * st.get('開局:%d' % k, 0) / G, 100 * t / T, 100 * l / t, 100 * (l / t * (1 - l / t) / t) ** .5))
            out[f] = st
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clog_name_raw.json'), 'w'), ensure_ascii=False)
