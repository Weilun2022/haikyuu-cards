"""deck_evo/deck_validator.py — 牌組合法性驗證（純標準庫）。"""
from __future__ import annotations

from deck_evo.card_pool import MAX_DECK, MAX_COPY, MAX_EVENT, get_card


def _is_event(card_no: str) -> bool:
    try:
        from game_engine.card_db import is_event
        return bool(is_event(card_no))
    except Exception:
        return False


def validate(deck: dict) -> dict:
    """
    驗證牌組合法性。
    deck: {"HV-P02-001": 2, ...}
    回傳: {"valid": bool, "errors": [str], "warnings": [str]}
    """
    from game_engine.card_db import load_cards
    load_cards()

    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(deck, dict) or not deck:
        return {"valid": False, "errors": ["牌組為空或格式錯誤"], "warnings": []}

    # 數量正規化
    norm: dict[str, int] = {}
    for k, v in deck.items():
        try:
            iv = int(v)
        except (TypeError, ValueError):
            errors.append(f"卡片 {k} 數量非整數：{v!r}")
            continue
        if iv <= 0:
            warnings.append(f"卡片 {k} 數量為 {iv}，已忽略")
            continue
        norm[str(k)] = iv

    total = sum(norm.values())

    # 規則 1：總張數 = 40
    if total != MAX_DECK:
        errors.append(f"總張數須為 {MAX_DECK}，目前為 {total}")

    # 規則 2：同名 ≤ 5
    for k, v in norm.items():
        if v > MAX_COPY:
            errors.append(f"卡片 {k} 數量 {v} 超過上限 {MAX_COPY}")

    # 規則 3：事件 ≤ 8
    event_count = sum(v for k, v in norm.items() if _is_event(k))
    if event_count > MAX_EVENT:
        errors.append(f"事件卡共 {event_count} 張，超過上限 {MAX_EVENT}")

    # 規則 4：角色牌學校唯一性
    schools: dict[str, int] = {}
    unknown: list[str] = []
    for k, v in norm.items():
        if _is_event(k):
            continue
        c = get_card(k)
        school = c.get("school", "") if c else ""
        # 排除通用/其他/ユース（這些可跨牌組使用）
        if school and school not in ("其他", "通用", "ユース", ""):
            schools[school] = schools.get(school, 0) + v
        elif not school:
            unknown.append(k)

    if len(schools) > 1:
        errors.append(f"牌組混入多所學校：{sorted(schools)}（須單一學校）")
    if unknown:
        warnings.append(f"以下角色牌無法判定學校：{unknown[:5]}{'...' if len(unknown) > 5 else ''}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
