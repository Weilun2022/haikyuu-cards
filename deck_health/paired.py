"""A2 配對評估（最小版）：candidate 與 baseline 用同一個 seed、同一個對手各打一場，形成一個 pair。
- 座位固定：candidate／baseline 都坐 A，對手坐 B（sim2.play_game 的 A／B）。
- 每個 half 都用全新的 random.Random(seed)、全新建的牌（卡序固定、技能 dict 深拷貝），所以執行順序（schedule）不影響結果。
- 所有對手在同一個 pair block 共用同一個 seed（研究封存要求每個對手都逐一覆蓋宣告的 seeds）。
  seed 由 derive_seed(experiment_id, block_id)（paired-seed-v1）決定，不含對手、不看 Python hash、執行順序或分批。
- metric 只接受 win=1／loss=0；平手、未知勝方、例外都算該 half 失敗，整個 pair 不列入有效結果，run 標為 incomplete／不可用。
- 彙總只做逐對手；不合併不同對手的統計。
- 未交付：低優先權（IDLE）與 multiprocessing；本模組只在目前行程內依序執行。
輸出形狀對應 data/deck-health/schemas/research-archive.schema.json 的 conclusions[].pairing／pair_results／pairs。"""
import copy, hashlib, json, math, os, platform, random, subprocess, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2
from manual_cards import MANUAL, NAME_CHOICE

SEATS = {'candidate': 'A', 'baseline': 'A', 'opponent': 'B'}
CARD_ORDER_POLICY = 'sorted-card-no-then-copies'  # 依 card_no 字元序排序、同卡連續，再交給 Player 用該 half 的 rng 洗牌
SCHEME = 'same-seed-same-opponent-candidate-vs-baseline'
METRIC = dict(name='win', value_map=dict(win=1, loss=0, draw=0))  # draw 只為符合 schema 必填；本階段平手一律拒收
OUTCOME = {SEATS['candidate']: 'win', SEATS['opponent']: 'loss'}
MAX_SEED = 2 ** 53 - 1  # 封存驗證器（JS）只認安全整數
NOT_DELIVERED = ['low_priority', 'multiprocessing']
FINGERPRINT_VERSION = 'deck-fingerprint-v1'
SEED_DERIVATION_VERSION = 'paired-seed-v1'
SEED_NAMESPACE = 'haikyuu-deck-health/paired-seed/v1'
# 執行依賴 allowlist（repo 相對路徑）：sim2 只 import manual_cards；manual_cards 依 DH_BATCHn 旗標 import manual_batch1～8；
# manual_batch*.py 沒有 import 其他專案檔。manifest 只讀這些檔，絕不讀其他 untracked／私人資料／結果／牌組。
EXECUTION_SOURCES = ('deck_health/sim2.py', 'deck_health/paired.py', 'deck_health/manual_cards.py') + \
    tuple(f'deck_health/manual_batch{i}.py' for i in range(1, 9))
SOURCE_SCOPE = 'execution-source-files'   # 只代表上列執行原始碼，不代表完整 git dirty tree 或所有 patch
MANUAL_ENV_KEYS = ('DH_PENDING', 'DH_MIXED') + tuple(f'DH_BATCH{i}' for i in range(1, 9))  # manual_cards 讀的開關，影響 MANUAL 內容
VERSIONS = dict(engine='sim2.play_game（版本以 sources.sha256／combined_sha256 與 git.head 識別）',
                strategy='sim2 內建啟發式（evaluate），雙方同一套',
                rng='python-random.Random(seed)（MT19937），每個 half 各建一個',
                seed_derivation=SEED_DERIVATION_VERSION, fingerprint=FINGERPRINT_VERSION)


class IncompleteRun(Exception):
    pass


class HalfFailure(Exception):
    pass


