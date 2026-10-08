"""換卡方案 vs 原牌組 對打勝率。用法：python -I compare2.py <cards_data.js> <base.json> <variants.json> <N> <out.jsonl>
variants.json: {"方案名": {"out": {"卡號": 張數}, "in": {"卡號": 張數}}, ...}
雙方先後手隨機；每個方案用 2 個 process 平行。"""
import sys, os, json, time, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2

U = None


def init(path):
    global U
    U = sim2.load_cards(path)


def job(args):
    a, b, n, seed = args
    gs = sim2.match(U, a, b, n, seed=seed)
    return sum(g['winner'] == 'A' for g in gs), n, sum(g['deck_left']['A'] for g in gs)


def apply(base, v):
    d = dict(base)
    for k, n in v.get('out', {}).items():
        d[k] -= n
        if d[k] == 0: d.pop(k)
    for k, n in v.get('in', {}).items(): d[k] = d.get(k, 0) + n
    assert sum(d.values()) == 40, (v, sum(d.values()))
    return d


if __name__ == '__main__':
    path, basef, varf, N, outf = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
    base = json.load(open(basef)); V = json.load(open(varf))
    with mp.Pool(2, initializer=init, initargs=(path,)) as pool, open(outf, 'a', encoding='utf-8') as fo:
        for name, v in V.items():
            t0 = time.time(); d = apply(base, v)
            res = pool.map(job, [(d, base, N // 2, 11), (d, base, N - N // 2, 23)])
            w = sum(r[0] for r in res); n = sum(r[1] for r in res)
            p = w / n; se = (p * (1 - p) / n) ** 0.5
            rec = dict(v=name, win=round(p, 4), se=round(se, 4), n=n, sec=round(time.time() - t0))
            fo.write(json.dumps(rec, ensure_ascii=False) + '\n'); fo.flush()
            print(json.dumps(rec, ensure_ascii=False), flush=True)
