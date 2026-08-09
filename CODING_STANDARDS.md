# Coding Standards

給 `code-review` skill 的 Standards 軸讀的（也適用於任何人/agent 寫這個 repo 的程式碼）。這裡只記錄**這個 repo 實際在遵守**的規範，不是理想化的通用最佳實踐。

## 技術棧

- 純前端靜態站（GitHub Pages），無建置流程、無框架。JS 直接寫在 `index.html`／`promo.html`／`game.html` 等頁面的 `<script>` 裡，或 `js/*.js`。
- 只有需要 Firebase SDK（雲端同步、Cloud Function 呼叫）的檔案、或刻意設計成不碰 DOM 的純函式模組（供 `node:test` 覆蓋，見下方測試現狀）用 ES module（`<script type="module">`），其餘一律是傳統全域 `<script>`，函式/變數直接掛在頁面的全域作用域。
- `functions/` 是唯一有第三方 npm 依賴的 Node 專案（Firebase Cloud Functions v2）。`js/package.json` 是例外但範圍很窄——只宣告 `js/` 底下的 ESM 模組邊界給 `node:test` 用，不裝任何依賴（理由見 [docs/adr/0005](docs/adr/0005-node-test-for-js-pure-modules.md)）。除此之外不要在根目錄或其他地方加 `package.json`/建置工具。
- Python 腳本（`build_data.py`、`scan_deck_photo.py` 等）是離線資料處理/開發用工具，不隨網站部署，不用套用前端規範。`.gitignore` 對 `*.py` 是 blanket 排除，但 2026-08 架構檢視後大部分下載/翻譯腳本已經個別 `git add -f` 進版控（`build_data.py`／`haikyuu_downloader.py`／`run_download.py`／`fetch_new_qa.py`／`apply_qa_fixes.py`／`translate_qa.py`／`translate_qa_new.py`／`audit_manual_overrides.py`／`build_card_feature_index.py`）——規則本身沒改，是逐一加回追蹤，之後新增的 Python 工具腳本預設也應該個別追蹤，不要假設「反正 *.py 都被排除」。

## 命名/組織

- 跟雲端同步相關的全域函式一律 `hv` 前綴（`hvOnLocalChange`、`hvRunAutoSync`）跟其他函式命名空間分開，避免全域作用域撞名。
- localStorage 存取集中成 `save*`/`load*` 配對函式，不要在各處散落 `localStorage.getItem` 裸呼叫。
- 使用者可見的提示一律走 `showToast(msg)`，不要另開新的提示 UI 模式。

## 註解

- 預設不寫註解。只有在「為什麼」不明顯時才寫——隱藏的限制條件、繞過某個特定 bug 的 workaround、會讓人意外的行為。不要寫「這段在做什麼」（好的命名就該講清楚），不要寫「這是為了修 X 問題/服務 Y 功能」這種會過時、跟目前程式碼脫鉤的參考。
- 這個 repo 的既有註解常常記錄「為什麼選這個做法、之前試過什麼失敗了」（例如 `cloud-sync.js` 開頭那段設計原則），這是刻意的、值得繼續延續的風格——省下未來重新踩同一個坑的時間。

## CSS

- 色票走 `css/theme.css` 的 CSS 自訂屬性（`--bg`/`--surface`/`--accent`/`--text` 等），不要在個別頁面硬編色碼。共用元件樣式放 `css/components.css`。
- 學校色票（`--s-*`）、稀有度色票（`--r-*`）刻意不放共用檔——不同頁面綁定不同資料源，鍵名本來就不一致，見 `tasks/log.md` 顏色架構設計參考段落。

## Commit 訊息

`type(scope): 中文說明`，type 用 `feat`/`fix`/`chore`/`refactor`/`style`/`redesign` 這幾種，scope 是受影響的功能區塊（例如 `cloud-sync`、`deck-export`、`theme`）。範例：`fix(cloud-sync): 修正換裝置首次同步時空白本機覆蓋雲端顏色資料`。

## 測試現狀（老實說）

**`functions/` 跟 `js/` 底下刻意不碰 DOM 的純函式模組有自動化測試，其餘（`index.html`／`game.html`／`js/*.js` 裡會碰 DOM 的檔案）沒有。** 這是刻意的分界，不是還沒做完：

