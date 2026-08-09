# SOP：更新官方最新資料

給人／未來的 Claude Code session 照著跑的操作手冊。跟 `CONTEXT.md`（詞彙/概念）不同，這份純粹是「照順序執行什麼指令」。

## 什麼時候要跑這套流程

官方出新彈（新卡）或新增 Q&A 裁定時。平常不需要排程執行——目前整條 pipeline 是手動觸發，見 `docs/translation/CONTEXT.md`「新卡／新QA偵測」。

## 前置條件

```bash
pip install -r requirements.txt
```

（第一次在這台機器上跑才需要；已經裝過 `pytest` 可以跳過。）

## 步驟

### 1. 偵測官方是否有新卡，並更新 `all_cards.json`

```bash
python check_new_cards.py
```

- 打官方 API 第一頁比對宣告總數 vs 本地張數；沒差異就印「沒有新資料」結束（exit 0），不動任何檔案。
- 有差異才觸發全量重抓，並印出新增/下架的卡片 ID。
- 兩道安全檢查都過了才會覆寫 `haikyuu_output/all_cards.json`（覆寫前自動備份成 `.bak`）：
  - 抓到的張數不能少於官方宣告總數（否則判斷是抓取中途失敗，直接中止不寫檔）
  - 下架比例不能超過 30%（否則判斷是官方 API 暫時異常，直接中止不寫檔）
- 中止時 exit code 是 1，可以看 print 出來的 `[ERROR]` 訊息判斷原因。

### 2. 補新卡的圖片／Excel

```bash
python run_download.py
```

- 讀步驟 1 產生的 `all_cards.json`，只下載本機還沒有的圖片（已存在的自動跳過），重新產生 Excel。
- 這一步不會重抓 `all_cards.json` 本身——那是步驟 1 的責任。
- 圖片會先存進 `haikyuu_output/images/`，接著自動同步複製到根目錄 `images/`（`sync_images_to_site()`，2026-08 新增）——網站（`index.html`/`game.html` 等）實際讀圖是走根目錄 `images/` 相對路徑，不是 `haikyuu_output/images/`，這一步沒做的話新卡在網站上會顯示不出來。

### 3. 補新卡的 Q&A 原文

```bash
python fetch_new_qa.py
```

- 自動比對 `all_cards.json` 有、`qa_data.json` 還沒有的 card_no，只抓這些，不動已經抓過的。

### 4. 翻譯新增的 Q&A（增量，不影響已翻譯過的卡）

```bash
python translate_qa_new.py
```

- 自動算出「`qa_data.json` 有非空 QA、但 `qa_data_zh.json` 還沒有」的 card_no 清單，逐筆用 Google Translate 翻譯＋套用 `TERM_FIX` 術語修正表。
- 已經在 `qa_data_zh.json` 裡的卡（含手動修正過的）一律跳過，不會被覆蓋。
- 這支腳本會實際呼叫 Google Translate（`deep_translator`），每筆問答間有延遲，卡數多的話會跑比較久（見 `translate_qa.py` 檔頭註解實測數據）。

### 5.（有新回報的翻譯錯誤才需要）套用已知修正

```bash
python apply_qa_fixes.py
```

- 只有 `apply_qa_fixes.py` 裡的 `FIXES` 表有新條目（例如收到新的 GitHub issue 回報翻譯錯誤）才需要跑這步——例行更新官方資料不一定要執行。
- 用內容比對定位要修正的 QA 條目，已經套用過的會自動跳過（no-op），找不到匹配或匹配到多筆會直接報錯中止，不會誤改。

### 6. 建置網站實際載入的資料

```bash
python build_data.py
```

- 讀 `all_cards.json`＋`qa_data_zh.json`＋`name_zh_data.py`＋`official_terms.json`，套用 `translate_skill()`／`clean_qa_text()` 規則鏈，輸出 `cards_data.js`／`cards_zh.json`。
- 這是網站實際會載入的檔案，`cards_data.js` 有進版控，`cards_zh.json` 沒有（見根目錄 `.gitignore`）。

