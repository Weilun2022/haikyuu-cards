"""
deck_evo/card_pool.py — 卡牌池管理
管理所有可用卡牌，提供合法牌組建構與突變工具。
"""
from __future__ import annotations
import json
import random
from pathlib import Path

ROOT = Path(__file__).parent.parent
CARDS_JSON = ROOT / "cards_zh.json"

MAX_DECK  = 40
MAX_COPY  = 5
MAX_EVENT = 8

_chars:  list[str] = []
_events: list[str] = []
_all_unique: dict[str, dict] = {}   # card_no → card dict (one entry per unique card_no)


def _load():
    global _chars, _events, _all_unique
    if _all_unique:
        return
    from game_engine.card_db import load_cards, is_event, is_character
    load_cards()
    seen: set[str] = set()
    for c in json.loads(CARDS_JSON.read_text("utf-8"))["cards"]:
        cno = c["card_no"]
        if cno in seen:
            continue
        seen.add(cno)
        _all_unique[cno] = c
        if is_character(cno):
            _chars.append(cno)
        elif is_event(cno):
            _events.append(cno)


def chars() -> list[str]:
    _load(); return _chars

def events() -> list[str]:
    _load(); return _events

def get_card(cno: str) -> dict | None:
    _load(); return _all_unique.get(cno)


def detect_school(deck: dict[str, int]) -> str:
    """偵測牌組主要學校。"""
    _load()
    counts: dict[str, int] = {}
    for cno, cnt in deck.items():
        c = _all_unique.get(cno, {})
        s = c.get("school", "")
        if s:
            counts[s] = counts.get(s, 0) + cnt
    return max(counts, key=counts.get) if counts else "通用"


def chars_by_school(school: str) -> list[str]:
    """傳回屬於指定學校的角色牌列表。"""
    _load()
    return [cno for cno in _chars if _all_unique.get(cno, {}).get("school") == school]


def is_legal(deck: dict[str, int]) -> bool:
    """檢查牌組合法性：40 張、≤5 份、≤8 事件。"""
    _load()
    from game_engine.card_db import is_event
    if sum(deck.values()) != MAX_DECK:
        return False
    if any(v > MAX_COPY for v in deck.values()):
        return False
    if sum(v for k, v in deck.items() if is_event(k)) > MAX_EVENT:
        return False
    return True


def mutate(deck: dict[str, int], n_swaps: int = 3,
           low_score_cards: list[str] | None = None,
           school_lock: str | None = None) -> dict[str, int]:
    """
    突變：移除 n_swaps 張低貢獻牌，加入隨機新牌。
    low_score_cards 若提供，優先從中選擇要移除的牌。
    school_lock 若提供，角色牌只能從指定學校選取（事件牌不受限）。
    """
    _load()
    from game_engine.card_db import is_event
    new = dict(deck)
    char_pool = chars_by_school(school_lock) if school_lock else _chars
    if not char_pool:
        char_pool = _chars  # fallback: 學校無角色牌時退回全卡池

    for _ in range(n_swaps):
        # 選擇移除候選（優先低分 → 單張 → 隨機）
        if low_score_cards:
            remove_pool = [c for c in low_score_cards if c in new]
        else:
            remove_pool = []
        if not remove_pool:
            remove_pool = [k for k, v in new.items() if v == 1]
        if not remove_pool:
            remove_pool = list(new.keys())
        if not remove_pool:
            break

        remove = random.choice(remove_pool)
        is_ev_remove = is_event(remove)
        new[remove] -= 1
        if new[remove] == 0:
            del new[remove]

        # 選擇加入新牌（維持事件比例上限）
        ev_cnt = sum(v for k, v in new.items() if is_event(k))
        if is_ev_remove and ev_cnt < MAX_EVENT:
            pool = random.choice([char_pool, _events, char_pool])
        elif ev_cnt < MAX_EVENT - 1:
            pool = random.choice([char_pool, char_pool, _events])
        else:
            pool = char_pool

        for _ in range(20):
            cand = random.choice(pool)
            if new.get(cand, 0) < MAX_COPY:
                new[cand] = new.get(cand, 0) + 1
                break

    return new


def crossover(deck_a: dict[str, int], deck_b: dict[str, int],
              score_a: dict[str, float] | None = None,
              score_b: dict[str, float] | None = None,
              school_lock: str | None = None) -> dict[str, int]:
    """
    交叉兩副牌組：先保留雙親共有的牌（加權取捨），再填充隨機牌至 40 張。
    school_lock 若提供，補足時角色牌只從指定學校選取。
    """
    _load()
    from game_engine.card_db import is_event

    sa = score_a or {}
    sb = score_b or {}
    char_pool = chars_by_school(school_lock) if school_lock else _chars
    if not char_pool:
        char_pool = _chars

    # 候選牌集合（兩親所有卡，最大份數取兩者平均上限）
    all_cards = set(deck_a) | set(deck_b)
    child: dict[str, int] = {}
    ev_cnt = 0

    # 按貢獻分加權，隨機決定是否放入
    candidates = sorted(all_cards,
                        key=lambda c: max(sa.get(c, 0.5), sb.get(c, 0.5)),
                        reverse=True)
    for cno in candidates:
        max_cnt = min((deck_a.get(cno, 0) + deck_b.get(cno, 0) + 1) // 2 + 1, MAX_COPY)
        score = max(sa.get(cno, 0.5), sb.get(cno, 0.5))
        take = random.random() < score
        if not take:
            continue
        ev = is_event(cno)
        if ev and ev_cnt + max_cnt > MAX_EVENT:
            max_cnt = MAX_EVENT - ev_cnt
        if max_cnt <= 0:
            continue
        cnt = random.randint(1, max_cnt)
        if sum(child.values()) + cnt > MAX_DECK:
            cnt = MAX_DECK - sum(child.values())
        if cnt <= 0:
            break
        child[cno] = cnt
        if ev:
            ev_cnt += cnt

    # 補足至 40 張（school_lock 限制角色牌來源）
    while sum(child.values()) < MAX_DECK:
        ev_cnt = sum(v for k, v in child.items() if is_event(k))
        pool = _events if ev_cnt < MAX_EVENT and random.random() < 0.15 else char_pool
        for _ in range(20):
            cand = random.choice(pool)
            if child.get(cand, 0) < MAX_COPY:
                child[cand] = child.get(cand, 0) + 1
                break

    return child
