# -*- coding: utf-8 -*-
"""haikyuu_downloader.py 純決策邏輯的回歸測試。

不打真實網路、不寫真實檔案——只測 should_refetch()/check_for_new_cards() 的決策部分，
HTTP 呼叫一律用假物件取代。
"""
import json
from pathlib import Path
from unittest import mock

import pytest

import haikyuu_downloader as hd


# ── should_refetch: 窮舉三種情境 ──────────────────────────────────
def test_should_refetch_equal_counts():
    assert hd.should_refetch(official_count=500, local_count=500) is False


def test_should_refetch_official_has_more():
    assert hd.should_refetch(official_count=521, local_count=518) is True


def test_should_refetch_official_has_fewer():
    # 官方數字比本地少（異常縮減，例如卡片下架）也要觸發重新檢查
    assert hd.should_refetch(official_count=515, local_count=518) is True


# ── is_fetch_complete: check_new_cards.py 寫檔前的完整性檢查 ──────────
def test_is_fetch_complete_exact_match():
    assert hd.is_fetch_complete(fetched_count=521, official_count=521) is True


def test_is_fetch_complete_more_than_official():
    # 抓到的比宣告數字多也算完整（不該發生，但不該因此擋下寫檔）
    assert hd.is_fetch_complete(fetched_count=522, official_count=521) is True


def test_is_fetch_complete_short_by_one():
    assert hd.is_fetch_complete(fetched_count=520, official_count=521) is False


def test_is_fetch_complete_severely_incomplete():
    assert hd.is_fetch_complete(fetched_count=3, official_count=521) is False


# ── is_removal_suspicious: 下架比例過高時要擋下寫檔 ──────────────────
def test_is_removal_suspicious_zero_local_count_never_suspicious():
    assert hd.is_removal_suspicious(removed_count=0, local_count=0) is False


def test_is_removal_suspicious_below_threshold():
    assert hd.is_removal_suspicious(removed_count=100, local_count=500, threshold=0.3) is False


def test_is_removal_suspicious_exactly_at_threshold_not_suspicious():
    # 剛好等於門檻不算「超過」，維持嚴格大於的語意
    assert hd.is_removal_suspicious(removed_count=150, local_count=500, threshold=0.3) is False


def test_is_removal_suspicious_above_threshold():
    assert hd.is_removal_suspicious(removed_count=200, local_count=500, threshold=0.3) is True


def test_is_removal_suspicious_uses_default_threshold():
    assert hd.is_removal_suspicious(removed_count=200, local_count=500) is True
    assert hd.is_removal_suspicious(removed_count=100, local_count=500) is False


# ── check_for_new_cards: 只測決策，API 呼叫與檔案 I/O 全部 stub ──────
def _fake_response(count):
    resp = mock.Mock()
    resp.raise_for_status = mock.Mock()
    resp.json.return_value = {"count": count}
    return resp


def test_check_for_new_cards_no_local_file_triggers_full_refetch(tmp_path, monkeypatch):
    monkeypatch.setattr(hd, "JSON_PATH", tmp_path / "all_cards.json")
    monkeypatch.setattr(hd, "requests", mock.Mock(get=mock.Mock(return_value=_fake_response(3))))
    monkeypatch.setattr(hd, "fetch_all_cards", lambda: [
        {"ID": "a"}, {"ID": "b"}, {"ID": "c"},
    ])

    result = hd.check_for_new_cards()

    assert result["official_count"] == 3
    assert result["local_count"] == 0
    assert result["has_new"] is True
    assert result["added_ids"] == ["a", "b", "c"]
    assert result["removed_ids"] == []


def test_check_for_new_cards_matching_counts_skips_full_refetch(tmp_path, monkeypatch):
    json_path = tmp_path / "all_cards.json"
    json_path.write_text(json.dumps([{"ID": "a"}, {"ID": "b"}]), encoding="utf-8")
    monkeypatch.setattr(hd, "JSON_PATH", json_path)
    monkeypatch.setattr(hd, "requests", mock.Mock(get=mock.Mock(return_value=_fake_response(2))))
    fetch_all_cards_mock = mock.Mock()
    monkeypatch.setattr(hd, "fetch_all_cards", fetch_all_cards_mock)

    result = hd.check_for_new_cards()

    assert result["has_new"] is False
    assert result["fetched_cards"] is None
    fetch_all_cards_mock.assert_not_called()  # 數字一致就不該觸發昂貴的全量重抓


