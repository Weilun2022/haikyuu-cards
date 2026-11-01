# 2026-10-28 Issue #118 A1：名字限制入口驗證
# 馬門 P04-037 鎖「本回合接球區不能登場百沢 雄大」＋人名規則（接球≠舉球）同時成立時，
# 雙名卡 P03-077「日向・百沢」兩個名字都不合法 → 技能入口必須在移動任何卡之前就放棄，不能以百沢登場。
import os, sys, random
import pytest
for k in ('DH_BATCH5', 'DH_BATCH6', 'DH_BATCH7', 'DH_BATCH8'): os.environ[k] = '1'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
FILL = 'HV-P04-033'  # 角川百沢（無技能、單名）
DUAL = 'HV-P03-077'  # 日向・百沢（無技能、雙名）
HINATA, MOMO = '日向 翔陽', '百沢 雄大'
LOCK = [dict(rule='cannot_enter_name', role='receive', name=MOMO)]
opp = sim2.Player([C('HV-P01-050')] * 20, random.Random(3), 'O')


def board(lock, toss_name):
    P = sim2.Player([C(FILL)] * 20, random.Random(11), 'A')
    for z in ('block', 'receive', 'toss', 'attack'): P.zones[z] = [C(FILL)]
    P.restrict = list(LOCK) if lock else []
    T = sim2.newT(opp, 1, 'attack'); T['phase'] = 'receive'
    if toss_name: T['names']['toss'] = toss_name
    return P, T


def snap(P):
    return ({z: [id(c) for c in st] for z, st in P.zones.items()}, [id(c) for c in P.hand], [id(c) for c in P.drop])


# ── 四個實際技能入口：(擺放, 觸發) ──
def _place_recv_guts(P, T, c): P.zones['receive'].insert(0, c)
def _fire_guts_to_zone(P, T): sim2.apply_effects([dict(type='guts_to_zone', zone='receive')], P, T, 'receive')  # apply_effects 的 guts_to_zone 通用分支

def _place_atk_guts(P, T, c): P.zones['attack'].insert(0, c)
def _fire_summon(P, T): sim2.fx_summon_from_guts(dict(type='summon_from_guts', **{'from': ['attack']}, to='receive', set_to=99), P, T, 'receive')  # best_guts_pull

def _place_drop(P, T, c): P.drop.append(c); T['hs_card'] = c
def _fire_hand_card(P, T): sim2.fx_hand_card_enter(dict(type='hand_card_enter', zone='receive'), P, T, 'receive')  # 五色 P03-011 型手牌技

def _place_holder(P, T, c): P.zones['attack'].append(c); T['trig_holder'] = c; T['trig_hz'] = 'attack'
def _fire_holder(P, T): sim2.fx_holder_move(dict(type='holder_move', to='receive'), P, T, 'attack')

ENTRIES = dict(guts_to_zone=(_place_recv_guts, _fire_guts_to_zone), summon_from_guts=(_place_atk_guts, _fire_summon),
               hand_card_enter=(_place_drop, _fire_hand_card), holder_move=(_place_holder, _fire_holder))


def run(key, lock, toss_name, no=DUAL):
    place, fire = ENTRIES[key]
    P, T = board(lock, toss_name); card = C(no)
    place(P, T, card); before = snap(P)
    fire(P, T)
    return P, T, before, P.zones['receive'][-1] is card


KEYS = pytest.mark.parametrize('k', list(ENTRIES))


# 1. 交集反例：鎖百沢＋舉球已是日向 → 077 沒有合法名字，入口必須整條放棄，盤面完全不動
@KEYS
def test_dual_name_no_legal_name_rejected_before_any_move(k):
    P, T, before, entered = run(k, lock=True, toss_name=HINATA)
    assert T['names'].get('receive') != MOMO, '被鎖時仍以百沢登場接球區'
    assert not entered, '沒有合法名字卻登場了'
    assert snap(P) == before, '拒絕時卡區／手牌／棄牌被動過'
    assert T['names'].get('receive') is None


# 2. 只有鎖、舉球沒定名 → 077 以日向登場
@KEYS
def test_lock_only_enters_as_hinata(k):
    P, T, before, entered = run(k, lock=True, toss_name=None)
    assert entered
    assert T['names']['receive'] == HINATA


# 3. 沒鎖、舉球是日向 → 077 照舊以百沢登場（未鎖名字不受影響）
@KEYS
def test_no_lock_toss_hinata_enters_as_momozawa(k):
    P, T, before, entered = run(k, lock=False, toss_name=HINATA)
    assert entered
    assert T['names']['receive'] == MOMO


# 4. 單名百沢卡被鎖 → 照舊不能登場、盤面不動
@KEYS
def test_single_name_locked_rejected(k):
    P, T, before, entered = run(k, lock=True, toss_name=None, no=FILL)
    assert not entered
    assert snap(P) == before


# 5. 單名百沢卡沒鎖 → 照舊登場
@KEYS
def test_single_name_unlocked_enters(k):
    P, T, before, entered = run(k, lock=False, toss_name=None, no=FILL)
    assert entered
    assert T['names']['receive'] == MOMO


# 6. 鎖只限接球區：同樣狀態下 077 叫到攻擊區不受影響
def test_lock_does_not_affect_attack_zone():
    P, T = board(True, None); card = C(DUAL)
    P.zones['block'].insert(0, card)
    sim2.fx_summon_from_guts(dict(type='summon_from_guts', **{'from': ['block']}, to='attack', set_to=99), P, T, 'attack')
    assert P.zones['attack'][-1] is card


# 7. 手牌主接球路線：鎖住時 077 以日向登場（既有行為，確認不回歸）
def test_hand_receive_line_still_hinata():
    P, T = board(True, None)
    P.hand = [C(DUAL), C('HV-P04-034'), C('HV-P04-035')]
    sim2.do_receive_line(P, T, P.hand[0], P.hand[1], P.hand[2], False)
    assert T['names'].get('receive') == HINATA
