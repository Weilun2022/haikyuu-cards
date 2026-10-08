"""牌組健檢：基準指標 + 每張卡 ±1 張比較。
用法：python -I report.py <cards_data.js> <deck.json> [N] [N_variant]"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim


def metrics(games):
    N = len(games)
    T = [t for g in games for t in g['turns']]
    ok = [t for t in T if t['res'] == 'ok']
    def rate(f, xs): return sum(1 for x in xs if f(x)) / max(1, len(xs))
    st = {}
    for g in games:
        for k, v in g['stats'].items(): st[k] = st.get(k, 0) + v
    m = dict(
        win=rate(lambda g: g['win'], games),
        deck_left=sum(g['deck_left'] for g in games) / N,
        rallies=sum(g['rallies'] for g in games) / N,
        rcv_ok_5=rate(lambda t: t['res'] == 'ok', [t for t in T if t['opp'] == 5 and t['src'] == 'attack']),
        rcv_ok_9=rate(lambda t: t['res'] == 'ok', [t for t in T if t['opp'] == 9]),
        op_mean=sum(t['op'] for t in ok) / max(1, len(ok)),
        op7=rate(lambda t: t['op'] >= 7, ok), op8=rate(lambda t: t['op'] >= 8, ok),
        op9=rate(lambda t: t['op'] >= 9, ok), op10=rate(lambda t: t['op'] >= 10, ok),
        score_beat=rate(lambda t: t['scored'], ok),
        lock=rate(lambda t: t['locks'], ok),
        per_game={k: v / N for k, v in st.items()},
    )
    # 每個 Rally 第 1 拍就得分的機率（看 Guts 累積後是否越打越強）
    by_r = {}
    for t in T:
        by_r.setdefault(t['rally'], []).append(t['scored'])
    m['first_beat_score_by_rally'] = {r: sum(v) / len(v) for r, v in sorted(by_r.items()) if len(v) >= 50}
    return m


if __name__ == '__main__':
    U = sim.load_cards(sys.argv[1]); deck = json.load(open(sys.argv[2]))
    N = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
    NV = int(sys.argv[4]) if len(sys.argv) > 4 else 400
    t0 = time.time()
    base = metrics(sim.run(U, deck, N))
    print('BASE', json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in base.items() if k != 'per_game'}, ensure_ascii=False))
    print('PER_GAME', json.dumps({k: round(v, 2) for k, v in sorted(base['per_game'].items())}, ensure_ascii=False))
    print('time', round(time.time() - t0, 1))
    if NV:
        filler = 'HV-P03-052'  # 田中龍之介（使用者手上有 3 張的備用卡）當替換基準
        out = {}
        bvar = metrics(sim.run(U, deck, NV, seed=99))
        out['_base_same_seed'] = bvar
        for no in deck:
            d = dict(deck); d[no] -= 1
            if d[no] == 0: d.pop(no)
            d[filler] = d.get(filler, 0) + 1
            out['-' + no] = metrics(sim.run(U, d, NV, seed=99))
            if no != 'HVBP-001':
                d2 = dict(deck); d2[no] += 1; d2['HVBP-001'] -= 1
                if d2['HVBP-001'] == 0: d2.pop('HVBP-001')
                out['+' + no] = metrics(sim.run(U, d2, NV, seed=99))
        json.dump(out, open('variants.json', 'w', encoding='utf-8'), ensure_ascii=False)
        print('variants done', round(time.time() - t0, 1))