def test_check_for_new_cards_reports_added_and_removed_ids(tmp_path, monkeypatch):
    json_path = tmp_path / "all_cards.json"
    json_path.write_text(json.dumps([{"ID": "a"}, {"ID": "b"}]), encoding="utf-8")
    monkeypatch.setattr(hd, "JSON_PATH", json_path)
    # 官方宣告數字比本地多，has_new=True 分支：驗證 diff 邏輯本身（b 下架，c/d 新增）
    monkeypatch.setattr(hd, "requests", mock.Mock(get=mock.Mock(return_value=_fake_response(3))))
    monkeypatch.setattr(hd, "fetch_all_cards", lambda: [{"ID": "a"}, {"ID": "c"}, {"ID": "d"}])

    result = hd.check_for_new_cards()

    assert result["has_new"] is True
    assert result["added_ids"] == ["c", "d"]
    assert result["removed_ids"] == ["b"]


# ── fetch_qa_data(only_missing=...): 只測「該抓哪些 card_no」，HTTP 全部 stub ──
def test_fetch_qa_data_only_missing_restricts_card_nos(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["cn"])
        return _fake_response_with_qa(count=0)

    monkeypatch.setattr(hd, "requests", mock.Mock(get=fake_get))
    monkeypatch.setattr(hd.time, "sleep", lambda *_a, **_k: None)

    cards = [{"card_no": "HV-P01-001"}, {"card_no": "HV-P01-002"}, {"card_no": "HV-P03-001"}]
    result = hd.fetch_qa_data(cards, only_missing=["HV-P03-001"])

    assert calls == ["HV-P03-001"]
    assert set(result.keys()) == {"HV-P03-001"}


def test_fetch_qa_data_without_only_missing_uses_all_cards(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["cn"])
        return _fake_response_with_qa(count=0)

    monkeypatch.setattr(hd, "requests", mock.Mock(get=fake_get))
    monkeypatch.setattr(hd.time, "sleep", lambda *_a, **_k: None)

    cards = [{"card_no": "HV-P01-002"}, {"card_no": "HV-P01-001"}]
    result = hd.fetch_qa_data(cards)

    assert calls == ["HV-P01-001", "HV-P01-002"]  # 沿用舊行為：排序後的全部 card_no
    assert set(result.keys()) == {"HV-P01-001", "HV-P01-002"}


def _fake_response_with_qa(count):
    resp = mock.Mock()
    resp.raise_for_status = mock.Mock()
    resp.json.return_value = {"count": count, "items": {}}
    return resp


# ── haikyuu_downloader.py 的 interactive 分支：不觸發真實 input()/網路 ──────
def test_main_non_interactive_fetches_when_json_missing(tmp_path, monkeypatch):
    json_path = tmp_path / "all_cards.json"
    qa_path = tmp_path / "qa_data.json"
    monkeypatch.setattr(hd, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(hd, "JSON_PATH", json_path)
    monkeypatch.setattr(hd, "QA_PATH", qa_path)
    monkeypatch.setattr(hd, "IMG_DIR", tmp_path / "images")
    monkeypatch.setattr(hd, "fetch_all_cards", lambda: [{"ID": "a", "card_no": "HV-P01-001"}])
    monkeypatch.setattr(hd, "fetch_qa_data", lambda cards, only_missing=None: {})
    monkeypatch.setattr(hd, "download_images", lambda cards: {})
    monkeypatch.setattr(hd, "build_excel", lambda cards, id_to_path: None)

    def fail_on_input(*_a, **_k):
        raise AssertionError("interactive=False 不應該呼叫 input()")

    monkeypatch.setattr("builtins.input", fail_on_input)

    hd.main(interactive=False)  # 這是修掉的 bug：舊版 run_download.py 在這個情境下會直接 crash

    assert json_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8")) == [{"ID": "a", "card_no": "HV-P01-001"}]
