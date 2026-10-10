"""有對打底線的目標導向換牌。
用法：python -I optimize_guard.py <cards_data.js> <start.json> <config.json> <out.jsonl>
config 範例：
{"school": "梟谷", "metric": "op8", "goal": {...},
 "guard": {"opponent": "fuku_c2.json", "min": 0.48, "n": 1000},
 "steps": 14, "n_screen": 150, "n_confirm": 800, "top": 6}
每一步：
1. 所有「換 1 張」用單人模擬粗篩（n_screen 場，共同亂數），取指標最高的前 top 個
2. 這些候選用單人模擬 n_confirm 場複查指標，並與 guard 對手對打 guard.n 場
3. 只在「指標比目前高」且「對打勝率 ≥ guard.min」的候選中選指標最高者
最後一步之後，由使用者另外用大樣本複查。"""
import sys, os, json, time, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2, solo, optimize

U = None


def init(path):
    global U
    U = sim2.load_cards(path)


def ev_solo(args):
    deck, goal, n, seed = args
    return solo.evaluate(U, deck, goal, n, seed)


def ev_h2h(args):
    deck, opp, n, seed = args
    gs = sim2.match(U, deck, opp, n, seed=seed)
    return sum(g['winner'] == 'A' for g in gs), n


if __name__ == '__main__':
    path, startf, cfgf, outf = sys.argv[1:5]
    cfg = json.load(open(cfgf, encoding='utf-8')); deck = json.load(open(startf))
    opp = json.load(open(cfg['guard']['opponent']))
    Ul = sim2.load_cards(path); pool = optimize.pool_for(Ul, cfg['school'])
    goal, metric, g = cfg['goal'], cfg['metric'], cfg['guard']

    def h2h(P, decks, seed):
        jobs = [(d, opp, g['n'] // 2, seed + i * 10 + k) for i, d in enumerate(decks) for k in range(2)]
        res = P.map(ev_h2h, jobs)
        return [(res[2 * i][0] + res[2 * i + 1][0]) / g['n'] for i in range(len(decks))]

    with mp.Pool(2, initializer=init, initargs=(path,)) as P, open(outf, 'a', encoding='utf-8') as fo:
        cur = deck
        cur_m = P.map(ev_solo, [(cur, goal, cfg['n_confirm'], 777)])[0]
        cur_h = h2h(P, [cur], 900)[0]
        fo.write(json.dumps(dict(step=0, deck=cur, m=cur_m, h2h=cur_h, pool=pool), ensure_ascii=False) + '\n'); fo.flush()
        for step in range(1, cfg['steps'] + 1):
            t0 = time.time()
            nb = list(optimize.neighbors(cur, pool, Ul))
            res = P.map(ev_solo, [(d, goal, cfg['n_screen'], 1000 + step) for _, d in nb])
            base_s = P.map(ev_solo, [(cur, goal, cfg['n_screen'], 1000 + step)])[0][metric]
            ranked = sorted(zip(nb, res), key=lambda x: -x[1][metric])
            ranked = [x for x in ranked if x[1][metric] > base_s][:cfg['top']]
            if not ranked:
                fo.write(json.dumps(dict(step=step, stop='粗篩沒有更好的換法'), ensure_ascii=False) + '\n'); break
            decks = [d for (_, d), _ in ranked]
            conf = P.map(ev_solo, [(d, goal, cfg['n_confirm'], 5000 + step) for d in decks] + [(cur, goal, cfg['n_confirm'], 5000 + step)])
            cur_c = conf[-1][metric]
            hs = h2h(P, decks, 7000 + step * 100)
            cands = [(m[metric], h, mv, d, m) for ((mv, d), _), m, h in zip(ranked, conf[:-1], hs)
                     if m[metric] > cur_c and h >= g['min']]
            log = [dict(move=mv, metric=round(m[metric], 4), h2h=round(h, 3)) for ((mv, _), _), m, h in zip(ranked, conf[:-1], hs)]
            if not cands:
                fo.write(json.dumps(dict(step=step, stop='沒有同時滿足指標進步與對打底線的換法', tried=log), ensure_ascii=False) + '\n'); break
            _, h, mv, d, m = max(cands, key=lambda x: (x[0], x[1]))
            cur, cur_m, cur_h = d, m, h
            fo.write(json.dumps(dict(step=step, move=mv, deck=cur, m=cur_m, h2h=cur_h, tried=log, sec=round(time.time() - t0)), ensure_ascii=False) + '\n'); fo.flush()
