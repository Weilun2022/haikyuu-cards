"""演化進度面板：python evo_panel.py [search.log 路徑] [埠號=8765]，瀏覽器開 http://localhost:8765
每 5 秒自動更新：搜尋是否在跑、勝率有沒有變好、可信度、前 3 名牌組、各輪決策。唯讀，不影響搜尋。
輸出目錄放 pipeline.json 就會列出全流程進度：[{title, kind, ...}]，kind＝search（這次搜尋）／log（log 有「n / 總數 秒 s」與 done 行，
要給 log、proc＝命令列特徵字串）／lines（每完成一項印一行 JSON，再給 total）／manual（給 status：pending、running、done、failed）。
est＝預估秒數，note＝附註。任何長時間工作都要列進來，面板才看得到。
資料解析在 evo_state.py，畫面在 evo_panel.html。"""
import json
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import evo_state

LOG = Path(r'C:/Users/evils/Documents/Claude/Claude Code/排球少年-deckhealth/out_evo_r4/search.log')
PORT = 8765
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MAIN = Path(r'C:/Users/evils/Documents/Claude/Claude Code/排球少年')  # 主 repo 的 images 比較齊全
IMG_DIRS = [MAIN / 'images', REPO / 'images']
ENGINE = '07d7dbe'  # 這次搜尋用的引擎；換引擎或 M1 收尾時改這裡，可信度欄位跟著變
M1_DONE = True
HOLDOUT = ['kakugawa_user', 'shira', 'ina_v5']
CARDS = {}


def load_cards():
    if CARDS: return
    t = (MAIN / 'cards_data.js').read_text(encoding='utf-8')
    data = json.loads(t[t.index('{'):t.rindex('}') + 1])
    for c in data['cards']:
        CARDS.setdefault(c['card_no'], dict(img=c['image_file'], name=c.get('name_zh') or c.get('name'), ev=c.get('category') == 'EVENT'))


PS = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
      "Select-Object ProcessId,ParentProcessId,CommandLine,KernelModeTime,UserModeTime | ConvertTo-Json -Compress")
_prev = {}


def procs():
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-Command', PS], capture_output=True, timeout=20).stdout.decode('utf-8', 'replace')
        rows = json.loads(out) if out.strip() else []
    except Exception:
        return None
    rows = rows if isinstance(rows, list) else [rows]
    main = [r for r in rows if r.get('CommandLine') and evo_state.is_this_search(r['CommandLine'], LOG.parent.name)]
    ids = {r['ProcessId'] for r in main}
    kids = [r for r in rows if r.get('ParentProcessId') in ids]
    cpu = sum((r['KernelModeTime'] + r['UserModeTime']) / 1e7 for r in main + kids)  # 秒
    return dict(main=len(main), workers=len(kids), cpu=cpu, rows=rows)


def read_json(name, default):
    try:
        return json.loads((LOG.parent / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):  # 還沒產生，或正在覆寫
        return default


def job(step, rows, search_text, search_age, search_kind, now):
    if step['kind'] == 'search':
        return evo_state.job_status(step, search_text, age=search_age, search_kind=search_kind, progress=read_json('progress.json', None))
    path = Path(step.get('log', ''))
    found = path.is_file()
    text = path.read_text(encoding='utf-8', errors='replace') if found else None  # 由程序直接重導的 log 是 cp950，判斷只看 ASCII 部分
    proc = step.get('proc')
    main = {r['ProcessId'] for r in rows or [] if proc and proc in (r.get('CommandLine') or '')}
    workers = sum(r.get('ParentProcessId') in main for r in rows or [])
    running = None if rows is None else bool(main)
    return dict(evo_state.job_status(step, text, running, now - path.stat().st_mtime if found else None), workers=workers)


def state():
    load_cards()
    p = procs()
    rows = p.pop('rows') if p else None
    now = time.time()
    delta = None
    if p:
        if 'cpu' in _prev and now - _prev['t'] > 1: delta = (p['cpu'] - _prev['cpu']) / (now - _prev['t'])
        _prev.update(cpu=p['cpu'], t=now)
    text = LOG.read_text(encoding='utf-8', errors='replace') if LOG.exists() else ''
    beats = [f.stat().st_mtime for f in (LOG, LOG.parent / 'progress.json') if f.exists()]  # progress.json 每秒更新，log 只在每段結束時寫
    age = now - max(beats) if beats else None
    s = evo_state.snapshot(text, read_json('results.json', []), CARDS)
    s.update(proc=p, busy=delta, age=age, log=str(LOG), run=LOG.parent.name, engine=ENGINE, m1_done=M1_DONE, holdout=HOLDOUT)
    s['kind'] = evo_state.verdict(s)
    s['holdout_result'] = evo_state.holdout_summary(read_json('verify_holdout.json', None))
    s['jobs'] = [job(step, rows, text, age, s['kind'], now) for step in read_json('pipeline.json', [])]
    s['pipeline'] = evo_state.pipeline(s['jobs'], now)
    return s


class Server(ThreadingHTTPServer):  # 單執行緒會被瀏覽器預開的閒置連線卡死
    request_queue_size = 64  # 預設 5，一次載幾十張卡圖時連線會被重置


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, body, ctype, cache='no-store'):
        self.send_response(200); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', cache); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith('/img/'):
            name = Path(unquote(self.path[5:])).name
            f = next((d / name for d in IMG_DIRS if (d / name).is_file()), None)
            if f is None:
                self.send_response(404); self.end_headers(); return
            return self.send(f.read_bytes(), 'image/webp' if name.endswith('.webp') else 'image/png', 'max-age=86400')
        if self.path == '/lib/lz-string.min.js':
            return self.send((MAIN / 'lib' / 'lz-string.min.js').read_bytes(), 'application/javascript')
        if self.path == '/state':
            return self.send(json.dumps(state(), ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')
        self.send((HERE / 'evo_panel.html').read_bytes(), 'text/html; charset=utf-8')


if __name__ == '__main__':
    if len(sys.argv) > 1: LOG = Path(sys.argv[1])
    if len(sys.argv) > 2: PORT = int(sys.argv[2])
    print('http://localhost:%d  log=%s' % (PORT, LOG), flush=True)
    Server(('127.0.0.1', PORT), H).serve_forever()
