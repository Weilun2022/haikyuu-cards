# 第 4 批（稲荷崎、伊達工業、白鳥沢）煙霧測試：每張卡都被放進牌組實際對打，不能丟例外；並統計哪些卡真的有觸發
import os, sys, random, json, collections
os.environ['DH_BATCH4'] = '1'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
from manual_batch4 import MANUAL_BATCH4
U = sim2.load_cards(os.path.join(HERE, '..', 'cards_data.js'))
fails = []
def ok(m, c):
    print(('OK   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
ok('第 4 批 %d 張全在卡庫' % len(MANUAL_BATCH4), all(k in U for k in MANUAL_BATCH4))
ok('第 4 批全部已進 MANUAL', all(k in sim2.MANUAL for k in MANUAL_BATCH4))
base = json.load(open(os.path.join(HERE, 'deck.json'), encoding='utf8'))
opps = [json.load(open(os.path.join(HERE, f), encoding='utf8')) for f in ('deck.json', 'fuku_op8_v2.json')]
cards = sorted(MANUAL_BATCH4)
bad = []
for k in cards:
    # 把該卡 4 張放進牌組，其餘用 deck.json 同類卡補到 40 張、事件 ≤8
    d = dict(base); need = 4
    for no in list(d):
        if need == 0 or no == k: continue
        same = U[no]['category'] == U[k]['category']
        if same:
            t = min(d[no], need); d[no] -= t; need -= t
            if d[no] == 0: del d[no]
    d[k] = d.get(k, 0) + (4 - need)
    n_ev = sum(n for no, n in d.items() if U[no]['category'] == 'EVENT')
    if sum(d.values()) != 40 or n_ev > 8: bad.append(k + ' 組牌失敗'); continue
    try:
        for o in opps: sim2.match(U, d, o, 12, seed=5)
    except Exception as e:
        bad.append('%s %r' % (k, e))
ok('逐張煙霧測試（%d 張 × 2 對手 × 12 場）無例外' % len(cards), not bad)
for b in bad: print('   ', b)
print('FAILED: %d' % len(fails))
