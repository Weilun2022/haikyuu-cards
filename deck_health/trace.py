"""印出一場對局的逐拍過程，人工檢查規則與技能是否被正確執行。"""
import sys, os, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim

U = sim.load_cards(sys.argv[1])
deck = json.load(open(sys.argv[2]))
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
rng = random.Random(seed)
L = sim.build_deck(U, deck)
log = []
g = sim.play_game(L, rng, log=log)
name = {no: U[no]['name_zh'] for no in deck}
for r, k, src, op, res, myop, hand, tops in log:
    t = {z: (name.get(v[0], v[0]) if v else '-') for z, v in tops.items()}
    print(f"Rally{r} 第{k}拍 對手{'發球' if src=='serve' else '攻擊'}{op} → {res} 我方進攻{myop} | 場上 接:{t['receive']} 舉:{t['toss']} 攻:{t['attack']} | 手牌{len(hand)}張")
print({k: v for k, v in g.items() if k not in ('turns', 'stats')})
print(json.dumps(g['stats'], ensure_ascii=False))
