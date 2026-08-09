# 卡牌翻譯 Pipeline（build_data.py）

建置期工具：把官方日文卡片原始資料轉成網站實際載入的 `cards_zh.json`／`cards_data.js`。跟「卡片目錄／牌組管理」（使用者怎麼用網站）是不同性質的知識，只共用「產出結果會被那個 context 讀取」這一點，見根目錄 `CONTEXT-MAP.md`。這個 context 也涵蓋「官方資料下載」這個上游步驟（`haikyuu_downloader.py` 等）——它產出的 `all_cards.json`／`qa_data.json` 就是本 pipeline的原始輸入。

**要實際執行「更新官方最新資料」，照 [SOP.md](SOP.md) 的步驟操作**——這份文件是詞彙/概念表，不是操作手冊。

## Language

**`pipeline_paths.py`（位置知識單一來源，2026-08 架構檢視新增）**：
`haikyuu_output/all_cards.json`／`qa_data.json`／`qa_data_zh.json`／`images/`（pipeline 暫存）、根目錄 `images/`（網站實際讀圖）、`cards_data.js`／`cards_zh.json` 這些「檔案實際放在哪」的事實，全部只在 `pipeline_paths.py` 定義一次，`haikyuu_downloader.py`／`build_data.py`／`translate_qa.py`／`translate_qa_new.py`／`apply_qa_fixes.py`／`audit_manual_overrides.py`／`deck_optimizer/analyze.py` 一律從這裡 import，不再各自宣告字面路徑。緣起：2026-08 同一週內連續出現兩次事故（`build_data.py` 讀到舊路徑的 `all_cards.json`、新卡圖片沒同步到網站讀圖的 `images/`），根因都是同一個位置事實被複製到多個檔案、其中一份沒跟著改。
_Avoid_: 新增任何會讀寫這些檔案的腳本時，不要用 `os.path.join(...)` 或字面字串重新宣告一份路徑——一律 `from pipeline_paths import ...`。

**新卡／新QA偵測**：
判斷「官方是否有更新」的標準流程：先打 API 第一頁讀宣告總數（`data['count']`），跟本地 `all_cards.json` 的張數比較，有差才觸發 `fetch_all_cards()` 全量重抓，用卡片 variant 層級的穩定 `ID` 欄位 diff 新舊，找出真正新增/下架的卡。QA 資料的新增判斷同理，但**不能**用 QA API 回傳的 `id` 欄位（每次重抓會整批重新編號，不是穩定主鍵）——必須用 `(question, answer)` 內容比對，見 `docs/adr/0004`。
`haikyuu_downloader.py` 的 `check_for_new_cards()`/`should_refetch()` 把這個判斷寫成可呼叫、可測試的純函式（2026-08）；實際的 CLI 入口是 `check_new_cards.py`——呼叫 `check_for_new_cards()`，`has_new=True` 時先過兩道安全檢查（`is_fetch_complete()` 確認抓到的張數沒有少於官方宣告總數、`is_removal_suspicious()` 確認下架比例沒有異常，預設超過 30% 視為可疑），都過了才備份舊的 `all_cards.json`（`.bak`）再原子寫入新資料；任一檢查沒過就印錯誤、不寫檔、以非零 exit code 結束。不需要互動確認——`all_cards.json` 本來就是可以從官方 API 完全重建的可拋棄快取。
_Avoid_: 不要繞過 `check_new_cards.py` 直接手動呼叫 `check_for_new_cards()` 再自己寫檔——那樣會跳過完整性/下架比例這兩道安全檢查。

**通用規則（`translate_skill()`）**：
把日文技能文字（`skill_jp`）轉成中文（`skill_zh`）的正規表達式規則鏈，套用在**所有卡片**上。規則**依序執行**，寫在哪一段會決定能不能命中——例如某規則要用「の」還沒被轉成「的」之前的日文原形寫，寫在轉換點之後就永遠不會觸發。新增規則前一定要確認插入位置在正確的轉換段落之間。
_Avoid_: 不要跟「MANUAL_OVERRIDES」混用——這個是套用在全部卡片的共用規則，MANUAL_OVERRIDES 是單張卡的例外。

**MANUAL_OVERRIDES**：
用 `image_file`（例如 `HV-P03-011-I.webp`）當 key，對**單一張卡**的翻譯結果做完全覆蓋，繞過「通用規則」跟「ANNOTATION_ZH」。用在通用規則語序/邏輯改了就會波及其他未審查卡片的疑難case（例如「サイドブロッカーとして…に登場させる」這種通用規則會誤抓區域為角色類型的句型）。
_Avoid_: 修翻譯問題時優先找有沒有同類 MANUAL_OVERRIDES 可以比照套用，不要直接改「通用規則」的 regex——那會波及所有未重新審查過的卡片。

**ANNOTATION_ZH**：
翻譯「注釈」（技能補充說明文字，`annotation` 欄位）用的**完整字串精確比對**查表，不是 regex——因為這類文字常常整段逐字重複出現在很多張卡上（例如「支付Guts…將此角色下方的牌依指定張數放入棄牌區」）。查表沒命中時退回用 `translate_skill()` 的啟發式規則硬翻。
_Avoid_: 跟「通用規則」是兩套不同機制（精確比對 vs regex），不要以為兩者共用同一份規則。

**ユース／疑似ユース（保留政策）**：
P03 系列卡片裡的官方用語，刻意**保留日文原文不翻**（見 `docs/adr/0001`），不當成漏翻處理。假名殘留掃描要排除這兩個詞再檢查。

