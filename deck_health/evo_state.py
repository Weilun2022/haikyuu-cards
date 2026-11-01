"""演化面板的資料層：search.log 文字＋results.json 列表 → 面板要顯示的快照。純函式，不碰檔案或程序。"""
import json
import re

ROUND = re.compile(r'== 第(\d+)輪 k=(\d+) 候選(\d+) 目前牌組 (\{.*\})')
RECHECK = re.compile(r'(-\d+\S+) ([+-][\d.]+)±([\d.]+)')
MOVE = re.compile(r'-(\d+)(HV-[\w-]+?)\+\d+(HV-[\w-]+)')
SECS = re.compile(r'\((\d+)s\)$')
COUNTER = re.compile(r'^(\d+) / (\d+) (\d+) s$', re.M)  # m1_winrate、cand 的進度行：已完成 / 總批數 已耗秒數 s
THRESHOLD = 2  # search.py 的採用門檻：差值 > 2×SE
STALE_FLOOR, STALE_NO_ESTIMATE = 600, 1800  # 紀錄多久沒更新算疑似卡住（秒）
SEARCH_STATUS = dict(run='running', stall='stall', done='done', dead='failed', unknown='unknown')
ROUND_STAGES = ('第一段', '粗篩', '複驗')
PACE_LINES = 5  # ETA 只看最近幾段的速度：機器忙閒會變，累積平均反應太慢


def card(no, cards):
    c = cards.get(no, {})
    return dict(no=no, name=c.get('name') or no)


def move(text, cards):
    k, out, in_ = MOVE.fullmatch(text).groups()
    return {'k': int(k), 'out': card(out, cards), 'in': card(in_, cards)}


def parse_log(text, cards):
    rounds, forced, cur, finished = {}, None, None, False
    for line in text.splitlines():
        m = ROUND.match(line)
        if line.startswith('結束 '):
            finished = True
        elif m:  # search.log 是附加寫入：重跑或回到較早的輪次時，同輪和較晚的舊紀錄都作廢，結束標記也作廢
            n = int(m[1])
            rounds = {k: v for k, v in rounds.items() if k < n}
            cur = rounds[n] = dict(round=n, k=int(m[2]), funnel=[int(m[3])], deck=json.loads(m[4]),
                                   recheck=[], adopted=None, stage_secs=[], no_candidate=False)
            finished = False
        elif line.startswith('== 禁用卡'):  # 這段的複驗不屬於任何一輪
            cur, finished = None, False
        elif line.startswith('採用 ') and '強制替換' in line:
            m = re.match(r'採用 (\S+)（強制替換，([+-][\d.]+)，SE ([\d.]+)', line)
            forced = dict(move(m[1], cards), delta=float(m[2]) / 100, se=float(m[3]) / 100)
        elif cur is None:
            continue
        elif line.startswith(('第一段前10', '粗篩前10')):
            m = SECS.search(line)
            if m: cur['stage_secs'].append(int(m[1]))
            if line.startswith('第一段') and len(cur['funnel']) == 1: cur['funnel'].append(30)
        elif line.startswith('複驗('):
            for mv, d, se in RECHECK.findall(line):
                cur['recheck'].append(dict(move(mv, cards), move=mv, delta=float(d) / 100, se=float(se) / 100,
                                           ratio=float(d) / float(se), adopted=False))
            cur['funnel'].append(len(cur['recheck']))
        elif line.startswith('採用 '):
            cur['adopted'] = line.split()[1].split('（')[0]
            for c in cur['recheck']: c['adopted'] = c['move'] == cur['adopted']
        elif line.startswith('粗篩無正向候選'):
            cur['no_candidate'] = True
    return [rounds[k] for k in sorted(rounds)], forced, finished


def binom_se(wr, n):
    return (wr * (1 - wr) / n) ** .5


def stat(row):
    return dict(wr=row['winrate'], se=binom_se(row['winrate'], row['n']), n=row['n'])


def key(deck):
    return json.dumps(deck, sort_keys=True)


