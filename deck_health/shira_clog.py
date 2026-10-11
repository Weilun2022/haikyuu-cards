"""白鳥沢卡手分析：每拍開始時手上牛島張數 → 該拍 LOSS 率。
用法：DH_SHIRA=1 python -I shira_clog.py <cards_data.js> <N>
比較原版（牛島 9）、P03-067×2（11）、×3（12），對手：烏野 deck.json、梟谷 fuku_op8_v2.json。"""
import sys, os, json, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2
HERE = os.path.dirname(os.path.abspath(__file__))
U = None
_tt = sim2.take_turn
NAME = '牛島 若利'


def tt(P, opp, op_in, src):
    k = min(sum(1 for c in P.hand if c.name == NAME), 4)
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
            if k.startswith(('拍:', 'LOSS:')): st[k] = st.get(k, 0) + v
    return st


if __name__ == '__main__':
    path, N = sys.argv[1], int(sys.argv[2])
    L = lambda f: json.load(open(os.path.join(HERE, f)))
    decks = {'原版(牛島9)': L('shira.json'), '067×2(牛島11)': L('shira_067x2.json'), '067×3(牛島12)': L('shira_067x3.json')}
    opps = {'烏野': L('deck.json'), '梟谷V2': L('fuku_op8_v2.json')}
    out = []
    with mp.Pool(2, initializer=init, initargs=(path,)) as pool:
        for dn, d in decks.items():
            tot = {}
            for on, o in opps.items():
                for st in pool.map(job, [(d, o, N // 2, 61), (d, o, N - N // 2, 67)]):
                    for k, v in st.items(): tot[k] = tot.get(k, 0) + v
            beats = sum(v for k, v in tot.items() if k.startswith('拍:'))
            row = dict(deck=dn, beats=beats, loss_rate=round(sum(v for k, v in tot.items() if k.startswith('LOSS:')) / beats, 4))
            for k in range(5):
                b = tot.get('拍:%d' % k, 0); l = tot.get('LOSS:%d' % k, 0)
                row['k%d' % k] = dict(share=round(b / beats, 3), loss=round(l / b, 3) if b else None, n=b)
            out.append(row); print(json.dumps(row, ensure_ascii=False), flush=True)
    json.dump(out, open(os.path.join(HERE, 'shira_clog_raw.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
