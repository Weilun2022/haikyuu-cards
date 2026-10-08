"""雙人對打的統計。用法：python -I report2.py <cards_data.js> <deckA.json> <deckB.json> [N]"""
import sys, os, json, time, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2


def summarize(games, side='A'):
    N = len(games)
    T = [t for g in games for t in g['turns']]
    mine = [t for t in T if t['who'] == side and t['act'] != 'LOSS']
    beats = collections.Counter()
    for g in games:
        per = collections.Counter(t['set'] for t in g['turns'])
        for s, n in per.items(): beats[min(n, 6)] += 1
    tot = sum(beats.values())
    st = collections.Counter()
    for g in games:
        for k, v in g['stats'][side].items(): st[k] += v
    att = [t['op'] for t in mine if t['act'] == 'receive']
    return dict(
        win=sum(g['winner'] == side for g in games) / N,
        sets_per_game=sum(g['set_no'] for g in games) / N,
        beats_dist={k: round(v / tot, 3) for k, v in sorted(beats.items())},
        deck_left=sum(g['deck_left'][side] for g in games) / N,
        block_rate=sum(1 for t in mine if t['act'].startswith('block')) / max(1, len(mine)),
        op_mean=sum(att) / max(1, len(att)),
        op_ge8=sum(1 for o in att if o >= 8) / max(1, len(att)),
        op_hist={k: round(v / len(att), 3) for k, v in sorted(collections.Counter(min(o, 12) for o in att).items())},
        per_game={k: round(v / N, 2) for k, v in sorted(st.items())},
    )


if __name__ == '__main__':
    U = sim2.load_cards(sys.argv[1]); A = json.load(open(sys.argv[2])); B = json.load(open(sys.argv[3]))
    N = int(sys.argv[4]) if len(sys.argv) > 4 else 500
    t0 = time.time()
    games = sim2.match(U, A, B, N)
    print(json.dumps(summarize(games, 'A'), ensure_ascii=False))
    print('time', round(time.time() - t0, 1))