def is_recheck(row):
    """'cur'＝每輪開始時用新種子重驗目前牌組，沒有「從一批裡挑最高」的偏差。"""
    return row['move'] == 'cur'


def estimate(rows):
    """一副牌目前最該看的那筆：有重驗就用最近一次，沒有才用候選時的分數。"""
    fresh = [r for r in rows if is_recheck(r)]
    return fresh[-1] if fresh else max(rows, key=lambda r: r['winrate'])


def current_deck(rounds, results):
    if not rounds: return None
    last = rounds[-1]
    if last['adopted']:  # 剛採用、下一輪還沒開始：新牌組只存在 results 裡
        for r in results:
            if r['round'] == last['round'] and r['move'] == last['adopted']: return r['deck']
    return last['deck']


def headline(deck, results):
    rows = [r for r in results if deck is not None and key(r['deck']) == key(deck)]
    if not rows: return None
    return dict(stat(estimate(rows)), selected=not any(is_recheck(r) for r in rows),
                rechecks=[stat(r) for r in rows if is_recheck(r)])


def describe(row, kind, rounds, rows):
    rd = next((x for x in rounds if x['round'] == row['round']), None)
    if kind == 'final':
        picked = next((x for x in rows if not is_recheck(x)), None)
        rest = '、'.join(f"{x['winrate'] * 100:.1f}%±{binom_se(x['winrate'], x['n']) * 100:.1f}" for x in rows if is_recheck(x))
        if picked is None: return f'重驗 {rest}。'
        if not rest: return f"第 {picked['round']} 輪剛採用，這是被挑中時的分數，還沒有重驗。"
        return f"第 {picked['round']} 輪採用，之後重驗 {rest}。"
    if kind == 'past': return f"第 {row['round']} 輪時採用過，後來換掉了。"
    c = next((x for x in rd['recheck'] if x['move'] == row['move']), None) if rd else None
    if c is None: return f"第 {row['round']} 輪候選。" if row['round'] else '強制換掉禁用卡時的候選。'
    if c['ratio'] > THRESHOLD:
        why = '但同輪輸給更高的候選' if rd['adopted'] else '但同輪差值最高的候選沒過，所以沒採用'
        return f"第 {row['round']} 輪候選，已過門檻（{c['ratio']:.2f} SE），{why}。"
    return f"第 {row['round']} 輪候選，差 {THRESHOLD - c['ratio']:.2f} 個 SE 未過門檻，沒有再驗過，數字可能偏高。"


def top_decks(results, rounds, deck, cards, n=3, min_games=500):
    """依各副牌的目前估計排名。候選只驗一次，分數含挑選偏差，所以採用牌組一定留在榜上，每副都標身分。"""
    groups = {}
    for r in results:
        if r['n'] >= min_games: groups.setdefault(key(r['deck']), []).append(r)
    ranked = sorted(groups.items(), key=lambda kv: -estimate(kv[1])['winrate'])
    shown = list(enumerate(ranked, 1))[:n]
    final_key = key(deck) if deck is not None else None
    if final_key in groups and all(k != final_key for _, (k, _rows) in shown):
        shown[-1] = next(x for x in enumerate(ranked, 1) if x[1][0] == final_key)
    adopted = {key(x['deck']) for x in rounds}
    out = []
    for rank, (k, rows) in shown:
        best = estimate(rows)
        kind = 'final' if k == final_key else 'past' if k in adopted else 'cand'
        cs = [dict(card(no, cards), img=cards.get(no, {}).get('img'), ev=bool(cards.get(no, {}).get('ev')), count=cnt)
              for no, cnt in best['deck'].items()]
        out.append(dict(stat(best), rank=rank, move=best['move'], round=best['round'], kind=kind,
                        why=describe(best, kind, rounds, rows), cards=sorted(cs, key=lambda c: (c['ev'], c['no']))))
    return out


