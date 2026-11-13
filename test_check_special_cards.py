# -*- coding: utf-8 -*-
"""check_special_cards.py 的外部行為測試。

測試資料一律寫在這個檔案裡，不讀真實的 haikyuu_output/all_cards.json。
"""
import json

import pytest

import check_special_cards as csc
from special_cards_data import SPECIAL_CARD_ENTRIES


def card(card_no, skill):
    return {"card_no": card_no, "skill": skill}


def special(card_no, tier="通用", kind="封鎖"):
    return {"card_no": card_no, "verdict": "special", "tier": tier, "kind": kind}


def excluded(card_no, reason="綁人名"):
    return {"card_no": card_no, "verdict": "excluded", "reason": reason}


# ── pending_review ────────────────────────────────────────────────────

def test_pending_review_lists_cards_mentioning_opponent_without_verdict():
    raw = [
        card("HV-P01-001", "相手のアタックを無効にする"),
        card("HV-P01-002", "相手の手札を1枚選んで捨てる"),
        card("HV-P01-003", "相手のガッツを1枚選んで捨てる"),
    ]
    entries = [special("HV-P01-002"), excluded("HV-P01-003")]

    assert csc.pending_review(raw, entries) == ["HV-P01-001"]


def test_pending_review_ignores_cards_not_mentioning_opponent():
    raw = [card("HV-P01-001", "自分のアタック+2")]

    assert csc.pending_review(raw, []) == []


def test_pending_review_lists_each_card_no_once_even_if_only_one_version_mentions_opponent():
    raw = [
        card("HV-P01-005", "自分のアタック+2"),
        card("HV-P01-005", "相手のブロック-3"),
        card("HV-P01-005", "相手のブロック-3"),
        card("HV-P01-004", "相手のレシーブ-1"),
    ]

    assert csc.pending_review(raw, []) == ["HV-P01-004", "HV-P01-005"]


@pytest.mark.parametrize("skill", [None, "", "-"])
def test_pending_review_tolerates_empty_skill(skill):
    assert csc.pending_review([card("HV-P01-001", skill)], []) == []


# ── stale_entries ─────────────────────────────────────────────────────

def test_stale_entries_lists_card_nos_missing_from_data_or_no_longer_mentioning_opponent():
    raw = [
        card("HV-P01-001", "相手のアタックを無効にする"),
        card("HV-P01-002", "自分のアタック+2"),
    ]
    entries = [excluded("HV-P01-001"), excluded("HV-P01-002"), special("HV-P09-999")]

    assert csc.stale_entries(raw, entries) == ["HV-P01-002", "HV-P09-999"]


def test_stale_entries_empty_when_every_entry_still_applies():
    raw = [card("HV-P01-001", "相手のアタックを無効にする")]

    assert csc.stale_entries(raw, [special("HV-P01-001")]) == []


# ── validate_entries ──────────────────────────────────────────────────

def test_validate_entries_accepts_well_formed_entries():
    entries = [
        special("HV-P01-001", tier="學校", kind="破壞"),
        excluded("HV-P01-002", reason="自保或雙方對等"),
    ]

    assert csc.validate_entries(entries) == []


@pytest.mark.parametrize("entries, expected_card_no", [
    ([special("HV-P01-001"), excluded("HV-P01-001")], "HV-P01-001"),            # 卡號重複
    ([{"card_no": "HV-P01-002", "verdict": "maybe"}], "HV-P01-002"),             # verdict 不合法
    ([{"card_no": "HV-P01-003", "verdict": "special", "kind": "封鎖"}], "HV-P01-003"),  # 缺 tier
    ([{"card_no": "HV-P01-004", "verdict": "special", "tier": "通用"}], "HV-P01-004"),  # 缺 kind
    ([special("HV-P01-005", tier="全國")], "HV-P01-005"),                        # tier 不合法
    ([special("HV-P01-006", kind="加值")], "HV-P01-006"),                        # kind 不合法
    ([{"card_no": "HV-P01-007", "verdict": "excluded"}], "HV-P01-007"),          # 缺 reason
    ([excluded("HV-P01-008", reason="太弱")], "HV-P01-008"),                     # reason 不合法
])
def test_validate_entries_reports_each_problem(entries, expected_card_no):
    errors = csc.validate_entries(entries)

    assert len(errors) == 1
    assert expected_card_no in errors[0]


def test_validate_entries_reports_missing_card_no():
    assert len(csc.validate_entries([{"verdict": "excluded", "reason": "綁人名"}])) == 1


def test_official_table_is_well_formed():
    assert csc.validate_entries(SPECIAL_CARD_ENTRIES) == []


# ── build_special_lookup ──────────────────────────────────────────────

def test_build_special_lookup_only_includes_special_with_search_keywords():
    lookup = csc.build_special_lookup([
        special("HV-P01-001", tier="學校", kind="破壞"),
        excluded("HV-P01-002"),
    ])

    assert lookup == {
        "HV-P01-001": {"tier": "學校", "kind": "破壞", "keywords": "特殊卡 學校特殊卡 破壞卡"},
    }
    assert "HV-P01-002" not in lookup


# ── main() 結束碼 ────────────────────────────────────────────────────

@pytest.fixture
def use_data(tmp_path, monkeypatch):
    """把 main() 的資料來源換成測試資料。"""
    def _use(raw_cards, entries):
        path = tmp_path / "all_cards.json"
        path.write_text(json.dumps(raw_cards, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(csc, "ALL_CARDS_JSON", path)
        monkeypatch.setattr(csc, "SPECIAL_CARD_ENTRIES", entries)
    return _use


def test_main_returns_0_when_every_card_is_judged(use_data, capsys):
    use_data([card("HV-P01-001", "相手の手札を捨てる")], [special("HV-P01-001")])

    assert csc.main() == 0
    assert "特殊卡判定齊全（1 筆）" in capsys.readouterr().out


def test_main_returns_1_and_lists_pending_card(use_data, capsys):
    use_data([{"card_no": "HV-P01-001", "name": "テスト選手", "skill": "相手の手札を捨てる"}], [])

    assert csc.main() == 1
    out = capsys.readouterr().out
    assert "HV-P01-001" in out
    assert "相手の手札を捨てる" in out


def test_main_returns_1_on_malformed_entry(use_data):
    use_data([card("HV-P01-001", "相手の手札を捨てる")],
             [{"card_no": "HV-P01-001", "verdict": "maybe"}])

    assert csc.main() == 1


def test_main_returns_0_when_only_stale_entries(use_data, capsys):
    use_data([card("HV-P01-001", "相手の手札を捨てる")],
             [special("HV-P01-001"), excluded("HV-P09-999")])

    assert csc.main() == 0
    assert "HV-P09-999" in capsys.readouterr().out


def test_build_special_lookup_skips_malformed_entries_instead_of_crashing():
    # build_data.py 在載入時呼叫這個函式；判定表打錯字不能讓整條建置卡死
    lookup = csc.build_special_lookup([
        {"card_no": "HV-P01-001", "verdict": "special", "kind": "封鎖"},
        special("HV-P01-002", tier="全國"),
        special("HV-P01-003"),
    ])

    assert list(lookup) == ["HV-P01-003"]