**QA 裁定翻譯**：
官方 QA 裁定文字（`qa_data.json`）走的是**完全獨立**的第二條管線：先用 Google Translate 整段機翻成 `qa_data_zh.json`，`clean_qa_text()` 再對機翻結果做後製修正（修正 Google 常見誤譯類別，例如 Guts/攔網 相關術語誤譯）。跟「通用規則」處理的輸入本質不同——通用規則吃的是原始日文，QA 裁定翻譯吃的是 Google 已經翻完的中文——所以兩條規則鏈**不應該合併**，見 `docs/adr/0003`。
_Avoid_: 不要跟「通用規則」搞混成同一套機制；也不要把 `translate_qa.py`/`translate_qa_new.py`（負責機翻+術語修正表）跟 `clean_qa_text()`（負責後製修正）當成同一層。

`qa_data_zh.json`（機翻＋人工審核修正過的結果）是這條 context 唯一進版控的資料檔（見 `docs/adr/0005`）——`all_cards.json`／`qa_data.json`／`cards_zh.json` 都是可以從官方 API 或既有規則鏈重新產生的可拋棄資料，唯獨 `qa_data_zh.json` 混有 `apply_qa_fixes.py` 套用過的人工修正，遺失就無法重建。改完一定要 `git add haikyuu_output/qa_data_zh.json`（見 `SOP.md` 第 8 步）。

`translate_qa.py` 的 `TERM_FIX` 表跟 `official_terms.json` 也刻意不合併：`TERM_FIX` 的 key 是「Google 常見的錯誤中文譯法」（例如「阻擋值」），value 是修正後的正確中文；`official_terms.json` 的 key 是「日文原詞」，value 才是正確中文。兩者比對方向不同（錯誤中文→正確中文 vs 日文→正確中文），沒辦法共用同一份表，2026-08 架構檢視時確認過這不是遺漏，是表本身形狀不同。

**譯名單一真相來源（`name_zh_data.py`）**：
卡片名稱翻譯的權威表（`NAME_ZH_ENTRIES`／`NAME_ZH_LOOKUP`），每筆有 `status`（`draft`/`confirmed`/`high` 等信心等級）。`通用規則` 裡如果要翻譯剛好也出現在卡名裡的日文字串（例如技能文字引用了某張卡的卡名），一律查這份表（`_apply_confirmed_name_zh()` 吃全文掃描＋`confirmed` gate；`_name_zh_value(jp, fallback)` 給還沒到 `confirmed` 門檻、但需要個別鎖定單一詞的呼叫點用），不要另外硬編一份翻譯。
2026-08 架構檢視時發現三筆歷史硬編翻譯（ヒナガラス／どんぴしゃり／今日 何をする？）跟這份表的確認版本已經 drift，原因是 `name_zh_data.py` 建表時（2026-07-07）比 `build_data.py` 那批硬編寫死的時間（2026-04-15）晚，同步從未補上；同一個月稍後又發現第 4～6 筆（灰羽リエーフ／超インナークロス／助けてもらう），其中「灰羽リエーフ」還同時在卡片名稱標籤、一般技能文字、`MANUAL_OVERRIDES` 三處各自顯示不同譯名。
**這批問題現在有自動化安全網**：`test_build_data.py` 的 `test_build_data_source_has_no_hardcoded_name_replacements` 靜態掃描 `build_data.py` 原始碼本身，找有沒有任何已登記在 `name_zh_data.py` 裡的日文詞被寫死翻譯、沒透過查表機制——`pytest`（SOP.md 步驟 7）跑的時候會自動執行，不用再等下一次人工全文審查才發現第 7 筆。這個測試刻意不掃 `MANUAL_OVERRIDES`（人工手寫、審查過的純文字，見 `docs/adr/0005` 同一套「不自動改寫人工內容」原則），所以 `MANUAL_OVERRIDES` 裡引用角色名字還是要人工確認跟 `name_zh_data.py` 一致。
_Avoid_: 修翻譯問題時，若字串同時是某卡卡名，先查 `name_zh_data.py` 有沒有 `confirmed`／個別鎖定版本，不要在 `通用規則`／`MANUAL_OVERRIDES` 裡重新翻一次。也不要因為新測試型態是「掃原始碼」就把一般函式測試也寫成斷言內部呼叫——這是刻意的單一例外，見 `CODING_STANDARDS.md`。

**假名殘留掃描**：
翻譯完成後的品質關卡——掃 `skill_zh`/`annotation_zh` 有沒有殘留日文假名/片假名，用來抓「規則沒命中、整段還是日文」的情況。**已知陷阱**：掃描時要排除引號「...」內引用其他卡片/技能日文原名的部分（那是刻意保留，不是漏翻，2026-07-25 在 `check_translations.js` 踩過這個坑），也要排除「ユース」類保留詞；且掃描範圍要涵蓋全庫，不能只挑特定系列（`\r\n` vs `\n` 換行差異曾經導致特定幾張卡的規則對不上而被漏掃，見 `docs/adr/0002`）。

## docs/adr/

- [0001](docs/adr/0001-yuusu-keep-untranslated.md) — ユース／疑似ユース 保留日文不翻的政策決定
- [0002](docs/adr/0002-crlf-normalization-in-pipeline.md) — pipeline 對 CRLF 換行做正規化，避免規則比對假陰性
- [0003](docs/adr/0003-qa-pipeline-google-translate-not-shared-engine.md) — QA 裁定翻譯改用 Google Translate + 術語修正表，不套用 translate_skill() 規則引擎
- [0004](docs/adr/0004-qa-diff-by-content-not-api-id.md) — QA 新增判斷用內容 diff，不用官方 API 的 id 欄位（會整批重新編號）
- [0005](docs/adr/0005-track-qa-data-zh-json-in-git.md) — qa_data_zh.json 進版控（含人工修正，不可重建），其餘三個資料檔維持 gitignore
