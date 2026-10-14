"""連續打 8 統計：同一局內，自己每次「接球→攻擊」的進攻值序列，算 ≥8 的最長連續次數；並記錄攻擊前舉球區＋攻擊區的 Guts 數。
用法：python -I streak8.py <cards_data.js> <對手.json> <N> <牌組1.json> [牌組2.json ...]
攔網回合不算攻擊、不中斷連續；失分（局結束）中斷。"""
import sys, os, json, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2
U = None
SEQ = []          # 本場 A 的 (set, guts_before, op)
_tt = sim2.take_turn
_pg = sim2.play_game


def tt(P, opp, op_in, src):
    g = sum(max(0, len(P.zones[z]) - 1) for z in ('toss', 'attack'))
    res = _tt(P, opp, op_in, src)
    if P.label == 'A' and res[0] == 'ok' and res[6] in ('receive', 'receive2', 'onetouch'):
        SEQ.append((CUR_SET[0], g, res[2]))
    return res


CUR_SET = [0]
_serve = sim2.serve_turn


def serve(P, opp):
    if P.label == 'A' or True: CUR_SET[0] += 1
    return _serve(P, opp)


sim2.take_turn = tt; sim2.serve_turn = serve


def init(path):
    global U
    U = sim2.load_cards(path)


def job(a):
    d, o, n, seed = a
    import random
    rng = random.Random(seed)
    A, B = sim2.build(U, d), sim2.build(U, o)
    out = dict(games=0, wins=0, attacks=0, eights=0, maxrun={}, maxrun_game={}, g_hist={})
    for _ in range(n):
        SEQ.clear(); CUR_SET[0] = 0
        r = sim2.play_game(A, B, rng)
        out['games'] += 1; out['wins'] += r['winner'] == 'A'
        best = run = 0; last = None; bg = rg = 0
        for s, g, op in SEQ:
            rg = rg + 1 if op >= 8 else 0; bg = max(bg, rg)   # 整場連續（跨局；Guts 跨局保留）
            if s != last: run = 0; last = s
            out['attacks'] += 1
            gk = min(g, 12); h = out['g_hist'].setdefault(gk, [0, 0]); h[0] += 1
            if op >= 8:
                out['eights'] += 1; h[1] += 1; run += 1; best = max(best, run)
            else: run = 0
        out['maxrun'][best] = out['maxrun'].get(best, 0) + 1
        out['maxrun_game'][bg] = out['maxrun_game'].get(bg, 0) + 1
    return out


def merge(a, b):
    for k in ('games', 'wins', 'attacks', 'eights'): a[k] += b[k]
    for k, v in b['maxrun'].items(): a['maxrun'][k] = a['maxrun'].get(k, 0) + v
    for k, v in b['maxrun_game'].items(): a['maxrun_game'][k] = a['maxrun_game'].get(k, 0) + v
    for k, v in b['g_hist'].items():
        h = a['g_hist'].setdefault(k, [0, 0]); h[0] += v[0]; h[1] += v[1]
    return a


if __name__ == '__main__':
    path, oppf, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
    opp = json.load(open(oppf)); res = {}
    so = int(os.environ.get('DH_SEED_OFFSET', '0'))
    with mp.Pool(2, initializer=init, initargs=(path,)) as pool:
        for f in sys.argv[4:]:
            d = json.load(open(f))
            rs = pool.map(job, [(d, opp, N // 2, 101 + so), (d, opp, N - N // 2, 202 + so)])
            m = rs[0]
            for r in rs[1:]: m = merge(m, r)
            G = m['games']; mr = m['maxrun']
            ge = lambda k: sum(v for kk, v in mr.items() if int(kk) >= k) / G
            gg = lambda k: sum(v for kk, v in m['maxrun_game'].items() if int(kk) >= k) / G
            line = dict(deck=f, opp=oppf, n=G, win=round(m['wins'] / G, 4), atk_per_game=round(m['attacks'] / G, 2),
                        eight_rate=round(m['eights'] / max(1, m['attacks']), 4), eights_per_game=round(m['eights'] / G, 2),
                        set_run2=round(ge(2), 4), set_run3=round(ge(3), 4), game_run2=round(gg(2), 4), game_run3=round(gg(3), 4), game_run5=round(gg(5), 4))
            print(json.dumps(line, ensure_ascii=False), flush=True)
            res[f] = dict(line, g_hist={k: v for k, v in sorted(m['g_hist'].items())})
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'streak8_raw.json'), 'w'), ensure_ascii=False, indent=1)
