"""產生「換卡方案」給 compare2.py／gauntlet.py（勝率搜尋用，不是單人指標）。
用法：python -I -X utf8 gen_variants.py <cards_data.js> <base.json> <out_variants.json> [選項]
選項（都可省略）：
  --pool 學校1,學校2   候選卡池的學校；'*' = 全部學校（預設 '*'）
  --extra-no-skill     另外加入所有學校的無技能卡（混校用；指定學校時才有意義）
  --kinds CHARACTER,EVENT   只換這些種類（預設 CHARACTER,EVENT）
  --outs 卡號,...      只拿這些卡當「換掉」的對象（預設：牌組內全部卡號）
  --ins 卡號,...       只用這些卡當「換入」的對象（預設：整個卡池）
  --k 1                每個方案一次換幾張（同一種卡 k 張換成另一種卡 k 張）
  --positions S,WS,MB,Li,... 換入的角色必須有這些位置之一（事件不受限）
  --sample N --seed S  方案太多時隨機抽 N 個（預設全部）
產生的方案保證：總數 40 張、事件 ≤8 張【總則 4-1-2】；技能卡只會來自 MANUAL（已結構化）。
方案名：「換 k 張 卡號(卡名) → 卡號(卡名)」。"""
import sys, os, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim2
from optimize import pool_for


def make(U, base, pool, kinds=('CHARACTER', 'EVENT'), outs=None, ins=None, k=1, positions=None):
    nm = lambda no: '%s(%s)' % (no.replace('HV-', ''), U[no]['name'])
    n_ev = sum(n for no, n in base.items() if U[no]['category'] == 'EVENT')
    cand_in = [no for no in (ins or pool) if no in U and U[no]['category'] in kinds]
    if positions:
        ps = set(positions)
        cand_in = [no for no in cand_in if U[no]['category'] == 'EVENT'
                   or ps & {p.strip() for p in (U[no].get('position') or '').split(',')}]
    cand_out = [no for no in (outs or list(base)) if no in base and base[no] >= k and U[no]['category'] in kinds]
    V = {}
    for o in cand_out:
        for i in cand_in:
            if i == o: continue
            ev_after = n_ev - (k if U[o]['category'] == 'EVENT' else 0) + (k if U[i]['category'] == 'EVENT' else 0)
            if ev_after > 8: continue
            V['換 %d 張 %s → %s' % (k, nm(o), nm(i))] = {'out': {o: k}, 'in': {i: k}}
    return V


if __name__ == '__main__':
    a = sys.argv[1:]
    path, basef, outf = a[0], a[1], a[2]
    opt = {}; i = 3
    while i < len(a):
        if a[i] == '--extra-no-skill': opt['extra'] = True; i += 1
        else: opt[a[i][2:]] = a[i + 1]; i += 2
    U = sim2.load_cards(path); base = json.load(open(basef, encoding='utf8'))
    pool_schools = opt.get('pool', '*')
    pool = pool_for(U, '*' if pool_schools == '*' else pool_schools.split(','), opt.get('extra', False))
    V = make(U, base, pool, kinds=tuple(opt.get('kinds', 'CHARACTER,EVENT').split(',')),
             outs=opt['outs'].split(',') if 'outs' in opt else None, ins=opt['ins'].split(',') if 'ins' in opt else None,
             k=int(opt.get('k', 1)), positions=opt['positions'].split(',') if 'positions' in opt else None)
    if 'sample' in opt and int(opt['sample']) < len(V):
        r = random.Random(int(opt.get('seed', 1)))
        V = dict(r.sample(sorted(V.items()), int(opt['sample'])))
    json.dump(V, open(outf, 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    print('卡池 %d 張；產生 %d 個方案 → %s' % (len(pool), len(V), outf))
