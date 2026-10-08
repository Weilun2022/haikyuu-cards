"""通用配比搜尋：用卡池典型數值的「無技能卡型」組牌，找出各類卡最順的張數。
卡型數值取自 cards_data.js 角色卡的眾數／平均（見 ARCH）。人名每 3 張一組（模擬實際牌組常見的同名 3 張）。
用法：
  python -I template.py grid <N> <out.jsonl>          粗篩：每個配比 vs 基準配比
  python -I template.py duel <N> <out.jsonl> a,b,c,d ... 指定配比（事件,接球,舉球,攻擊）兩兩對打
"""
import sys, os, json, random, itertools, time, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2

# 卡型（卡池眾數）：接球手 R、舉球手 S、攻擊手 A
ARCH = {
    'R': dict(srv=1, blk=0, rcv=5, tos=0, atk=0, position='Li'),
    'R6': dict(srv=1, blk=0, rcv=6, tos=0, atk=0, position='Li'),      # 接球手約 15% 是 6
    'S': dict(srv=2, blk=1, rcv=1, tos=1, atk=1, position='S'),
    'S2': dict(srv=2, blk=1, rcv=1, tos=2, atk=1, position='S'),       # 舉球手約 40% 是 2
    'A': dict(srv=2, blk=2, rcv=2, tos=0, atk=3, position='WS'),
    'RA': dict(srv=1, blk=1, rcv=5, tos=0, atk=3, position='WS'),     # 503，可攻可守
    'SA': dict(srv=1, blk=1, rcv=1, tos=1, atk=3, position='S'),      # 013，可舉可攻
}
# 通用事件：卡池 61/80 張事件會抽牌，常見效果是「抽 1 + 數值 +1」
GEN_EVENTS = {
    'GEN-EV-R': [dict(timing='event', phases=['receive'],
                      effects=[dict(type='draw', who='self', n=1),
                               dict(type='stat_add', target=dict(who='self', count=1), stat='rcv', n=1)])],
    'GEN-EV-A': [dict(timing='event', phases=['attack'],
                      effects=[dict(type='draw', who='self', n=1),
                               dict(type='stat_add', target=dict(who='self', count=1), stat='atk', n=1)])],
}
sim2.MANUAL.update(GEN_EVENTS)
# 通用角色技能（卡池最常見的「付 Guts 加數值」，約一半的卡帶技能）
GEN_SKILLS = {
    'GEN-A+': [dict(timing='on_enter', zones=['attack'], cost=[dict(type='guts', n=3)],
                    effects=[dict(type='stat_add', target='this', stat='atk', n=3)])],
    'GEN-R+': [dict(timing='on_enter', zones=['receive'], cost=[dict(type='guts', n=2)],
                    effects=[dict(type='stat_add', target='this', stat='rcv', n=2)])],
    'GEN-S+': [dict(timing='on_enter', zones=['toss'], cost=[dict(type='guts', n=2)],
                    effects=[dict(type='stat_add', target='this', stat='tos', n=2)])],
}
sim2.MANUAL.update(GEN_SKILLS)
SKILLED = float(os.environ.get('SKILLED', '0.5'))  # 每類帶技能的比例


def raw(no, name, cat, st=None):
    d = dict(card_no=no, name=name, category=cat, position=(st or {}).get('position', '-'),
             school='通用', school_tags=['通用'])
    for k in ('srv', 'blk', 'rcv', 'tos', 'atk'): d[k] = (st or {}).get(k, 0)
    return d


