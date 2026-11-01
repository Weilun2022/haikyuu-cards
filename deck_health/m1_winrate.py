"""M1 分階段勝率對照：七副牌兩兩 21 組，各 N 場、同種子配對。
版本：base=c818f92（M1 前）、iso=673b0b3（只修隔離）、cur=目前工作檔（資訊邊界版）。
用法：python -I deck_health/m1_winrate.py [N] [workers]；一律 IDLE 優先權，輸出 m1_verification/winrate_*.json。"""
import hashlib
import itertools
import json
import math
from multiprocessing import Pool
from pathlib import Path
import random
import subprocess
import sys
import time
import types

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from m1_verify import idle

DECKS = ['deck', 'fuku_op8_v2', 'shira_final', 'ina_v4b', 'mixed_user', 'champ', 'kakugawa_user']
REFS = dict(base='c818f92', iso='673b0b3', cur=None)
CHUNK = 50
_state = {}


def load(version):
    ref = REFS[version]
    if ref is None:
        source = (HERE / 'sim2.py').read_bytes()
    else:
        source = subprocess.check_output(['git', 'show', ref + ':deck_health/sim2.py'], cwd=HERE.parent)
    mod = types.ModuleType('engine_' + version)
    mod.__file__ = str(HERE / 'sim2.py')
    exec(compile(source, mod.__file__, 'exec'), mod.__dict__)
    return mod, hashlib.sha256(source).hexdigest()


def init():
    idle()


def run(task):
    version, a, b, lo, hi = task
    if version not in _state:
        eng, _ = load(version)
        u = eng.load_cards(str(HERE.parent / 'cards_data.js'))
        _state[version] = (eng, u, {})
    eng, u, built = _state[version]
    for n in (a, b):
        if n not in built:
            built[n] = eng.build(u, json.loads((HERE / (n + '.json')).read_text(encoding='utf-8')))
    out = []
    for seed in range(lo, hi):
        r = eng.play_game(built[a], built[b], random.Random(seed))
        out.append(1 if r['winner'] == 'A' else 0)
    return (version, a, b, lo, out)


def main():
    if not sys.flags.isolated:
        raise SystemExit('必須使用 python -I')
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    workers = min(16, int(sys.argv[2]) if len(sys.argv) > 2 else 14)
    idle()
    hashes = {v: load(v)[1] for v in REFS}
    tasks = [(v, a, b, lo, min(lo + CHUNK, 1000 + n))
             for a, b in itertools.combinations(DECKS, 2)
             for lo in range(1000, 1000 + n, CHUNK) for v in REFS]
    res = {}
    start = time.perf_counter()
    with Pool(workers, initializer=init) as pool:
        for i, (v, a, b, lo, out) in enumerate(pool.imap_unordered(run, tasks), 1):
            res.setdefault((a, b, v), {})[lo] = out
            if i % 100 == 0: print(i, '/', len(tasks), round(time.perf_counter() - start), 's', flush=True)
    rows = []
    for a, b in itertools.combinations(DECKS, 2):
        s = {v: [x for lo in sorted(res[(a, b, v)]) for x in res[(a, b, v)][lo]] for v in REFS}
        row = dict(pair=[a, b], N=len(s['base']), winrate={v: sum(s[v]) / len(s[v]) for v in REFS})
        for x, y in [('base', 'iso'), ('iso', 'cur'), ('base', 'cur')]:
            d = [q - p for p, q in zip(s[x], s[y])]
            m = sum(d) / len(d)
            sd = math.sqrt(sum((t - m) ** 2 for t in d) / (len(d) - 1))
            se = sd / math.sqrt(len(d))
            row[x + '_to_' + y] = dict(diff=m, se=se, over_2se=m != 0 and abs(m) >= 2 * se)
        rows.append(row)
    out = HERE / 'm1_verification' / ('winrate_%d.json' % n)
    out.write_text(json.dumps(dict(refs=REFS, sha256=hashes, N=n, workers=workers, priority='IDLE',
                                   seconds=time.perf_counter() - start, rows=rows), ensure_ascii=False, indent=2), encoding='utf-8')
    print('done', out, round(time.perf_counter() - start), 's')


if __name__ == '__main__':
    main()
