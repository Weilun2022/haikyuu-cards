"""本機自動執行器：由 Windows 工作排程器每幾分鐘執行一次，不需要 AI、不需要人操作。

流程：
1. 取得 deck-health 分支最新內容（這個資料夾是專用的 clone，會直接對齊遠端）
2. 讀 deck_health/mailbox/jobs.json，找出還沒完成的工作
3. 只執行白名單裡的分析程式，參數必須是數字或 deck_health 裡存在的檔名
4. 結果寫進 deck_health/mailbox/results/<工作編號>/，commit 並 push

安全設計：不執行任何任意指令；只跑白名單程式，參數逐一檢查。
用法：python -I runner.py            （正常執行）
      python -I runner.py --dry-run  （只列出會執行的工作，不跑、不推）
      python -I runner.py --list-pending / --only <工作編號>（GitHub Actions 用）"""
import json, os, re, subprocess, sys, time, datetime

HERE = os.path.dirname(os.path.abspath(__file__))          # .../deck_health
ROOT = os.path.dirname(HERE)                                # repo 根目錄
MAILBOX = os.path.join(HERE, 'mailbox')
JOBS = os.path.join(MAILBOX, 'jobs.json')
RESULTS = os.path.join(MAILBOX, 'results')
LOCK = os.path.join(ROOT, '.runner.lock')
LOCAL_LOG = os.path.join(ROOT, 'runner.log')                # 只留在本機，不推上 GitHub
BRANCH = 'deck-health'
NOWIN = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}  # 排程執行時不跳出黑色視窗

# 白名單：程式名稱 → 檔案
ALLOWED = {
    'compare2': 'compare2.py',
    'gauntlet': 'gauntlet.py',
    'vs_deck': 'vs_deck.py',
    'optimize': 'optimize.py',
    'optimize_guard': 'optimize_guard.py',
    'solo': 'solo.py',
    'template': 'template.py',
}
SAFE_NAME = re.compile(r'^[\w\-.]+$')