def net_change(rounds, deck, cards):
    if not rounds or deck is None: return {'in': [], 'out': []}
    start = rounds[0]['deck']
    diff = lambda a, b: [dict(card(c, cards), count=n - b.get(c, 0)) for c, n in a.items() if n > b.get(c, 0)]
    return {'in': diff(deck, start), 'out': diff(start, deck)}


def stage_info(rounds, results, finished):
    """目前輪走到哪一段，以及上一輪同一段花多久（本階段 ETA 的依據；總輪數未知，不估整體）。"""
    if finished or not rounds: return None
    cur, prev = rounds[-1], rounds[-2] if len(rounds) > 1 else None
    step = min(len(cur['stage_secs']), 2)
    expect, s = None, prev['stage_secs'] if prev else []
    if step == 0 and s:
        expect = s[0]
    elif step == 1 and len(s) == 2:
        expect = s[1] - s[0]
    elif step == 2 and len(s) == 2 and len(rounds) > 2:  # log 沒記複驗耗時：用整輪間隔扣掉粗篩累計
        ts = {r['round']: r['t'] for r in results}
        if prev['round'] in ts and rounds[-3]['round'] in ts:
            expect = ts[prev['round']] - ts[rounds[-3]['round']] - prev['stage_secs'][1]
    return dict(round=cur['round'], k=cur['k'], step=step, candidates=cur['funnel'][0], expect_secs=expect)


def adoption(ranked):
    """複驗候選 (差值, SE, 換牌) 依差值由高到低排好，回傳第一個過門檻的；都沒過回傳 None。"""
    return next((c for c in ranked if c[0] > THRESHOLD * c[1]), None)


def decision(rounds):
    """最近一次有結論的輪次。out_evo_r2 以前的搜尋只檢查差值最高的候選，較低的候選可能過了門檻卻沒被採用，要分開講。"""
    done = [r for r in rounds if r['recheck'] or r['no_candidate']]
    if not done: return None
    last = done[-1]
    adopted = next((c for c in last['recheck'] if c['adopted']), None)
    passed, closest = None, None
    if adopted is None:
        passed = next((c for c in last['recheck'] if c['ratio'] > THRESHOLD), None)
        rejected = []
        for r in reversed(done):
            if r['adopted']: break
            rejected += r['recheck']
        closest = max((c for c in rejected if 0 < c['ratio'] <= THRESHOLD), key=lambda c: c['ratio'], default=None)
    return dict(round=last['round'], adopted=adopted, passed=passed, closest=closest,
                gap=THRESHOLD - closest['ratio'] if closest else None)


def is_this_search(cmdline, out_name):
    """search.py 的輸出目錄在命令列上；別的輸出目錄的搜尋不算這次。"""
    return 'search.py' in cmdline and out_name in cmdline


def verdict(s):
    p = s['proc']
    if p is None: return 'unknown'
    if p['main'] == 0: return 'done' if s['finished'] else 'dead'
    if s['busy'] is not None and s['busy'] < 0.2: return 'stall'
    stage = s['stage']
    if stage and s['age'] is not None:  # 單一 worker 空轉時 CPU 還有 1 核，光看 CPU 抓不到
        expect = stage['expect_secs']
        if s['age'] > (max(3 * expect, STALE_FLOOR) if expect else STALE_NO_ESTIMATE): return 'stall'
    return 'run'


def job_progress(step, text):
    """(已完成, 總數, 剩餘秒數, 是否跑完)。lines 型每完成一項印一行 JSON，log 沒有耗時，用 est 按比例估。"""
    text = text or ''
    if step['kind'] == 'lines':
        done, total = sum(line.startswith('{') for line in text.splitlines()), step['total']
        return done, total, step.get('est') and step['est'] * (total - done) / total, done >= total
    finished = any(line.startswith('done ') for line in text.splitlines())
    rows = [tuple(map(int, row)) for row in COUNTER.findall(text)]
    if not rows: return None, None, None, finished
    done, total, secs = rows[-1]
    start = rows[max(0, len(rows) - 1 - PACE_LINES)] if len(rows) > 1 else (0, total, 0)
    return done, total, (secs - start[2]) * (total - done) / (done - start[0]) if done > start[0] else None, finished


