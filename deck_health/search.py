"""梟谷牌組（DH_POLICY=default/always 套在 A 方）貪婪搜尋（同種子配對）。
用法: python -I search.py <deck_health根目錄> <起始牌組json> <輸出目錄>
每輪：所有「-k張X +k張Y」(k=2，找不到改善後改 k=1) 粗篩 → 前 TOP 名用新種子複驗 → 差值 > 2×SE 才採用。"""
import sys, os, json, math, time, multiprocessing as mp
root = sys.argv[1]; sys.path.insert(0, root)
POLICY = os.environ.get('DH_POLICY', 'default')

def low_priority():
    """Windows：把程序設成「低」優先權，滿載時前景操作照樣順（使用者 2026-10-28：16 核滿載卡到電腦不能動）。"""
    if os.name == 'nt':
        import ctypes
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass(ctypes.c_void_p(k.GetCurrentProcess()), 0x40)  # IDLE_PRIORITY_CLASS


low_priority()

import sim2, parallel, evo_state

OPPS = os.environ.get('OPPS', 'deck.json,fuku_op8_v2.json,shira_final.json,ina_v4b.json,mixed_user.json,champ.json').split(',')
CHARS = ['HV-P01-043', 'HV-P01-044', 'HV-P01-045', 'HV-P01-046', 'HV-P01-047', 'HV-P01-048', 'HV-P01-049', 'HV-P01-050',
         'HV-P01-051', 'HV-P01-052', 'HV-P02-064', 'HV-P02-065', 'HV-P02-066', 'HV-P02-067', 'HV-P03-061', 'HV-P03-062',
         'HV-PR-006', 'HV-PR-026', 'HV-PR-047', 'HV-PR-062',
         'HV-P04-063', 'HV-P04-064', 'HV-P04-065', 'HV-P04-066', 'HV-P04-067']
EVENTS = ['HV-P01-089', 'HV-P01-090', 'HV-P01-091', 'HV-P01-092', 'HV-P01-093', 'HV-PR-031', 'HV-D01-011']
POOL = CHARS + EVENTS
# 台灣不能用的卡（PR-013 木兎・赤葦是日本限定書卡，使用者 2026-10-29）：不進卡池；起始牌組有的話先強制換掉
BAN = ['HV-PR-013', 'HV-PR-021', 'HV-PR-077']  # PR-013/077 雜誌附錄、PR-021 ジャンプフェスタ：台灣不能用（使用者 2026-10-29：雜誌卡一律不能用）
MULT = [int(x) for x in os.environ.get('MULT', ','.join('1' * len(OPPS))).split(',')]
SCREEN_N, CONFIRM_N, TOP, MAX_ROUNDS = int(os.environ.get('SCREEN_N', 50)), int(os.environ.get('CONFIRM_N', 1500)), 5, 8
STAGE2_N, STAGE2_K = int(os.environ.get('STAGE2_N', 300)), 30  # 兩段粗篩：先 50 場砍到前 30 名，再跑 300 場
U = None; OPP = None


def init():
    global U, OPP
    low_priority()
    U = sim2.load_cards(r'C:/Users/evils/Documents/Claude/Claude Code/排球少年-deckhealth/cards_data.js')
    sim2.CFG['a_block_policy'] = POLICY
    OPP = [json.load(open(os.path.join(root, f))) for f in OPPS]


def job(a):
    vid, d, oi, n, seed = a
    return vid, oi, seed, [int(g['winner'] == 'A') for g in sim2.match(U, d, OPP[oi], n, seed=seed)]


class SafePool:
    """子程序無聲死掉時 mp.Pool 會永遠卡住（2026-10-29 月島搜尋卡在第 2 輪）。
    改用 ProcessPoolExecutor：子程序死掉會丟 BrokenProcessPool，就重建程序池、把整批重算。"""
    def __init__(self, n): self.n = n; self.ex = None; self._new()
    def _new(self):
        from concurrent.futures import ProcessPoolExecutor
        if self.ex: self.ex.shutdown(wait=False, cancel_futures=True)
        self.ex = ProcessPoolExecutor(self.n, initializer=init)
    def run(self, fn, tasks, tick=None):
        from concurrent.futures.process import BrokenProcessPool
        games = sum(t[3] for t in tasks)
        for attempt in range(5):
            try:
                rows, done = [], 0
                for row in self.ex.map(fn, tasks, chunksize=1):
                    rows.append(row); done += len(row[3])
                    if tick: tick(done, games)
                return rows
            except BrokenProcessPool:
                print('子程序異常結束，重建程序池重算（第%d次）' % (attempt + 1), flush=True); self._new()
        raise RuntimeError('程序池連續失敗 5 次')
    def close(self): self.ex.shutdown(wait=True)