def deck_fingerprint(deck):
    """deck-fingerprint-v1：依 card_no 排序的 [[card_no, n], ...] 無空白 JSON 的 SHA-1。"""
    pairs = [[no, n] for no, n in sorted(deck.items()) if n > 0]
    return hashlib.sha1(json.dumps(pairs, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def _ident(x, what):
    if not isinstance(x, str) or not x:
        raise ValueError(f'{what} 必須是非空字串：{x!r}')
    return x


def derive_seed(experiment_id, block_id):
    """paired-seed-v1：SHA-256(SEED_NAMESPACE + '\\n' + canonical JSON {block_id, experiment_id})，取前 8 bytes 大端整數右移 11 位 → 0～2^53-1。"""
    payload = json.dumps(dict(block_id=_ident(block_id, 'block_id'), experiment_id=_ident(experiment_id, 'experiment_id')),
                         sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    d = hashlib.sha256((SEED_NAMESPACE + '\n' + payload).encode('utf-8')).digest()
    return int.from_bytes(d[:8], 'big') >> 11


def seed_plan(experiment_id, block_ids):
    if not isinstance(block_ids, (list, tuple)):
        raise ValueError('block_ids 必須是串列')
    return check_plan([dict(block_id=b, seed=derive_seed(experiment_id, b)) for b in block_ids])


def check_plan(plan):
    """[{block_id, seed}, ...]：非空、block_id 非空字串且不重複、seed 為 0～2^53-1 整數且不重複。"""
    if not isinstance(plan, (list, tuple)) or not plan:
        raise ValueError('seed plan 必須是非空串列')
    for p in plan:
        if not isinstance(p, dict) or set(p) != {'block_id', 'seed'}:
            raise ValueError(f'plan 項目需為 {{block_id, seed}}：{p!r}')
        _ident(p['block_id'], 'block_id')
        if type(p['seed']) is not int or not 0 <= p['seed'] <= MAX_SEED:
            raise ValueError(f"seed 必須是 0～2^53-1 的整數：{p['seed']!r}")
    for k in ('block_id', 'seed'):
        if len({p[k] for p in plan}) != len(plan):
            raise ValueError(f'plan 的 {k} 不得重複')
    return [dict(p) for p in plan]


def check_deck(U, deck):
    if not isinstance(deck, dict) or any(no not in U or type(n) is not int or n < 1 for no, n in deck.items()):
        raise ValueError('牌表需為 {card_no: 正整數}，且卡號都在卡庫內')
    if sum(deck.values()) != 40:
        raise ValueError(f'牌表必須 40 張：{sum(deck.values())}')


def build_isolated(U, deck):
    """依 CARD_ORDER_POLICY 建牌；技能 dict 與 alts 深拷貝（每次呼叫＝每場每側一份），同一副牌內的引用關係（skills／whens／handsk）保持一致。"""
    memo, L = {}, []
    for no in sorted(deck):
        for _ in range(deck[no]):
            c = sim2.Card(U[no])
            c.skills = copy.deepcopy(c.skills, memo)
            c.whens = copy.deepcopy(c.whens, memo)
            c.handsk = copy.deepcopy(c.handsk, memo)
            c.alts = copy.deepcopy(c.alts, memo)   # 原本引用 NAME_CHOICE 的 list
            L.append(c)
    return L


def play_half(play_game, U, side_deck, opp_deck, seed):
    res = play_game(build_isolated(U, side_deck), build_isolated(U, opp_deck), random.Random(seed))
    w = res.get('winner') if isinstance(res, dict) else None
    if w not in OUTCOME:
        raise HalfFailure('draw_or_unknown_winner')
    o = OUTCOME[w]
    return dict(outcome=o, metric_value=METRIC['value_map'][o])


def run_paired(U, candidate, baseline, opponents, plan, *, play_game=None, schedule=None):
    """plan 用 seed_plan() 產生。schedule 只改執行順序：(opponent_id, block_id) 任務的排列。"""
    plan = check_plan(plan)
    blocks = [p['block_id'] for p in plan]
    seed_of = {p['block_id']: p['seed'] for p in plan}
    if not isinstance(opponents, (list, tuple)) or not opponents:
        raise ValueError('至少要一個對手')
    ids = [o.get('opponent_id') for o in opponents]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('opponent_id 必須是不重複的非空字串')
    for d in [candidate, baseline] + [o['deck'] for o in opponents]:
        check_deck(U, d)
    tasks = [(o['opponent_id'], b) for b in blocks for o in opponents]
    if schedule is None:
        schedule = tasks
    elif len(schedule) != len(tasks) or Counter(map(tuple, schedule)) != Counter(tasks):
        raise ValueError('schedule 必須是 (opponent_id, block_id) 任務的排列')
    pg = play_game or sim2.play_game
    decks = {o['opponent_id']: o['deck'] for o in opponents}
    done, failures = {}, []
    for oid, b in schedule:
        s, sides = seed_of[b], {}
        for name, d in (('candidate', candidate), ('baseline', baseline)):
            try:
                sides[name] = play_half(pg, U, d, decks[oid], s)
            except HalfFailure as e:
                failures.append(dict(opponent_id=oid, block_id=b, seed=s, side=name, reason=str(e)))
            except Exception as e:
                failures.append(dict(opponent_id=oid, block_id=b, seed=s, side=name, reason='exception:' + type(e).__name__))
        if len(sides) == 2:
            done[(oid, b)] = sides
    fps = {o['opponent_id']: deck_fingerprint(o['deck']) for o in opponents}
    pair_results = []
    for b in blocks:
        for oid in ids:
            if (oid, b) in done:
                pair_results.append(dict(pair_id=json.dumps([b, oid], ensure_ascii=False, separators=(',', ':')),
                                         opponent_id=oid, opponent_fingerprint=fps[oid], seed=seed_of[b],
                                         candidate=done[(oid, b)]['candidate'], baseline=done[(oid, b)]['baseline']))
    failures.sort(key=lambda f: (blocks.index(f['block_id']), ids.index(f['opponent_id']), f['side']))
    ok = not failures and len(pair_results) == len(tasks)
    return dict(plan=plan, opponents=[dict(opponent_id=i, fingerprint=fps[i]) for i in ids],
                status='complete' if ok else 'incomplete', usable=ok,
                expected_pairs=len(tasks), completed_pairs=len(pair_results),
                pair_results=pair_results, failures=failures)


def aggregate(opponent_id, fingerprint, rows):
    n = len(rows)
    wins = sum(r['candidate']['outcome'] == 'win' for r in rows)
    bw = sum(r['baseline']['outcome'] == 'win' for r in rows)
    p = wins / n
    d = [r['candidate']['metric_value'] - r['baseline']['metric_value'] for r in rows]
    delta = se_delta = None
    if n >= 2:
        delta = sum(d) / n
        se_delta = math.sqrt(sum((x - delta) ** 2 for x in d) / (n - 1)) / math.sqrt(n)
    return dict(opponent_id=opponent_id, opponent_fingerprint=fingerprint, wins=wins, losses=n - wins, draws=0, n=n,
                win_rate=p, se=math.sqrt(p * (1 - p) / n), delta=delta, se_delta=se_delta,
                baseline=dict(wins=bw, losses=n - bw, draws=0))


def conclusion_fragment(run):
    """封存結論中與配對有關的欄位，只含逐對手彙總。不只看旗標：有任何 failure 或 pair 數不足就拒絕（否則會 seed_uncovered）。"""
    expected = len(run['plan']) * len(run['opponents'])
    if (run.get('status') != 'complete' or run.get('usable') is not True or run['failures']
            or not run['expected_pairs'] == run['completed_pairs'] == len(run['pair_results']) == expected):
        raise IncompleteRun(f"{len(run['failures'])} 個 half 失敗，完成 {len(run['pair_results'])}/{expected} pair，不能產生配對結論")
    pairs = [aggregate(o['opponent_id'], o['fingerprint'], [r for r in run['pair_results'] if r['opponent_id'] == o['opponent_id']])
             for o in run['opponents']]
    return dict(design='paired', seeds=[p['seed'] for p in run['plan']],
                pairing=dict(scheme=SCHEME, metric=copy.deepcopy(METRIC), delta_definition='mean-of-pair-differences',
                             se_delta_definition='sample-sd-of-pair-differences/sqrt(N)'),
                pair_results=run['pair_results'], pairs=pairs)


def _json_default(o):
    if isinstance(o, (set, frozenset)): return sorted(o, key=repr)
    return repr(o)


def manual_skills_hash():
    s = json.dumps(dict(MANUAL=MANUAL, NAME_CHOICE=NAME_CHOICE), sort_keys=True, ensure_ascii=False, default=_json_default)
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(args):
    return subprocess.run(['git', '-C', REPO_ROOT] + list(args), capture_output=True, check=True).stdout


def _read_source(path):
    if path not in EXECUTION_SOURCES:   # 第二道防線：allowlist 以外一律拒讀
        raise ValueError(f'不在執行原始碼 allowlist：{path}')
    with open(os.path.join(REPO_ROOT, *path.split('/')), 'rb') as f:
        return f.read()


def _source_status(raw):
    """解析 `git status --porcelain=v1 -z`；只保留 allowlist 內的路徑，其餘（含私人檔）直接丟掉、不記錄。"""
    out, toks, i = {p: 'clean' for p in EXECUTION_SOURCES}, raw.decode('utf-8', 'replace').split('\0'), 0
    while i < len(toks):
        t = toks[i]; i += 1
        if len(t) < 4: continue
        code, path = t[:2], t[3:]
        if code[0] in 'RC': i += 1   # rename／copy 後面多一個原路徑
        if path in out: out[path] = code.strip()
    return out


def manifest(candidate, baseline, git=_git, read_bytes=_read_source):
    """範圍＝execution-source-files：只 hash EXECUTION_SOURCES 的內容；git 只唯讀 rev-parse HEAD 與這些精確路徑的 status。
    不讀全 repo diff、不列 untracked、不讀任何 allowlist 以外的檔，所以不代表完整 dirty tree。"""
    head = git(['rev-parse', 'HEAD']).decode().strip()
    status = _source_status(git(['status', '--porcelain=v1', '-z', '--untracked-files=all', '--'] + list(EXECUTION_SOURCES)))
    sha, h = {}, hashlib.sha256()
    for p in sorted(EXECUTION_SOURCES):
        b, pb = read_bytes(p), p.encode('utf-8')
        sha[p] = hashlib.sha256(b).hexdigest()
        h.update(b'%d\0' % len(pb)); h.update(pb); h.update(b'\0%d\0' % len(b)); h.update(b)
    return dict(seats=dict(SEATS), card_order_policy=CARD_ORDER_POLICY, cfg=copy.deepcopy(sim2.CFG),
                decks=dict(fingerprint_version=FINGERPRINT_VERSION, candidate=deck_fingerprint(candidate), baseline=deck_fingerprint(baseline)),
                sources=dict(scope=SOURCE_SCOPE, sha256=sha, combined_sha256=h.hexdigest(),
                             manual_env={k: os.environ.get(k) for k in MANUAL_ENV_KEYS}),
                manual_skills_hash=manual_skills_hash(), metric=copy.deepcopy(METRIC), scheme=SCHEME,
                versions=dict(VERSIONS, python=platform.python_version()), not_delivered=list(NOT_DELIVERED),
                git=dict(head=head, source_status=status, sources_dirty=any(v != 'clean' for v in status.values())))
