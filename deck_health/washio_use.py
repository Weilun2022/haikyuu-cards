"""鷲尾 P01-051 實戰去向（描述統計，小樣本）：每次出場在哪裡、是哪種攔網、每拍手上有沒有鷲尾卻沒用。
用法：python -I washio_use.py <cards_data.js> <牌組.json> <N 每個對手> <對手1.json,對手2.json,...> <out.json>"""
import sys, os, json, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2
NO = 'HV-P01-051'
U = None
_enter = sim2.enter; _tt = sim2.take_turn


def enter(P, T, zone, card, from_hand, as_side_blocker=False, name=None, defer=None):
    if card.no == NO:
        P.bump('W位:' + ('side' if as_side_blocker else zone))
    return _enter(P, T, zone, card, from_hand, as_side_blocker, name, defer)


def tt(P, opp, op_in, src):
    k = sum(1 for c in P.hand if c.no == NO)
    before = dict(P.stats)
    res = _tt(P, opp, op_in, src)
    Pn = res[1]
    d = {key: v - before.get(key, 0) for key, v in Pn.stats.items() if v != before.get(key, 0)}
    act = next((key[3:] for key in d if key.startswith('行動:')), '?')
    used = {key[3:]: v for key, v in d.items() if key.startswith('W位:')}
    if k:
        Pn.bump('拍有鷲尾'); Pn.bump('拍鷲尾張數', k)
        if not used: Pn.bump('拍有鷲尾沒用:' + ('對手攻擊≥4' if src == 'attack' and op_in >= 4 else '其他'))
    Pn.bump('拍')
    if used:
        if act == 'onetouch': Pn.bump('用:一觸')
        elif 'block' in used or 'side' in used:
            Pn.bump('用:%s攔網(%s)' % ('單張' if act == 'block1' else '多張', '中間' if 'block' in used else '側邊'))
        else:
            for z in used: Pn.bump('用:填位' + z)
    return res


sim2.enter = enter; sim2.take_turn = tt


def init(path):
    global U
    U = sim2.load_cards(path)


def job(a):
    d, o, n, seed = a
    gs = sim2.match(U, d, o, n, seed=seed); st = {}
    for g in gs:
        for key, v in g['stats']['A'].items():
            if key.startswith(('W位:', '用:', '拍', '一觸')): st[key] = st.get(key, 0) + v
    return n, st


if __name__ == '__main__':
    path, df, N, opps, outf = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4].split(','), sys.argv[5]
    d = json.load(open(df)); out = {}
    with mp.Pool(int(os.environ.get('DH_WORKERS', '2')), initializer=init, initargs=(path,)) as pool:
        for of in opps:
            o = json.load(open(of))
            rs = pool.map(job, [(d, o, N // 2, 71), (d, o, N - N // 2, 83)])
            st = {}
            for _, r in rs:
                for key, v in r.items(): st[key] = st.get(key, 0) + v
            out[of] = dict(games=N, stats=st)
    json.dump(out, open(outf, 'w'), ensure_ascii=False, indent=1)
    for of, r in out.items():
        st, G = r['stats'], r['games']
        print('==', of, '每場')
        for key in sorted(st): print('  %s %.2f' % (key, st[key] / G))
