"""卡手分析：每拍開始時手上木兎張數、該拍 LOSS 率。用法：python -I clog.py <cards_data.js> <N>
比較 V2 與 V2 的 P01-044 換成 P03-061（×2、×4），對手都是 V2。"""
import sys, os, json, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2
HERE = os.path.dirname(os.path.abspath(__file__))
U = None
_tt = sim2.take_turn


def tt(P, opp, op_in, src):
    k = min(sum(1 for c in P.hand if c.name == '木兎 光太郎'), 4)
    res = _tt(P, opp, op_in, src)
    Pn = res[1]
    Pn.bump('拍:%d' % k)
    if res[0] == 'loss': Pn.bump('LOSS:%d' % k)
    return res


sim2.take_turn = tt


def init(path):
    global U
    U = sim2.load_cards(path)


def job(a):
    deck, opp, n, seed = a
    gs = sim2.match(U, deck, opp, n, seed=seed)
    st = {}
    for g in gs:
        for k, v in g['stats']['A'].items():
            if k.startswith(('拍:', 'LOSS:', '技能:HV-P03-061')): st[k] = st.get(k, 0) + v
    return sum(g['winner'] == 'A' for g in gs), n, st


if __name__ == '__main__':
    path, N = sys.argv[1], int(sys.argv[2])
    v2 = json.load(open(os.path.join(HERE, 'fuku_op8_v2.json')))
    var = {'V2': v2}
    for k in (2, 4):
        d = dict(v2); d['HV-P01-044'] -= k; d['HV-P03-061'] = k
        if d['HV-P01-044'] == 0: d.pop('HV-P01-044')
        var['P01-044→P03-061×%d' % k] = d
    out = {}
    with mp.Pool(2, initializer=init, initargs=(path,)) as pool:
        for name, d in var.items():
            rs = pool.map(job, [(d, v2, N // 2, 11), (d, v2, N - N // 2, 23)])
            w = sum(r[0] for r in rs); n = sum(r[1] for r in rs); st = {}
            for r in rs:
                for k, v in r[2].items(): st[k] = st.get(k, 0) + v
            out[name] = dict(win=w / n, n=n, stats=st)
            print(name, round(w / n, 4), flush=True)
    json.dump(out, open(os.path.join(HERE, 'clog_raw.json'), 'w'), ensure_ascii=False, indent=1)