def make_deck(E, R, S, A, n6=None, n2=None, nRA=0, nSA=0):
    assert E + R + S + A == 40
    cards = []
    # 接球 6、舉球 2 的張數：可直接指定；否則看 FIX_R6 / FIX_S2；再否則依卡池比例
    if n6 is None: n6 = int(os.environ['FIX_R6']) if 'FIX_R6' in os.environ else round(R * 0.15)
    if n2 is None: n2 = int(os.environ['FIX_S2']) if 'FIX_S2' in os.environ else round(S * 0.4)
    n6, n2 = min(n6, R), min(n2, S)
    sk = lambda i, n: (i % 2 == 1) if SKILLED == 0.5 else (i < round(n * SKILLED))

    # 接球手：共 R 張，其中 nRA 張替換為 RA，其餘優先保留 n6 張 R6
    cur_r6 = min(n6, max(0, R - nRA))
    cur_r = max(0, R - nRA - cur_r6)
    for i in range(cur_r6):
        cards.append(raw('GEN-R+' if sk(i, R) else 'GEN-R', f'接{i // 3}', 'CHARACTER', ARCH['R6']))
    for i in range(cur_r):
        cards.append(raw('GEN-R+' if sk(cur_r6 + i, R) else 'GEN-R', f'接{(cur_r6 + i) // 3}', 'CHARACTER', ARCH['R']))
    for i in range(nRA):
        cards.append(raw('GEN-RA', f'攻守{i // 3}', 'CHARACTER', ARCH['RA']))

    # 舉球手：共 S 張，其中 nSA 張替換為 SA，其餘優先保留 n2 張 S2
    cur_s2 = min(n2, max(0, S - nSA))
    cur_s = max(0, S - nSA - cur_s2)
    for i in range(cur_s2):
        cards.append(raw('GEN-S+' if sk(i, S) else 'GEN-S', f'舉{i // 3}', 'CHARACTER', ARCH['S2']))
    for i in range(cur_s):
        cards.append(raw('GEN-S+' if sk(cur_s2 + i, S) else 'GEN-S', f'舉{(cur_s2 + i) // 3}', 'CHARACTER', ARCH['S']))
    for i in range(nSA):
        cards.append(raw('GEN-SA', f'舉攻{i // 3}', 'CHARACTER', ARCH['SA']))

    for i in range(A): cards.append(raw('GEN-A+' if sk(i, A) else 'GEN-A', f'攻{i // 3}', 'CHARACTER', ARCH['A']))
    for i in range(E): cards.append(raw('GEN-EV-R' if i % 2 == 0 else 'GEN-EV-A', f'事{i}', 'EVENT'))
    return [sim2.Card(c) for c in cards]


def job(args):
    a, b, n, seed = args
    rng = random.Random(seed)
    A, B = make_deck(*a), make_deck(*b)
    gs = [sim2.play_game(A, B, rng) for _ in range(n)]
    return sum(g['winner'] == 'A' for g in gs), n


def duel(pool, a, b, N, seed=7):
    res = pool.map(job, [(a, b, N // 2, seed), (a, b, N - N // 2, seed + 1000)])
    w = sum(r[0] for r in res); n = sum(r[1] for r in res)
    p = w / n
    return p, (p * (1 - p) / n) ** 0.5


if __name__ == '__main__':
    mode, N, outf = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    with mp.Pool(2) as pool, open(outf, 'a', encoding='utf-8') as fo:
        if mode == 'grid':
            ref = (8, 11, 10, 11)
            Es = [int(x) for x in os.environ.get('ES', '8,6').split(',')]
            for E in Es:
                for S in range(6, 15):
                    for R in range(6, 17):
                        A = 40 - E - S - R
                        if A < 4: continue
                        t0 = time.time()
                        p, se = duel(pool, (E, R, S, A), ref, N)
                        rec = dict(E=E, R=R, S=S, A=A, win=round(p, 4), se=round(se, 4), n=N, sec=round(time.time() - t0, 1))
                        fo.write(json.dumps(rec, ensure_ascii=False) + '\n'); fo.flush()
        elif mode in ('duel', 'vs'):  # duel：兩兩對打；vs：第一個配比當基準，其餘各自對打基準
            cfgs = [tuple(int(x) for x in s.split(',')) for s in sys.argv[4:]]
            pairs = itertools.combinations(cfgs, 2) if mode == 'duel' else [(c, cfgs[0]) for c in cfgs[1:]]
            for a, b in pairs:
                t0 = time.time(); p, se = duel(pool, a, b, N)
                rec = dict(a=a, b=b, win_a=round(p, 4), se=round(se, 4), n=N, sec=round(time.time() - t0, 1))
                fo.write(json.dumps(rec, ensure_ascii=False) + '\n'); fo.flush(); print(json.dumps(rec), flush=True)