- **`functions/`**：唯一有第三方 npm 依賴的 Node 專案，也是最早採用這套慣例的地方，用 Node 內建的 `node:test` + `node:assert/strict`，**沒有裝任何新的測試框架依賴**（不是 Jest/Vitest，是刻意選擇，理由見 [docs/adr/0004](docs/adr/0004-node-test-runner-for-functions.md)）。
  - 執行：`cd functions && npm test`（`node --test` 會自動掃描並執行所有符合 `**/*.test.js` 的檔案，不用逐一註冊）。
  - **加新測試就直接照這個慣例放檔案**：測試檔跟被測的原始檔放同一個資料夾、檔名是 `<被測檔案>.test.js`（例如 `lib/cardLookup.test.js` 測 `lib/cardLookup.js`），寫完直接跑得到，不用改任何設定。
  - **只測公開匯出的函式（`export function ...`），不測內部細節**——斷言回傳值，不去檢查內部快取變數/私有函式有沒有被呼叫。
  - **會碰網路的函式**（例如 `cardLookup.js` 的 `loadCards()` 會 `fetch` 一個外部網址）：用 `node:test` 內建的 `mock.method(globalThis, 'fetch', ...)` 把全域 `fetch` 換成回傳假資料的版本，測試不能依賴真實網路——外部網站變慢或掛掉不該讓測試跟著變紅。參考 `functions/lib/cardLookup.test.js` 的寫法。
  - 現有測試：`functions/lib/cardLookup.test.js`（日文卡名模糊比對）。

- **`js/` 底下刻意設計成不碰 DOM／瀏覽器 API 的純函式模組**（例如 `school-popularity.js`／`card-name-suggest.js`）：跟 `functions/` 一樣用 `node:test`，測試檔同資料夾、命名 `<被測檔案>.test.js`。`js/package.json`（`{"type": "module"}`）只是讓 Node 的 ESM 判定在這層停下來，本身不裝任何 npm 依賴，`js/` 底下不會有 `node_modules/`。理由跟例外範圍見 [docs/adr/0005](docs/adr/0005-node-test-for-js-pure-modules.md)——只有「刻意不碰 DOM」的模組適用，`cloud-sync.js`／`deck-scan.js` 這類會碰 DOM/瀏覽器 API 的 `js/*.js` 不受影響，繼續維持下面這條的手動測試慣例。
  - 執行：`cd js && npm test`。
  - 現有測試：`js/school-popularity.test.js`（`computeTopSchools` 熱門學校排行）。

- **`index.html`／`game.html`／`js/*.js` 裡會碰 DOM 的檔案**：沒有模組系統（`export`/`import`），函式直接掛在頁面全域作用域，市面上標準測試框架抓不到單一函式來測。要幫這幾個檔案補測試，需要先決定要不要導入瀏覽器層級的測試工具（例如 Playwright，真的開瀏覽器跑腳本），這是一個比較大、還沒做的獨立決定，不要自己假設可以套用 `functions/`／`js/` 純函式模組那套 `node:test` 的做法。目前驗證方式維持手動：改完用瀏覽器實測（`console` 手動呼叫、注入 mock 盤面/mock 牌組資料、DOM 幾何量測），這個習慣不算「沒有測試」，只是沒有存成可重跑的腳本。

採用 `tdd` skill 在 `index.html`/`game.html` 這類還沒有自動化測試的模組上是**引入新習慣**，不是「補回原本就有的測試」。第一次在這類模組用 TDD 之前，照 `tdd` skill 的規則跟使用者確認 seam 在哪，不要假設既有的手動驗證方式可以直接套用同一套 seam。`functions/` 底下則已經有真正的 seam 慣例可以直接沿用，不用重新確認。

- **根目錄的 Python 下載/翻譯 pipeline（2026-08 起）**：用 `pytest`（`requirements.txt` 記錄依賴），不是 stdlib `unittest`——這是這條 pipeline 第一次有自動化測試時的明確選擇，理由是 fixture/parametrize 對這批規則鏈類的回歸測試比較好寫，跟 `functions/`/`js/` 選 `node:test`（避免新依賴）是不同情境下的不同判斷，不要互相套用對方的理由。
  - 執行：`pip install -r requirements.txt` 後 `pytest`（或 `pytest test_build_data.py` 等單檔執行）。
  - 測試檔命名 `test_<被測檔案>.py`，放在根目錄（跟被測檔同層），只測外部行為（輸入→輸出），不斷言內部呼叫了哪個 helper。
  - 會打真實網路/寫真實檔案的函式（`haikyuu_downloader.py` 的 `fetch_qa_data`/`check_for_new_cards` 等）一律用 `unittest.mock`／`monkeypatch` 把 `requests`/檔案路徑換掉，測試不能依賴真實網路或本機的 `haikyuu_output/` 資料。
  - 現有測試：`test_build_data.py`（翻譯規則鏈回歸）、`test_haikyuu_downloader.py`（新卡偵測/下載決策邏輯，含 `sync_images_to_site()`）、`test_apply_qa_fixes.py`（QA 修正內容比對邏輯）、`test_check_new_cards.py`（`check_new_cards.py` 的寫檔/中止決策）、`test_pipeline_paths.py`（pipeline 位置常數的形狀檢查）、`test_translate_qa.py`（QA 術語覆寫表 `apply_term_fix()`／撞名術語佔位符機制，含冪等性回歸測試）。
