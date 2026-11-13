# -*- coding: utf-8 -*-
"""檢查特殊卡判定表（special_cards_data.py）是否齊全、格式是否正確。

出新彈、更新 all_cards.json 之後、建置之前執行（見 docs/translation/SOP.md）：

    python check_special_cards.py

- 有格式錯誤，或有卡號應判定卻還沒判定 → 印出清單（附卡名與日文效果文字），結束碼 1。
- 只有過期條目（表裡有、資料裡已不存在或已不含「相手」）→ 印出提醒，結束碼 0。
- 全部沒問題 → 印「特殊卡判定齊全（N 筆）」，結束碼 0。

判定準則見 docs/translation/SPECIAL_CARDS.md。上半部是純函式（不讀檔、不印東西），
build_data.py 與測試共用。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_paths import ALL_CARDS_JSON
from special_cards_data import SPECIAL_CARD_ENTRIES

# 干擾對手的效果一定會提到對手，所以「效果文字含『相手』」就是應判定範圍。
OPPONENT_WORD = "相手"


def _mentions_opponent(skill) -> bool:
    return isinstance(skill, str) and OPPONENT_WORD in skill


def _card_nos_needing_review(raw_cards) -> set:
    """任一版本的 skill 含「相手」的卡號。"""
    return {c.get("card_no") for c in raw_cards
            if c.get("card_no") and _mentions_opponent(c.get("skill"))}


def pending_review(raw_cards, entries) -> list:
    """回傳應判定卻沒有判定的卡號（已排序、不重複）。

    應判定＝該卡號任一版本的 skill 含「相手」。raw_cards 是 all_cards.json 的格式
    （欄位 card_no、skill）。判定是 special 或 excluded 都算「判過了」。
    """
    judged = {e.get("card_no") for e in entries}
    return sorted(_card_nos_needing_review(raw_cards) - judged)


def stale_entries(raw_cards, entries) -> list:
    """回傳表裡有、但資料裡已不存在或已不含「相手」的卡號（官方下架或改文字）。"""
    needing = _card_nos_needing_review(raw_cards)
    return sorted({e.get("card_no") for e in entries if e.get("card_no")} - needing)


VERDICTS = ("special", "excluded")
TIERS = ("通用", "學校")
KINDS = ("封鎖", "無效", "破壞", "懲罰", "削弱")
REASONS = ("綁人名", "純數值削弱", "只讀對手狀態", "不划算", "自保或雙方對等")


def _entry_errors(entry) -> list:
    card_no = entry.get("card_no")
    if not card_no:
        return [f"缺 card_no：{entry}"]
    verdict = entry.get("verdict")
    if verdict not in VERDICTS:
        return [f"{card_no}：verdict「{verdict}」不合法，只能是 {'／'.join(VERDICTS)}"]
    if verdict == "special":
        checks = [("tier", TIERS), ("kind", KINDS)]
    else:
        checks = [("reason", REASONS)]
    errors = []
    for field, allowed in checks:
        value = entry.get(field)
        if value is None:
            errors.append(f"{card_no}：{verdict} 缺 {field}")
        elif value not in allowed:
            errors.append(f"{card_no}：{field}「{value}」不合法，只能是 {'／'.join(allowed)}")
    return errors


def validate_entries(entries) -> list:
    """回傳錯誤訊息清單：卡號重複、verdict／tier／kind／reason 不在允許值內、缺必填欄位。
    沒問題回傳空清單。"""
    errors = []
    seen = set()
    for entry in entries:
        card_no = entry.get("card_no")
        if card_no and card_no in seen:
            errors.append(f"{card_no}：卡號重複")
            continue
        seen.add(card_no)
        errors.extend(_entry_errors(entry))
    return errors


def build_special_lookup(entries) -> dict:
    """card_no → {'tier', 'kind', 'keywords'}，只收 verdict == 'special'。

    keywords 是首頁搜尋列比對用的文字，例：'特殊卡 通用特殊卡 封鎖卡'。
    格式錯誤的條目直接略過（build_data.py 在載入時呼叫，打錯字不能讓建置卡死；
    錯誤由 validate_entries／check_special_cards.py 回報）。
    """
    return {
        e["card_no"]: {
            "tier": e["tier"],
            "kind": e["kind"],
            "keywords": f"特殊卡 {e['tier']}特殊卡 {e['kind']}卡",
        }
        for e in entries if e.get("verdict") == "special" and not _entry_errors(e)
    }


# ── 命令列入口 ────────────────────────────────────────────────────────

def _describe_pending(raw_cards, card_no) -> list:
    """未判定卡號的卡名與日文效果文字（不同版本文字不同時逐一列出），方便當場判定。"""
    lines = []
    seen_skills = set()
    for c in raw_cards:
        if c.get("card_no") != card_no or not _mentions_opponent(c.get("skill")):
            continue
        if c["skill"] in seen_skills:
            continue
        seen_skills.add(c["skill"])
        lines.append(f"  {card_no} {c.get('name', '')}")
        lines.append(f"    {c['skill']}")
    return lines


def main() -> int:
    raw_cards = json.loads(Path(ALL_CARDS_JSON).read_text(encoding="utf-8"))
    entries = SPECIAL_CARD_ENTRIES

    errors = validate_entries(entries)
    pending = pending_review(raw_cards, entries)
    stale = stale_entries(raw_cards, entries)

    if errors:
        print(f"[ERROR] special_cards_data.py 格式錯誤 {len(errors)} 處：")
        for msg in errors:
            print(f"  {msg}")

    if pending:
        print(f"[ERROR] 特殊卡未判定 {len(pending)} 個卡號（效果文字含「{OPPONENT_WORD}」）：")
        for card_no in pending:
            for line in _describe_pending(raw_cards, card_no):
                print(line)
        print("請照 docs/translation/SPECIAL_CARDS.md 逐張判定，在 special_cards_data.py 各加一筆。")

    if stale:
        print(f"[提醒] 判定表裡有 {len(stale)} 個卡號在資料裡已不存在或已不含「{OPPONENT_WORD}」"
              f"（官方下架或改文字），請確認後從 special_cards_data.py 移除或重判：")
        print("  " + "、".join(stale))

    if errors or pending:
        return 1
    if not stale:
        print(f"特殊卡判定齊全（{len(entries)} 筆）")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 主控台預設不是 UTF-8，比照 build_data.py
    sys.exit(main())