def evaluate(pool, decks, n, sa, sb, tick=None):
    """decks: {vid: deck} → {vid: 逐場勝負 list}（同 vid 內順序固定，跨 vid 同位置同種子）"""
    ch = {oi: parallel.chunks(n * MULT[oi], sa + oi * 100003, sb) for oi in range(len(OPPS))}  # MULT：加權＝該對手多跑幾倍場數
    tasks = [(v, d, oi, k, s) for v, d in decks.items() for oi in range(len(OPPS)) for k, s in ch[oi]]
    res = {}
    for v, oi, s, w in pool.run(job, tasks, tick):
        res[(v, oi, s)] = w
    return {v: [x for oi in range(len(OPPS)) for k, s in ch[oi] for x in res[(v, oi, s)]] for v in decks}


def paired(a, b):
    d = [x - y for x, y in zip(a, b)]
    m = sum(d) / len(d)
    var = sum((x - m) ** 2 for x in d) / (len(d) - 1)
    return m, math.sqrt(var / len(d))


def moves(deck, k):
    out = {}
    nev = sum(n for c, n in deck.items() if c in EVENTS)
    for x, nx in deck.items():
        kk = min(k, nx)
        for y in POOL:
            if y == x: continue
            ev = nev - (kk if x in EVENTS else 0) + (kk if y in EVENTS else 0)
            if ev > 8: continue
            d = dict(deck); d[x] -= kk
            if d[x] == 0: del d[x]
            d[y] = d.get(y, 0) + kk
            out[f'-{kk}{x}+{kk}{y}'] = d
    return out


def record(out, decks, res, stage, rnd):
    """把每個複驗牌組的絕對勝率寫進 results.json，給儀表板列前 3 名（勝率＝對加權後 10 副對手的平均）。"""
    path = os.path.join(out, 'results.json')
    try: rows = json.load(open(path, encoding='utf-8'))
    except Exception: rows = []
    seen = {json.dumps(r['deck'], sort_keys=True) + r['stage'] + str(r['round']) for r in rows}
    for v, d in decks.items():
        if not res.get(v): continue
        key = json.dumps(d, sort_keys=True) + stage + str(rnd)
        if key in seen: continue
        rows.append(dict(deck=d, winrate=sum(res[v]) / len(res[v]), n=len(res[v]), move=v, stage=stage, round=rnd, t=time.time()))
    json.dump(rows, open(path, 'w', encoding='utf-8'), ensure_ascii=False)


def reporter(out, rnd, k, plan, stage, t0):
    """evaluate 的進度回呼：把本輪進度寫進 progress.json 給儀表板，最多一秒一次。面板正在讀而寫失敗時跳過，不能影響搜尋。"""
    path = os.path.join(out, 'progress.json'); last = [0]
    def tick(done, total):
        now = time.time()
        if done < total and now - last[0] < 1: return
        last[0] = now
        try:
            with open(path + '.tmp', 'w', encoding='utf-8') as f: json.dump(evo_state.round_progress(rnd, k, stage, done, total, plan, t0, now), f)
            os.replace(path + '.tmp', path)
        except OSError: pass
    return tick


def log(msg, f):
    print(msg, flush=True); f.write(msg + '\n'); f.flush()


