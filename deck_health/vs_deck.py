"""多副牌各自對同一個對手牌組。用法：python -I vs_deck.py <cards_data.js> <對手.json> <N> <牌組1.json> [牌組2.json ...]"""
import sys, os, json, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2
U = None


def init(path):
    global U
    U = sim2.load_cards(path)


def job(a):
    d, o, n, seed = a
    return sum(g['winner'] == 'A' for g in sim2.match(U, d, o, n, seed=seed)), n


if __name__ == '__main__':
    path, oppf, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
    opp = json.load(open(oppf))
    with mp.Pool(2, initializer=init, initargs=(path,)) as pool:
        for f in sys.argv[4:]:
            d = json.load(open(f))
            rs = pool.map(job, [(d, opp, N // 2, 11), (d, opp, N - N // 2, 23)])
            w = sum(r[0] for r in rs); n = sum(r[1] for r in rs); p = w / n
            print(json.dumps(dict(deck=f, opp=oppf, win=round(p, 4), se=round((p * (1 - p) / n) ** .5, 4), n=n), ensure_ascii=False), flush=True)
