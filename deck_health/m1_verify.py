"""M1 本機驗證：父子程序 IDLE，固定測試 hash seed，保留完整輸出。"""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def idle():
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = ctypes.c_void_p
    h = ctypes.c_void_p(k.GetCurrentProcess())
    if not k.SetPriorityClass(h, 0x40) or k.GetPriorityClass(h) != 0x40:
        raise RuntimeError('無法設定並查驗 IDLE')


def main():
    idle()
    os.chdir(HERE.parent)
    os.environ.update(PYTHONHASHSEED='0', PYTHONIOENCODING='utf-8')
    out = HERE / 'm1_verification'
    out.mkdir(exist_ok=True)
    suites = ['archive', 'paired', 'paired_runtime', 'name_entry_restrictions',
              'p03016_self_attack', 'p04037_umakado']
    scripts = ['batch1', 'batch2', 'batch2_units', 'batch3', 'batch3_units',
               'batch4', 'batch4_units', 'batch5', 'batch5_units', 'batch6',
               'batch7', 'batch8', 'block_serve', 'champ', 'fetch_attack',
               'fuku_batch2', 'guts_zones', 'inari', 'mixed', 'onetouch_center',
               'p04', 'review_fixes', 'shira', 'yamiji']
    bootstrap = ('import sys;sys.path.insert(0,' + repr(str(HERE)) + ');'
                 'from m1_verify import idle;idle();')
    jobs = [('pytest', bootstrap + 'import pytest;raise SystemExit(pytest.main(' +
             repr([str(HERE / 'tests' / f'test_{s}.py') for s in suites] +
                  ['-q', '-p', 'no:cacheprovider', '--tb=short']) + '))'),
            ('real_sim', bootstrap + 'import pytest;raise SystemExit(pytest.main(' +
             repr([str(HERE / 'tests/test_paired_runtime.py'), '-q', '-k',
                   'test_real_sim_spawn_replay', '-p', 'no:cacheprovider', '--tb=short']) + '))')]
    if '--legal' in sys.argv:
        jobs.append(('legal', bootstrap + 'import pytest;raise SystemExit(pytest.main(' +
                     repr([str(HERE / 'tests/test_legal_information.py'), '-q',
                           '-p', 'no:cacheprovider', '--tb=short']) + '))'))
    jobs += [(s, bootstrap + 'import runpy;runpy.run_path(' +
              repr(str(HERE / 'tests' / f'test_{s}.py')) + ',run_name="__main__")') for s in scripts]
    summary = []
    for name, code in jobs:
        start = time.perf_counter()
        r = subprocess.run([sys.executable, '-c', code], capture_output=True, encoding='utf-8')
        text = r.stdout + r.stderr
        (out / f'{name}.txt').write_text(text, encoding='utf-8')
        bad = [line for line in text.splitlines() if
               (line.startswith('FAIL ') or line.startswith('FAIL:') or
                line.startswith('FAILED ') or line.startswith('FAILS: [')) and
               line not in ('FAILS: []', 'FAILED: none')]
        item = dict(name=name, returncode=r.returncode, failures=bad,
                    seconds=time.perf_counter() - start)
        summary.append(item)
        (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        print(name, r.returncode, bad, flush=True)
        if r.returncode or bad:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