def log(msg):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    with open(LOCAL_LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def git(*args, check=True):
    r = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', **NOWIN)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失敗：{r.stderr.strip()[:500]}")
    return r.stdout.strip()


def sync():
    git('fetch', '-q', 'origin', BRANCH)
    git('checkout', '-q', BRANCH)
    git('reset', '-q', '--hard', f'origin/{BRANCH}')


def resolve_args(job, out_path):
    """把工作單的參數轉成實際參數；不合法就丟出錯誤。"""
    out = []
    for a in job.get('args', []):
        if isinstance(a, int):
            out.append(str(a)); continue
        if not isinstance(a, str):
            raise ValueError(f'參數型別不允許：{a!r}')
        if a == '{cards}':
            out.append(os.path.join(ROOT, 'cards_data.js')); continue
        if a == '{out}':
            out.append(out_path); continue
        if re.fullmatch(r'\d+', a):
            out.append(a); continue
        parts = a.split(',')                                # gauntlet 的對手清單用逗號分隔
        for p in parts:
            if not SAFE_NAME.fullmatch(p) or '..' in p:
                raise ValueError(f'參數不允許：{a!r}')
            if not os.path.isfile(os.path.join(HERE, p)):
                raise ValueError(f'找不到檔案：{p}')
        out.append(a)
    return out


def run_job(job):
    jid = job['id']
    if not SAFE_NAME.fullmatch(jid):
        raise ValueError(f'工作編號不合法：{jid!r}')
    script = ALLOWED.get(job.get('script'))
    if not script:
        raise ValueError(f"程式不在白名單：{job.get('script')!r}")
    rdir = os.path.join(RESULTS, jid)
    os.makedirs(rdir, exist_ok=True)
    out_path = os.path.join(rdir, 'out.jsonl')
    args = resolve_args(job, out_path)
    cpu = os.cpu_count() or 2
    cap = cpu if os.environ.get('GITHUB_ACTIONS') == 'true' else max(1, cpu - 2)  # GitHub 伺服器用全部核心；本機保留 2 核
    workers = max(1, min(int(job.get('workers', 2)), cap))
    timeout = int(job.get('timeout_min', 120)) * 60
    if os.environ.get('GITHUB_ACTIONS') == 'true':  # 工作單的時限是照本機 16 程序估的；核心較少時按比例放寬（上限 340 分鐘）
        timeout = min(340 * 60, int(timeout * max(1.0, int(job.get('workers', 2)) / workers)))
    env = dict(os.environ, DH_WORKERS=str(workers))
    for k, v in (job.get('env') or {}).items():
        if not (re.fullmatch(r'DH_[A-Z0-9_]+', k) and re.fullmatch(r'[\w\-.]+', str(v))):
            raise ValueError(f'環境變數不允許：{k}')
        env[k] = str(v)
    t0 = time.time()
    status = dict(id=jid, script=job['script'], args=job.get('args', []), workers=workers,
                  started=datetime.datetime.now().isoformat(timespec='seconds'))
    with open(os.path.join(rdir, 'log.txt'), 'w', encoding='utf-8') as lf:
        try:
            r = subprocess.run([sys.executable, '-I', '-X', 'utf8', script, *args], cwd=HERE, env=env,
                               stdout=lf, stderr=subprocess.STDOUT, timeout=timeout, **NOWIN)
            status.update(ok=r.returncode == 0, returncode=r.returncode)
        except subprocess.TimeoutExpired:
            status.update(ok=False, returncode=None, error=f'超過時間上限 {timeout // 60} 分鐘')
    status.update(finished=datetime.datetime.now().isoformat(timespec='seconds'), seconds=round(time.time() - t0, 1))
    with open(os.path.join(rdir, 'status.json'), 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=1)
    return status


def push(jid, status):
    git('add', os.path.join('deck_health', 'mailbox', 'results', jid))
    msg = f"chore(runner): {'完成' if status.get('ok') else '失敗'}工作 {jid}（{status.get('seconds')} 秒）"
    git('-c', 'user.name=deck-runner', '-c', 'user.email=deck-runner@localhost', 'commit', '-q', '-m', msg)
    for i in range(8):  # 多個工作同時推送時互相讓位
        if subprocess.run(['git', 'push', '-q', 'origin', f'HEAD:{BRANCH}'], cwd=ROOT, **NOWIN).returncode == 0:
            return
        time.sleep(3 + 2 * i)
        git('pull', '-q', '--rebase', 'origin', BRANCH)
    raise RuntimeError('push 失敗多次')


def pending_ids():
    if not os.path.isfile(JOBS):
        return []
    jobs = json.load(open(JOBS, encoding='utf-8')).get('jobs', [])
    return [str(j.get('id', '')) for j in jobs
            if SAFE_NAME.fullmatch(str(j.get('id', ''))) and not os.path.isfile(os.path.join(RESULTS, str(j.get('id')), 'status.json'))]


def run_one_ci(jid):
    """GitHub Actions 用：checkout 已經是最新內容，只執行指定的一個工作。"""
    jobs = {str(j.get('id')): j for j in json.load(open(JOBS, encoding='utf-8')).get('jobs', [])}
    if jid not in jobs or jid not in pending_ids():
        print(f'{jid} 不需要執行'); return
    try:
        st = run_job(jobs[jid])
    except Exception as e:
        rdir = os.path.join(RESULTS, jid); os.makedirs(rdir, exist_ok=True)
        st = dict(id=jid, ok=False, error=str(e))
        with open(os.path.join(rdir, 'status.json'), 'w', encoding='utf-8') as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
    push(jid, st)
    print(json.dumps(st, ensure_ascii=False))


def main(dry):
    if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 6 * 3600:
        return  # 上一輪還在跑
    open(LOCK, 'w').close()
    try:
        sync()
        if not os.path.isfile(JOBS):
            return
        jobs = json.load(open(JOBS, encoding='utf-8')).get('jobs', [])
        for job in jobs:
            jid = str(job.get('id', ''))
            if os.path.isfile(os.path.join(RESULTS, jid, 'status.json')):
                continue
            if dry:
                print('會執行：', json.dumps(job, ensure_ascii=False)); continue
            log(f'開始 {jid}')
            try:
                st = run_job(job)
            except Exception as e:  # 工作單不合法：記錄失敗原因並推回，避免每輪重試
                rdir = os.path.join(RESULTS, jid if SAFE_NAME.fullmatch(jid) else 'invalid')
                os.makedirs(rdir, exist_ok=True)
                st = dict(id=jid, ok=False, error=str(e))
                with open(os.path.join(rdir, 'status.json'), 'w', encoding='utf-8') as f:
                    json.dump(st, f, ensure_ascii=False, indent=1)
                jid = os.path.basename(rdir)
            push(jid, st)
            log(f"結束 {jid} ok={st.get('ok')}")
            sync()  # 推完再對齊一次，讀到雲端剛加的新工作
    except Exception as e:
        log(f'錯誤：{e}')
    finally:
        try:
            os.remove(LOCK)
        except OSError:
            pass


if __name__ == '__main__':
    if '--list-pending' in sys.argv:
        print(json.dumps(pending_ids()))
    elif '--only' in sys.argv:
        run_one_ci(sys.argv[sys.argv.index('--only') + 1])
    else:
        main('--dry-run' in sys.argv)
