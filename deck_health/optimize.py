"""目標導向自動換牌：從可用卡池反覆嘗試「換 1 張」，保留讓目標變好、且不破底線的換法。
用法：python -I optimize.py <cards_data.js> <start.json> <config.json> <out.jsonl>
config: {"school": "梟谷", "goal": {...}, "objective": "combo"|"mean_op",
         "rcv5_floor_drop": 0.02, "steps": 12, "n_screen": 150, "n_confirm": 800}
每一步：所有換法用 n_screen 場粗篩（共同亂數），前 4 名與目前牌組用 n_confirm 場複查，有進步才採用。"""
import sys, os, json, time, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parallel, sim2, solo
from manual_cards import MANUAL

U = None


def init(path):
    global U
    U = sim2.load_cards(path)


def ev(args):
    deck, goal, n, seed = args
    return solo.evaluate(U, deck, goal, n, seed)


def pool_for(U, school, extra_no_skill=False):
    """換牌候選卡池。school：單一學校（字串）、學校清單、或 '*'（全部學校）。
    extra_no_skill=True：除了指定學校，再加入「所有學校的無技能卡」（混校用：無技能卡不需結構化，可直接跨校）。
    技能卡必須已在 MANUAL（未結構化／未驗收的不放進搜尋；DH_MIXED、DH_P04 等環境變數載入的草稿卡只在該旗標開啟時才在 MANUAL）。"""
    schools = None if school == '*' else ({school} if isinstance(school, str) else set(school))
    out = []
    for c in U.values():
        skilled = c['skill_jp'] not in ('-', '')
        in_school = schools is None or bool(schools & set(c.get('school_tags') or []))
        if not in_school and not (extra_no_skill and not skilled): continue
        if skilled and c['card_no'] not in MANUAL: continue  # 未結構化的技能卡不放進搜尋
        out.append(c['card_no'])
    return sorted(out)


def score(m, cfg, floor):
    s = m['combo_rate'] + 0.01 * m['mean_op'] if cfg['objective'] == 'combo' else m['mean_op'] + 0.5 * m['combo_rate']
    if m['rcv5'] < floor: s -= 10 * (floor - m['rcv5']) + 1  # 破底線重罰
    return s


def neighbors(deck, pool, U):
    n_ev = lambda d: sum(n for k, n in d.items() if U[k]['category'] == 'EVENT')
    for out in list(deck):
        for inn in pool:
            if inn == out: continue
            d = dict(deck); d[out] -= 1
            if d[out] == 0: d.pop(out)
            d[inn] = d.get(inn, 0) + 1
            if n_ev(d) > 8: continue
            yield (out, inn), d


if __name__ == '__main__':
    path, startf, cfgf, outf = sys.argv[1:5]
    cfg = json.load(open(cfgf, encoding='utf-8')); deck = json.load(open(startf))
    Ul = sim2.load_cards(path); pool = pool_for(Ul, cfg['school'], cfg.get('extra_no_skill', False))
    goal = cfg['goal']
    with mp.Pool(parallel.workers(), initializer=init, initargs=(path,)) as P, open(outf, 'a', encoding='utf-8') as fo:
        base = P.map(ev, [(deck, goal, cfg['n_confirm'], 777)])[0]
        floor = base['rcv5'] - cfg['rcv5_floor_drop']
        cur, cur_m = deck, base
        fo.write(json.dumps(dict(step=0, deck=cur, m=cur_m, floor=floor, pool=pool), ensure_ascii=False) + '\n'); fo.flush()
        for step in range(1, cfg['steps'] + 1):
            t0 = time.time()
            nb = list(neighbors(cur, pool, Ul))
            res = P.map(ev, [(d, goal, cfg['n_screen'], 1000 + step) for _, d in nb])
            cur_s = P.map(ev, [(cur, goal, cfg['n_screen'], 1000 + step)])[0]
            ranked = sorted(zip(nb, res), key=lambda x: -score(x[1], cfg, floor))[:4]
            ranked = [x for x in ranked if score(x[1], cfg, floor) > score(cur_s, cfg, floor)]
            if not ranked:
                fo.write(json.dumps(dict(step=step, stop='粗篩沒有更好的換法'), ensure_ascii=False) + '\n'); break
            conf = P.map(ev, [(d, goal, cfg['n_confirm'], 5000 + step) for (_, d), _ in ranked] + [(cur, goal, cfg['n_confirm'], 5000 + step)])
            cur_c = conf[-1]
            best = max(zip(ranked, conf[:-1]), key=lambda x: score(x[1], cfg, floor))
            (mv, d), _ = best[0]; m = best[1]
            if score(m, cfg, floor) <= score(cur_c, cfg, floor):
                fo.write(json.dumps(dict(step=step, stop='複查後沒有進步'), ensure_ascii=False) + '\n'); break
            cur, cur_m = d, m
            fo.write(json.dumps(dict(step=step, move=mv, deck=cur, m=cur_m, cur_before=cur_c, sec=round(time.time() - t0)), ensure_ascii=False) + '\n'); fo.flush()
