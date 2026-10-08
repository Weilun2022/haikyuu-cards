"""印出一場雙人對打的逐拍過程。用法：python -I trace2.py <cards_data.js> <deckA.json> <deckB.json> [seed]"""
import sys, os, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2

U = sim2.load_cards(sys.argv[1])
A = json.load(open(sys.argv[2])); B = json.load(open(sys.argv[3]))
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
log = []
g = sim2.play_game(sim2.build(U, A), sim2.build(U, B), random.Random(seed), log=log)
for s, beat, who, act, op, hand, deck in log:
    print(f"第{s}局 第{beat}拍 {who} {act:8s} 送出{op:>2}點 | 手牌{hand} 牌庫{deck}")
print('winner', g['winner'], g['sets'], 'deck_left', g['deck_left'])
for k in 'AB': print(k, json.dumps(g['stats'][k], ensure_ascii=False))