### 7. 品質檢查

```bash
node check_translations.js
pytest
```

- `check_translations.js`：假名/片假名殘留掃描 + 官方術語一致性檢查（含 QA 文字），抓「規則沒命中、整段還是日文」或用詞跟站內慣例不符的漏翻；現在抓到問題會直接 exit 1，不是只印出來。
- `pytest`：跑現有的回歸測試套件（`translate_skill()`/`clean_qa_text()` 規則鏈、新卡/新QA偵測決策、QA 修正比對邏輯），確認這次資料更新沒有連帶跑出程式邏輯層級的問題。**也包含一個靜態掃描 `build_data.py` 原始碼本身的安全網測試**（`test_build_data_source_has_no_hardcoded_name_replacements`）：找有沒有任何已登記在 `name_zh_data.py` 裡的角色/台詞譯名被寫死翻譯、繞過查表機制——這是 2026-08 修「灰羽リエーフ」等 3 筆歷史譯名分歧時新增的，往後同款問題會在這裡自動被抓到，見 `docs/translation/CONTEXT.md`「譯名單一真相來源」。

### 8. Commit + push

`cards_data.js`、`haikyuu_output/qa_data_zh.json`、以及根目錄 `images/` 底下新增的卡圖都要進版控（`all_cards.json`/`qa_data.json`/`cards_zh.json`/`haikyuu_output/images/` 是可以從官方 API 重建的可拋棄資料，維持 gitignore 不動；`qa_data_zh.json` 混有人工審核修正、無法重建，見 `docs/adr/0005`；根目錄 `images/` 是網站實際讀圖的位置，步驟 2 的 `sync_images_to_site()` 已經把新卡圖同步過去，這裡只是要把新增的檔案 `git add` 進去）。

```bash
git add cards_data.js haikyuu_output/qa_data_zh.json images/
git commit -m "chore(cards): 更新官方新卡資料（含 P0X 系列）"
git push
```

第一次把 `qa_data_zh.json` 加進版控時要用 `git add -f haikyuu_output/qa_data_zh.json`（`.gitignore` 對 `*.json` 是 blanket 排除）；加過一次之後 git 就會正常追蹤，之後不用再加 `-f`。

## 遇到問題時

- `check_new_cards.py` 印 `[ERROR]` 中止：看訊息判斷是「抓取不完整」還是「下架比例異常」，重跑一次通常就好（暫時性 API 問題）；如果重跑還是一樣，才需要人工檢查官方頁面是不是真的改版了。
- `translate_qa_new.py` 翻譯結果出現「翻譯失敗」字樣：Google Translate 那次呼叫失敗，腳本會繼續跑完其他卡，跑完後手動針對失敗的卡再跑一次，或直接編輯 `qa_data_zh.json` 對應欄位。
- 翻譯用詞系統性錯誤（同一種誤譯出現在很多張卡）：改 `translate_qa.py` 的 `TERM_FIX` 表，不要一張一張手改 `qa_data_zh.json`；個別卡的裁定文字邏輯性翻錯才用 `apply_qa_fixes.py`。
- `pytest` 在 `test_build_data_source_has_no_hardcoded_name_replacements` 失敗：代表 `build_data.py` 裡有某個已登記在 `name_zh_data.py` 的角色/台詞名字被寫死翻譯、沒透過查表機制——錯誤訊息會指出是哪一行、對應哪個日文詞，改成呼叫 `_apply_confirmed_name_zh()`（全文掃描，需要 `status: confirmed`）或 `_name_zh_value(jp, fallback)`（個別鎖定，不看 status），不要留著寫死字面量。`MANUAL_OVERRIDES` 裡的個別條目不在這個測試掃描範圍內，要另外人工核對是否跟 `name_zh_data.py` 一致。
- 更多細節（規則鏈怎麼運作、各種例外情況）見 `docs/translation/CONTEXT.md`。
