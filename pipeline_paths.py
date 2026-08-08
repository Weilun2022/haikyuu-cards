# -*- coding: utf-8 -*-
"""單一位置知識來源：官方卡片下載／QA 翻譯 pipeline 每個檔案實際放在哪。

所有下載/翻譯/建置/稽核腳本都應該從這裡 import 路徑常數，不要各自宣告字面路徑
——2026-08 兩次官方更新事故（卡片資料/圖片沒同步到網站實際讀取的位置）都是因為
同一個位置事實被複製到多個檔案，其中一份沒跟著改。見 docs/translation/CONTEXT.md。

所有路徑都錨定在這個檔案自己的位置（ROOT），不依賴呼叫者的工作目錄。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ── 下載/翻譯 pipeline 的暫存輸出（可從官方 API 或既有規則鏈重建，
#    qa_data_zh.json 除外——混有人工審核修正，見 docs/adr/0005） ──
OUTPUT_DIR      = ROOT / "haikyuu_output"
ALL_CARDS_JSON  = OUTPUT_DIR / "all_cards.json"
QA_JSON         = OUTPUT_DIR / "qa_data.json"
QA_ZH_JSON      = OUTPUT_DIR / "qa_data_zh.json"
IMG_DIR         = OUTPUT_DIR / "images"
EXCEL_PATH      = OUTPUT_DIR / "haikyuu_cards_with_images.xlsx"

# ── 網站實際載入/讀取的位置 ──────────────────────────────────────────
SITE_IMG_DIR    = ROOT / "images"
CARDS_DATA_JS   = ROOT / "cards_data.js"
CARDS_ZH_JSON   = ROOT / "cards_zh.json"