def round_progress(rnd, k, stage, done, total, plan, t0, now):
    """search.py 寫給面板的本輪進度。plan 是三段預計場數；done、total 是目前這段的實際場數，總場數用它取代預計值。"""
    before = sum(plan[:stage])
    return dict(round=rnd, k=k, stage=stage, done=before + done, total=before + total + sum(plan[stage + 1:]), secs=now - t0)


def job_status(step, text=None, running=False, age=None, search_kind=None, progress=None):
    """流程一步的狀態、進度與剩餘秒數。text 是 log 內容，None 表示 log 還沒建立；running＝程序在不在，None 表示讀不到程序清單。"""
    done = total = None
    extra = {}
    eta = step.get('est')
    if step['kind'] == 'manual':
        status = step['status']
        if status == 'running': eta = None  # 沒有東西在倒數，est 不會變，完成時間會一直往後推
    elif step['kind'] == 'search':
        status = SEARCH_STATUS[search_kind] if text else 'pending'
        if progress and status in ('running', 'stall'):  # 百分比只到本輪：總輪數未定，eta_secs 維持空的，不算進全流程完成時間
            done, total = progress['done'], progress['total']
            extra = dict(label=f"第 {progress['round']} 輪 · {ROUND_STAGES[progress['stage']]}",
                         round_eta=progress['secs'] * (total - done) / done if done else None)
    else:
        done, total, left, finished = job_progress(step, text)
        if left is not None: eta = left
        if finished: status = 'done'
        elif running is None: status = 'unknown'
        elif running: status = 'stall' if age is not None and age > STALE_NO_ESTIMATE else 'running'
        else: status = 'failed' if text is not None else 'pending'
    if status == 'done': eta = 0
    pct = 100 if status == 'done' else done / total * 100 if total and status != 'pending' else None
    return dict(step, status=status, done=done, total=total, pct=pct, eta_secs=eta, age=age, **extra)


def pipeline(jobs, now):
    """整條流程的總覽。沒有估計時間的步驟不算進完成時間，另外列在 unestimated。"""
    if not jobs: return None
    has = lambda *names: any(j['status'] in names for j in jobs)
    kind = ('dead' if has('failed') else 'run' if has('running') else 'stall' if has('stall') else
            'unknown' if has('unknown') else 'wait' if has('pending') else 'done')
    current = next((j for j in jobs if j['status'] in ('running', 'stall')), None)
    unfinished = [j for j in jobs if j['status'] in ('running', 'stall', 'pending')]
    remaining = sum(j['eta_secs'] for j in unfinished if j['eta_secs'] is not None)
    return dict(kind=kind, current=current, done=sum(j['status'] == 'done' for j in jobs), total=len(jobs),
                finish_at=now + remaining if current and current['eta_secs'] is not None and remaining else None,  # 目前這步估不出時間，總時間就算不出來
                unestimated=[j['title'] for j in unfinished if j['eta_secs'] is None])


def holdout_summary(verify):
    """留出對手驗證的輸出 → 面板要顯示的最終牌組結果；還沒驗證回傳 None。"""
    if verify is None: return None
    return dict(wr=verify['weighted']['final'], diff=verify['diffs']['final']['diff'], se=verify['diffs']['final']['se'])


def snapshot(log_text, results, cards):
    rounds, forced, finished = parse_log(log_text, cards)
    for rd in rounds:
        c = next((r for r in reversed(results) if r['round'] == rd['round'] and is_recheck(r)), None)
        rd['cur'] = c and stat(c)
    deck = current_deck(rounds, results)
    return dict(rounds=rounds, forced=forced, finished=finished, final=headline(deck, results),
                tops=top_decks(results, rounds, deck, cards), net=net_change(rounds, deck, cards),
                stage=stage_info(rounds, results, finished), decision=decision(rounds))
