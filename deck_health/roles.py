"""V2 鏡像對打，統計每張卡實際被出到哪個位置（只算真的選中的行動）。"""
import sys, json, multiprocessing as mp
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import sim2
U = sim2.load_cards('/home/claude/haikyuu-cards/cards_data.js')
v2 = json.load(open('/home/claude/haikyuu-cards/deck_health/fuku_op8_v2.json'))
_enter = sim2.enter
def enter(P, T, zone, card, from_hand, as_side_blocker=False, name=None):
    z = 'side' if as_side_blocker else zone
    P.bump('位:%s:%s' % (card.no, z))
    return _enter(P, T, zone, card, from_hand, as_side_blocker, name)
sim2.enter = enter
_pe = sim2.play_event
def play_event(P, T, ev, zh):
    P.bump('位:%s:event' % ev.no); return _pe(P, T, ev, zh)
sim2.play_event = play_event
def job(seed):
    gs = sim2.match(U, v2, v2, 500, seed=seed); st = {}
    for g in gs:
        for side in 'AB':
            for k, v in g['stats'][side].items():
                if k.startswith('位:') or k.startswith('技能:') or k in ('一觸', '二段攻擊', '棄牌區撈回'): st[k] = st.get(k, 0) + v
    return st
if __name__ == '__main__':
    with mp.Pool(2) as p: rs = p.map(job, [5, 9])
    st = {}
    for r in rs:
        for k, v in r.items(): st[k] = st.get(k, 0) + v
    json.dump(dict(games=2000, stats=st), open('/home/claude/haikyuu-cards/deck_health/v2_roles_raw.json', 'w'), ensure_ascii=False, indent=0)
    print('done')
