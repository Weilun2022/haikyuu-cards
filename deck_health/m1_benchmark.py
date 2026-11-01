"""M1 效能量測：以 -I、IDLE 在同一程序比較固定版本及目前版本。"""
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import time
import types

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from m1_verify import idle


def load(ref):
    source = subprocess.check_output(['git', 'show', ref + ':deck_health/sim2.py'], cwd=HERE.parent)
    mod = types.ModuleType('engine_' + ref)
    mod.__file__ = str(HERE / 'sim2.py')
    exec(compile(source, mod.__file__, 'exec'), mod.__dict__)
    return mod, hashlib.sha256(source).hexdigest()


def main():
    if not sys.flags.isolated:
        raise SystemExit('必須使用 python -I')
    idle()
    import sim2
    baseline, baseline_hash = load('c818f92')
    engines = [('baseline', baseline), ('current', sim2)]
    u = sim2.load_cards(str(HERE.parent / 'cards_data.js'))
    report = dict(baseline='c818f92', baseline_sha256=baseline_hash,
                  current_sha256=hashlib.sha256((HERE / 'sim2.py').read_bytes()).hexdigest(),
                  isolated=True, priority=64, workers=1, python=sys.version, cfg=sim2.CFG,
                  seed_range=[1000, 1099], results=[])
    out = HERE / 'm1_verification/information_performance.json'
    for an, bn in [('fuku_op8_v2', 'deck'), ('shira_final', 'ina_v4b'), ('kakugawa_user', 'champ')]:
        decks = [json.loads((HERE / (n + '.json')).read_text(encoding='utf-8')) for n in (an, bn)]
        result = dict(pair=[an, bn], N=100)
        for name, engine in engines:
            a, b = [engine.build(u, d) for d in decks]
            start = time.perf_counter()
            for seed in range(1000, 1100):
                engine.play_game(a, b, random.Random(seed))
            result[name] = time.perf_counter() - start
        result['ratio'] = result['current'] / result['baseline']
        report['results'].append(result)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
