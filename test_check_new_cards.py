# -*- coding: utf-8 -*-
"""check_new_cards.py 的寫檔/中止決策整合測試。

不打真實網路——check_for_new_cards() 整個用 monkeypatch 換掉，只驗證 main() 收到
不同結果時該不該寫檔、備份、回傳什麼 exit code。純決策部分（is_fetch_complete/
is_removal_suspicious）已經在 test_haikyuu_downloader.py 裡窮舉測過，這裡不重複。
"""
import json

import check_new_cards as cnc


def test_format_id_list_empty():
    assert cnc._format_id_list([]) == "（無）"


def test_format_id_list_short():
    assert cnc._format_id_list(["a", "b", "c"]) == "a, b, c"


def test_format_id_list_truncates_long_lists():
    ids = [str(i) for i in range(50)]
    result = cnc._format_id_list(ids, limit=30)
    assert result.startswith("0, 1, 2")
    assert "共 50 筆" in result
    assert "29" in result  # 最後一個保留的 ID
    assert "30" not in result.split("...")[0]  # 第 31 個 (index 30) 不該出現在保留範圍內


def _fake_result(official_count, local_count, has_new, added_ids=None, removed_ids=None, fetched_cards=None):
    return {
        "official_count": official_count,
        "local_count": local_count,
        "has_new": has_new,
        "added_ids": added_ids or [],
        "removed_ids": removed_ids or [],
        "fetched_cards": fetched_cards,
    }


def test_no_new_cards_does_not_write(tmp_path, monkeypatch):
    json_path = tmp_path / "all_cards.json"
    json_path.write_text(json.dumps([{"ID": "a"}]), encoding="utf-8")
    monkeypatch.setattr(cnc, "JSON_PATH", json_path)
    monkeypatch.setattr(cnc, "check_for_new_cards", lambda: _fake_result(1, 1, False))

    exit_code = cnc.main()

    assert exit_code == 0
    assert json.loads(json_path.read_text(encoding="utf-8")) == [{"ID": "a"}]
    assert not json_path.with_suffix(".json.bak").exists()


def test_clean_update_writes_file_and_backup(tmp_path, monkeypatch):
    json_path = tmp_path / "all_cards.json"
    json_path.write_text(json.dumps([{"ID": "a"}]), encoding="utf-8")
    monkeypatch.setattr(cnc, "JSON_PATH", json_path)
    fetched = [{"ID": "a"}, {"ID": "b"}]
    monkeypatch.setattr(
        cnc, "check_for_new_cards",
        lambda: _fake_result(2, 1, True, added_ids=["b"], fetched_cards=fetched),
    )

    exit_code = cnc.main()

    assert exit_code == 0
    assert json.loads(json_path.read_text(encoding="utf-8")) == fetched
    backup_path = json_path.parent / (json_path.name + ".bak")
    assert backup_path.exists()
    assert json.loads(backup_path.read_text(encoding="utf-8")) == [{"ID": "a"}]


def test_incomplete_fetch_aborts_without_writing(tmp_path, monkeypatch):
    json_path = tmp_path / "all_cards.json"
    original = [{"ID": "a"}, {"ID": "b"}]
    json_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(cnc, "JSON_PATH", json_path)
    # 官方宣告 521，但只抓到 3 筆——明顯是抓取中途失敗
    monkeypatch.setattr(
        cnc, "check_for_new_cards",
        lambda: _fake_result(521, 2, True, fetched_cards=[{"ID": "x"}, {"ID": "y"}, {"ID": "z"}]),
    )

    exit_code = cnc.main()

    assert exit_code == 1
    assert json.loads(json_path.read_text(encoding="utf-8")) == original
    assert not (json_path.parent / (json_path.name + ".bak")).exists()


def test_suspicious_removal_ratio_aborts_without_writing(tmp_path, monkeypatch):
    json_path = tmp_path / "all_cards.json"
    original = [{"ID": str(i)} for i in range(500)]
    json_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(cnc, "JSON_PATH", json_path)
    # 500 筆裡「下架」了 200 筆（40%），超過預設 30% 門檻
    monkeypatch.setattr(
        cnc, "check_for_new_cards",
        lambda: _fake_result(
            500, 500, True,
            removed_ids=[str(i) for i in range(200)],
            fetched_cards=[{"ID": str(i)} for i in range(200, 500)],
        ),
    )

    exit_code = cnc.main()

    assert exit_code == 1
    assert json.loads(json_path.read_text(encoding="utf-8")) == original


def test_fresh_checkout_no_existing_file_writes_full_dataset(tmp_path, monkeypatch):
    json_path = tmp_path / "all_cards.json"
    monkeypatch.setattr(cnc, "JSON_PATH", json_path)
    fetched = [{"ID": "a"}, {"ID": "b"}, {"ID": "c"}]
    monkeypatch.setattr(
        cnc, "check_for_new_cards",
        lambda: _fake_result(3, 0, True, added_ids=["a", "b", "c"], fetched_cards=fetched),
    )

    exit_code = cnc.main()

    assert exit_code == 0
    assert json.loads(json_path.read_text(encoding="utf-8")) == fetched
    assert not (json_path.parent / (json_path.name + ".bak")).exists()
