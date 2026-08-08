# -*- coding: utf-8 -*-
"""pipeline_paths.py 是下載/翻譯 pipeline 的單一位置知識來源，回歸測試只需要
確認它本身沒有意外壞掉（例如 ROOT 解析錯誤、常數被誤刪）——不需要測試「跟
build_data.py/haikyuu_downloader.py 是否一致」，因為那些模組現在都直接 import
這裡的常數，結構上不可能再分岔（2026-08 架構檢視要解決的正是這個問題）。
"""
from pathlib import Path

import pipeline_paths as pp


def test_root_is_repo_root():
    assert pp.ROOT == Path(__file__).resolve().parent


def test_all_paths_resolve_under_root():
    for name in (
        "ALL_CARDS_JSON", "QA_JSON", "QA_ZH_JSON", "IMG_DIR", "EXCEL_PATH",
        "SITE_IMG_DIR", "CARDS_DATA_JS", "CARDS_ZH_JSON",
    ):
        path = getattr(pp, name)
        assert pp.ROOT in path.parents, f"{name} 沒有錨定在 ROOT 底下：{path}"


def test_pipeline_output_dir_vs_site_dir_are_distinct():
    # 這正是這次要修的兩個事故的核心事實：pipeline 暫存區跟網站實際讀取的位置
    # 是兩個不同目錄，不能混用。
    assert pp.IMG_DIR != pp.SITE_IMG_DIR
    assert pp.OUTPUT_DIR not in pp.SITE_IMG_DIR.parents
