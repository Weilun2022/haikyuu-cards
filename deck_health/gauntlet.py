"""多副牌 vs 多個對手的勝率表。用法：python -I gauntlet.py <cards_data.js> <base.json> <variants.json> <opp1.json,opp2.json> <N> <out.jsonl>
variants.json 格式同 compare2.py；每組 (方案, 對手) 用 2 個 process、固定種子，各方案共用同一組種子（配對比較）。"""
import sys, os, json, time, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2
from compare2 import apply

U = None


def init(path):
    global U
    U = sim2.load_cards(path)


def job(args):
    a, b, n, seed = args
    return sum(g['winner'] == 'A' for g in sim2.match(U, a, b, n, seed=seed)), n


if __name__ == '__main__':
    path, basef, varf, opps, N, outf = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(','), int(sys.argv[5]), sys.argv[6]
    base = json.load(open(basef)); V = json.load(open(varf))
    with mp.Pool(2, initializer=init, initargs=(path,)) as pool, open(outf, 'a', encoding='utf-8') as fo:
        for name, v in V.items():
            d = apply(base, v)
            for of in opps:
                t0 = time.time(); o = json.load(open(of))
                so = int(os.environ.get('DH_SEED_OFFSET', '0'))  # 換種子複驗；預設 0 = 舊結果可重現
                res = pool.map(job, [(d, o, N // 2, 31 + so), (d, o, N - N // 2, 47 + so)])
                w = sum(r[0] for r in res); n = sum(r[1] for r in res); p = w / n
                rec = dict(v=name, opp=of, win=round(p, 4), se=round((p * (1 - p) / n) ** 0.5, 4), n=n, sec=round(time.time() - t0))
                fo.write(json.dumps(rec, ensure_ascii=False) + '\n'); fo.flush()