if __name__ == '__main__':
    deck = json.load(open(sys.argv[2])); out = sys.argv[3]
    assert sum(deck.values()) == 40
    lf = open(os.path.join(out, 'search.log'), 'a', encoding='utf-8')
    hist = []
    k = int(os.environ.get('START_K', 2)); rnd = int(os.environ.get('START_ROUND', 1)) - 1
    done_path = os.path.join(out, 'search_result.json')
    if rnd and os.path.exists(done_path):  # search_result.json 每次採用都整份覆寫，接續時沒帶上前幾輪就會遺失
        hist = [h for h in json.load(open(done_path, encoding='utf-8'))['hist'] if h['round'] <= rnd]
    pool = SafePool(parallel.workers())
    for x in [c for c in BAN if c in deck]:
        kk = deck[x]; nev = sum(n for c, n in deck.items() if c in EVENTS); fm = {}
        for y in POOL:
            if y in EVENTS and nev + kk > 8: continue
            d = dict(deck); del d[x]; d[y] = d.get(y, 0) + kk; fm[f'-{kk}{x}+{kk}{y}'] = d
        log(f'== 禁用卡強制替換 {x}×{kk}，候選{len(fm)}', lf)
        r = evaluate(pool, {'cur': deck, **fm}, STAGE2_N, 7000, 8000)
        sc = sorted(((paired(r[v], r['cur'])[0], v) for v in fm), reverse=True)
        log('粗篩前10: ' + ' | '.join(f'{v} {m*100:+.1f}' for m, v in sc[:10]), lf)
        top = {v: fm[v] for m, v in sc[:TOP]}
        rc = evaluate(pool, {'cur': deck, **top}, CONFIRM_N, 70000, 80000)
        record(out, top, rc, 'forced', 0)
        cf = sorted(((*paired(rc[v], rc['cur']), v) for v in top), reverse=True)
        log(f'複驗(含禁用卡勝率 {sum(rc["cur"])/len(rc["cur"])*100:.1f}%): ' + ' | '.join(f'{v} {m*100:+.2f}±{se*100:.2f}' for m, se, v in cf), lf)
        m, se, v = cf[0]; deck = top[v]
        hist.append(dict(round=0, move=v, diff=m, se=se, forced=True, deck=dict(deck)))
        log(f'採用 {v}（強制替換，{m*100:+.2f}，SE {se*100:.2f}）', lf)
    if True:
        while rnd < MAX_ROUNDS:
            rnd += 1; t0 = time.time()
            mv = moves(deck, k)
            log(f'== 第{rnd}輪 k={k} 候選{len(mv)} 目前牌組 {json.dumps(deck)}', lf)
            sa, sb = 1000 + rnd * 7, 2000 + rnd * 11  # 粗篩種子每輪不同
            plan = [(len(mv) + 1) * SCREEN_N * sum(MULT), (min(STAGE2_K, len(mv)) + 1) * STAGE2_N * sum(MULT), (TOP + 1) * CONFIRM_N * sum(MULT)]
            r = evaluate(pool, {'cur': deck, **mv}, SCREEN_N, sa, sb, reporter(out, rnd, k, plan, 0, t0))
            sc = sorted(((paired(r[v], r['cur'])[0], v) for v in mv), reverse=True)
            log('第一段前10: ' + ' | '.join(f'{v} {m*100:+.1f}' for m, v in sc[:10]) + f'  ({time.time()-t0:.0f}s)', lf)
            s2 = {v: mv[v] for m, v in sc[:STAGE2_K]}
            r = evaluate(pool, {'cur': deck, **s2}, STAGE2_N, 3000 + rnd * 7, 4000 + rnd * 11, reporter(out, rnd, k, plan, 1, t0))
            sc = sorted(((paired(r[v], r['cur'])[0], v) for v in s2), reverse=True)
            log('粗篩前10: ' + ' | '.join(f'{v} {m*100:+.1f}' for m, v in sc[:10]) + f'  ({time.time()-t0:.0f}s)', lf)
            top = {v: mv[v] for m, v in sc[:TOP] if m > 0}
            if not top:
                log('粗篩無正向候選', lf)
            else:
                rc = evaluate(pool, {'cur': deck, **top}, CONFIRM_N, 50000 + rnd * 13, 60000 + rnd * 17, reporter(out, rnd, k, plan, 2, t0))
                record(out, {'cur': deck, **top}, rc, 'confirm', rnd)
                base_w = sum(rc['cur']) / len(rc['cur'])
                cf = sorted(((*paired(rc[v], rc['cur']), v) for v in top), reverse=True)
                log(f'複驗(目前勝率 {base_w*100:.1f}%): ' + ' | '.join(f'{v} {m*100:+.2f}±{se*100:.2f}' for m, se, v in cf), lf)
                pick = evo_state.adoption(cf)  # 不只看第一名：第 2 輪差值第二名過了 2×SE 卻沒被檢查，新種子複驗確認是真的（+2.30，SE 0.33）
                if pick:
                    m, se, v = pick
                    deck = top[v]
                    hist.append(dict(round=rnd, move=v, diff=m, se=se, base=base_w, deck=dict(deck)))
                    log(f'採用 {v}（{m*100:+.2f}，SE {se*100:.2f}）', lf)
                    json.dump(dict(deck=deck, hist=hist), open(os.path.join(out, 'search_result.json'), 'w'), ensure_ascii=False, indent=1)
                    continue
                log('複驗未達 2×SE', lf)
            if k == 2: k = 1; log('改用單張替換', lf); continue
            break
    log('結束 ' + json.dumps(deck), lf)
    json.dump(dict(deck=deck, hist=hist), open(os.path.join(out, 'search_result.json'), 'w'), ensure_ascii=False, indent=1)
