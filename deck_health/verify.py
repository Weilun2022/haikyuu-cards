"""結構化卡片的自動檢查 + 反向翻譯成中文，供人工驗收。
用法：python -I verify.py <cards_data.js> [card_no ...]
檢查只能抓「結構跟原文對不上」的錯，不能證明結構正確；最終以人工驗收與官方 Q&A 為準。"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from manual_cards import MANUAL

ZONE = dict(serve='發球區', block='攔網區', receive='接球區', toss='舉球區', attack='攻擊區', any='任一區')
PHASE = dict(draw='抽牌', receive='接球', toss='舉球', attack='攻擊', block='攔網', serve='發球')
STAT = dict(srv='發球值', blk='攔網值', rcv='接球值', tos='舉球值', atk='攻擊值', any='任一數值')
WHO = dict(self='自己', opp='對手')
DUR = dict(this_turn='此回合中', next_opp_turn='對手下一回合中')


def load_cards(path):
    s = open(path, encoding='utf-8').read()
    d = json.loads(s[s.index('{'):s.rstrip().rstrip(';').rindex('}') + 1])
    u = {}
    for c in d['cards']:
        u.setdefault(c['card_no'], c)
    return u


def tgt(t):
    if t == 'this': return '此角色'
    if t == 'that': return '該角色'
    if t == 'same': return '同一角色'
    s = WHO[t['who']] + '的'
    if t.get('school'): s += t['school']
    if t.get('position'): s += t['position'] + '的'
    if t.get('role'): s += {'toss': '舉球', 'attack': '攻擊', 'receive': '接球'}[t['role']] + '角色'
    else: s += '角色'
    return s + f"{t.get('count', 1)}人"


def cond(c):
    t = c['type']
    of = dict(serve='發球', attack='攻擊', serve_or_attack='發球或攻擊')
    if t == 'set_total_le': return f"雙方 Set 牌合計 ≤{c['n']}"
    if t == 'opp_op_le': return f"對手{of[c['of']]}的進攻值 ≤{c['n']}"
    if t == 'opp_op_ge': return f"對手{of[c['of']]}的進攻值 ≥{c['n']}"
    if t == 'opp_hand_le': return f"對手手牌 ≤{c['n']} 張"
    if t == 'self_is_role': return '此角色是舉球角色' if c['role'] == 'toss' else f"此角色是{c['role']}角色"
    if t == 'self_role_name':
        return f"自己的{'舉球' if c['role']=='toss' else '攻擊'}角色是「{c['name']}」"
    if t == 'event_zone_count_le':
        return f"{WHO[c['who']]} Event 區的「{c['card_name']}」≤{c['n']} 張" + ('（含這張）' if c.get('includes_self') else '')
    if t == 'event_zone_phase_count_ge':
        return f"{WHO[c['who']]} Event 區可在{'/'.join(PHASE[p] for p in c['phases'])}打出的牌合計 ≥{c['n']} 張"
    return json.dumps(c, ensure_ascii=False)


def cost(c):
    t = c['type']
    if t == 'guts': return f"從此卡底下支付 {c['n']} Guts"
    if t == 'mill': return f"棄置{WHO[c['who']]}牌庫頂 {c['n']} 張"
    if t == 'discard_hand': return f"從手牌棄置 {c['n']} 張"
    if t == 'discard_this_from_hand': return '從手牌棄置此卡'
    if t == 'this_to_deck_bottom': return '此卡放到自己牌庫底'
    return json.dumps(c, ensure_ascii=False)


def eff(e):
    t = e['type']
    if t == 'draw': s = f"{WHO[e['who']]}抽 {e['n']} 張"
    elif t == 'discard_hand': s = f"{WHO[e['who']]}從手牌棄置 {e['n']} 張"
    elif t == 'stat_add': s = f"{tgt(e['target'])}的{STAT[e['stat']]} +{e['n']}"
    elif t == 'stat_set': s = f"{tgt(e['target'])}的{STAT[e['stat']]}設為 {e['value']}"
    elif t == 'stat_cap': s = f"{DUR[e['duration']]}，此角色的{STAT[e['stat']]}不會因技能達到 {e['below']} 以上"
    elif t == 'reveal_top_take':
        s = f"公開{WHO[e['who']]}牌庫頂 {e['n']} 張，其中「{'」或「'.join(e['names'])}」最多 {e['max']} 張加入手牌，其餘放牌庫底"
    elif t == 'aura_on_enter':
        s = f"{DUR[e['duration']]}，每當{WHO[e['who']]}的「{e['name']}」出場，該角色{STAT[e['stat']]} +{e['n']}"
    elif t == 'drop_to_hand':
        f = e['filter']; s = f"從{WHO[e['who']]}棄牌區將{f.get('school','')}{'角色' if f.get('category')=='CHARACTER' else ''}牌最多 {e['max']} 張加入手牌"
    elif t == 'drop_to_zone':
        s = f"從{WHO[e['who']]}棄牌區使「{e['name']}」{e['max']} 張出場至{ZONE[e['zone']]}" + ('（強制）' if e.get('mandatory') else '')
        if e.get('then'): s += '，' + eff(e['then'])
    elif t == 'guts_to_zone':
        f = e.get('filter', {})
        s = f"{WHO[e['who']]}{ZONE[e['zone']]}的{f.get('position','')}Guts {'最多 ' if not e.get('exact') else ''}{e['max']} 張出場至{ZONE[e['zone']]}"
    elif t == 'event_to_hand': s = f"從{WHO[e['who']]} Event 區將只能在{PHASE[e['filter']['only_phase']]}打出的牌最多 {e['max']} 張加入手牌"
    elif t == 'restrict_opp':
        role = {'receive': '接球', 'block': '攔網'}[e['role']]
        if e['rule'] == 'cannot_enter': s = f"{DUR[e['duration']]}，對手不能出場原本{STAT['rcv']} ≥{e['base_rcv_ge']} 的{role}角色"
        else: s = f"{DUR[e['duration']]}，對手最多只能出場 {e['max']} 名{role}角色"
    elif t == 'on_opp_non_draw_add_mill': s = f"{DUR[e['duration']]}，每當對手以抽牌以外的方式把牌加入手牌，棄置對手牌庫頂 {e['n']} 張"
    elif t == 'keyword': s = f"［{e['name']}({e['n']})］"
    else: s = json.dumps(e, ensure_ascii=False)
    if e.get('if'): s = '若' + '且'.join(cond(c) for c in e['if']) + '：' + s
    return s


def render(sk):
    head = []
    if sk['timing'] == 'event': head.append(f"［事件・{'/'.join(PHASE[p] for p in sk['phases'])}階段］")
    elif sk['timing'] == 'from_hand': head.append(f"［{'/'.join(PHASE[p] for p in sk['phases'])}階段・從手牌］")
    elif sk['timing'] == 'on_enter': head.append(f"［登場到{'/'.join(ZONE[z] for z in sk['zones'])}時］")
    elif sk['timing'] == 'trigger':
        tr = sk['trigger']
        if tr['event'] == 'enter':
            head.append(f"［常駐］自己從手牌出場原本攻擊值 {tr['base_atk']} 的攻擊角色時")
        else:
            head.append('［常駐］自己攻擊階段中，從手牌打出事件牌時')
    parts = []
    if sk.get('conditions'): parts.append('條件：' + '，'.join(cond(c) for c in sk['conditions']))
    if sk.get('cost'): parts.append('代價：' + '，'.join(cost(c) for c in sk['cost']))
    parts.append('效果：' + '；'.join(eff(e) for e in sk['effects']))
    return head[0] + ' ' + ' ／ '.join(parts)


def walk_nums(o, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ('note',): continue
            if isinstance(v, bool): continue
            if isinstance(v, int): acc.add(v)
            else: walk_nums(v, acc)
    elif isinstance(o, list):
        for v in o: walk_nums(v, acc)
    return acc


def has_key_val(o, val):
    return val in json.dumps(o, ensure_ascii=False)


def check(card, skills):
    jp = card['skill_jp']
    issues = []
    jp_nums = {int(x) for x in re.findall(r'\d+', jp)}
    st_nums = walk_nums(skills, set())
    miss = jp_nums - st_nums
    extra = {n for n in st_nums - jp_nums if n != 1}  # 「1」常是隱含的最多 1 張／1 人
    if miss: issues.append(f'原文數字未出現在結構中：{sorted(miss)}')
    if extra: issues.append(f'結構中有原文沒有的數字：{sorted(extra)}')
    pairs = [('相手', '"opp'), ('ガッツ払', '"guts"'), ('引', '"draw"'), ('デッキの下', 'deck_bottom'),
             ('ドロップエリアから', 'drop_to_'), ('イベントエリアから', 'event_to_hand'), ('登場させられない', 'restrict_opp')]
    blob = json.dumps(skills, ensure_ascii=False)
    for jw, sw in pairs:
        a, b = jw in jp, sw in blob
        if jw == '引' and re.sub(r'引く以外', '', jp).find('引') < 0: a = False  # 「抽牌以外」是否定語
        if a and not b: issues.append(f'原文有「{jw}」，結構沒有對應')
        if b and not a and jw != '相手': issues.append(f'結構有 {sw}，原文沒有「{jw}」')
    if '相手' not in jp and ('"opp"' in blob):
        # 對手條件類（opp_op_*、opp_hand_*）由 type 名稱表達
        issues.append('結構含對手主體，但原文沒有「相手」')
    return issues


if __name__ == '__main__':
    U = load_cards(sys.argv[1])
    only = sys.argv[2:] or list(MANUAL)
    out = []
    for no in only:
        c = U[no]; sk = MANUAL[no]
        out.append(dict(card_no=no, name=c['name_zh'], jp=c['skill_jp'], zh=c['skill_zh'],
                        render=[render(s) for s in sk], issues=check(c, sk),
                        qa=[q['question'] + ' → ' + q['answer'] for q in c['qa']]))
    json.dump(out, open('verify_out.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for r in out:
        print(f"== {r['card_no']} {r['name']}  {'⚠ ' + '；'.join(r['issues']) if r['issues'] else '✓ 自動檢查通過'}")
        for s in r['render']: print('   ', s)
