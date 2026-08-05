# -*- coding: utf-8 -*-
"""apply_qa_fixes.py 的內容比對邏輯回歸測試。

用合成的 qa 陣列（不需要真實的 qa_data_zh.json 語料）測 find_fix_target()/apply_fixes()：
- 找得到 anchor 時正確定位並套用
- 已經套用過的（目標欄位已經等於新值）視為 no-op，不報錯
- 找不到、或找到超過一筆，都要直接丟例外，不能靜默跳過或誤改
"""
import pytest

import apply_qa_fixes as aqf


def test_find_fix_target_locates_by_anchor_when_not_yet_applied():
    qa_array = [
        {"question_zh": "問題A", "answer_zh": "包含 Miyaji 的舊翻譯"},
        {"question_zh": "問題B", "answer_zh": "無關的另一筆"},
    ]
    idx = aqf.find_fix_target(
        qa_array,
        target_fields={"answer_zh": "正確翻譯"},
        anchor_fields={"answer_zh": "Miyaji"},
    )
    assert idx == 0


def test_find_fix_target_returns_none_when_already_applied():
    qa_array = [
        {"question_zh": "問題A", "answer_zh": "正確翻譯"},  # 已經是目標值
    ]
    idx = aqf.find_fix_target(
        qa_array,
        target_fields={"answer_zh": "正確翻譯"},
        anchor_fields={"answer_zh": "Miyaji"},  # anchor 找不到也沒關係，已經套用過了
    )
    assert idx is None


def test_find_fix_target_raises_when_anchor_not_found():
    qa_array = [
        {"question_zh": "問題A", "answer_zh": "完全不相關的內容"},
    ]
    with pytest.raises(ValueError, match="anchor 沒有命中"):
        aqf.find_fix_target(
            qa_array,
            target_fields={"answer_zh": "正確翻譯"},
            anchor_fields={"answer_zh": "Miyaji"},
        )


def test_find_fix_target_raises_when_anchor_matches_multiple():
    qa_array = [
        {"question_zh": "問題A", "answer_zh": "包含 Miyaji 第一筆"},
        {"question_zh": "問題B", "answer_zh": "包含 Miyaji 第二筆"},
    ]
    with pytest.raises(ValueError, match="命中超過一筆"):
        aqf.find_fix_target(
            qa_array,
            target_fields={"answer_zh": "正確翻譯"},
            anchor_fields={"answer_zh": "Miyaji"},
        )


def test_find_fix_target_raises_when_target_already_matches_multiple():
    qa_array = [
        {"answer_zh": "正確翻譯"},
        {"answer_zh": "正確翻譯"},
    ]
    with pytest.raises(ValueError, match="目標欄位命中超過一筆"):
        aqf.find_fix_target(
            qa_array,
            target_fields={"answer_zh": "正確翻譯"},
            anchor_fields=None,
        )


def test_find_fix_target_raises_when_no_anchor_and_not_applied():
    qa_array = [{"answer_zh": "完全不相關"}]
    with pytest.raises(ValueError, match="沒有提供 anchor"):
        aqf.find_fix_target(qa_array, target_fields={"answer_zh": "正確翻譯"}, anchor_fields=None)


def test_apply_fixes_updates_matching_entry_and_counts_changed_fields():
    data = {
        "HV-TEST-001": [
            {"question_zh": "Q", "answer_zh": "包含 Miyaji 的舊翻譯"},
        ],
    }
    fixes = {
        "HV-TEST-001": [
            {"anchor": {"answer_zh": "Miyaji"}, "set": {"answer_zh": "正確翻譯"}},
        ],
    }
    changed = aqf.apply_fixes(data, fixes)
    assert changed == 1
    assert data["HV-TEST-001"][0]["answer_zh"] == "正確翻譯"


def test_apply_fixes_is_idempotent_on_second_run():
    data = {
        "HV-TEST-001": [
            {"question_zh": "Q", "answer_zh": "包含 Miyaji 的舊翻譯"},
        ],
    }
    fixes = {
        "HV-TEST-001": [
            {"anchor": {"answer_zh": "Miyaji"}, "set": {"answer_zh": "正確翻譯"}},
        ],
    }
    aqf.apply_fixes(data, fixes)
    changed_second_run = aqf.apply_fixes(data, fixes)
    assert changed_second_run == 0  # 第二次跑，已經套用過，no-op，不報錯


def test_apply_fixes_warns_on_missing_card_no_without_raising():
    data = {}  # 完全沒有這個 card_no
    fixes = {
        "HV-MISSING": [
            {"anchor": {"answer_zh": "x"}, "set": {"answer_zh": "y"}},
        ],
    }
    changed = aqf.apply_fixes(data, fixes)
    assert changed == 0


def test_all_real_fixes_table_entries_are_well_formed():
    # 不需要真實 qa_data_zh.json 語料，只驗證 FIXES 表本身的結構完整性：
    # 每筆修正都要有 anchor 跟 set，set 不能是空字典。
    for card_no, entries in aqf.FIXES.items():
        assert entries, f"{card_no} 沒有任何修正項目"
        for fix in entries:
            assert fix.get("set"), f"{card_no} 有一筆修正缺少 set"
            assert fix.get("anchor"), f"{card_no} 有一筆修正缺少 anchor"
