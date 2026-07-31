---
status: accepted
---

# `js/` 底下不碰 DOM 的純函式模組也用 `node:test`，透過 `js/package.json` 開一個獨立的 ESM 邊界

[ADR 0004](0004-node-test-runner-for-functions.md) 把「`functions/` 是唯一有自動化測試的地方」講得很死，`CODING_STANDARDS.md` 也明講 `index.html`/`game.html`/`js/*.js` 沒有模組系統可以讓 `node:test` 直接 import 被測函式。這份 ADR 記錄一個明確的例外：`js/school-popularity.js`、`js/card-name-suggest.js` 這類**刻意設計成不碰 DOM、不碰瀏覽器 API 的純函式模組**，補上跟 `functions/` 同款的 `node:test` 覆蓋。

這不是隨手繞過既有規範——issue #80（熱門學校標籤／卡名搜尋建議）的 spec 經過三輪 Claude↔GPT（A2A）壓力測試，其中第三輪明確聚焦「測試 seam 怎麼切」，結論是把這兩個功能拆成不碰 DOM 的純函式 module，並沿用 `functions/` 已經驗證過的 `node:test` 慣例（原話見 issue #80 內文「Further Notes」段落："第三輪聚焦測試 seam 切法（結論：拆成兩個獨立純函式 module、明確定義 pendingDelta/lastSyncedSnapshot 狀態分層、payload/snapshot 型別需與 cloud-sync.js 對齊）"）。

## Considered Options

- **維持現狀，`js/*.js` 完全不補自動化測試**：符合 `CODING_STANDARDS.md` 現有措辭，但會讓 `computeTopSchools`/`buildSuggestions`/`addView` 這幾個純邏輯函式（排序、去重、狀態轉換）完全沒有可重跑的驗證，只能每次改完手動開瀏覽器戳，跟 `functions/` 目前享有的保障不對等——而這兩個新模組跟 `cardLookup.js` 一樣是純函式，沒有理由被排除在外。
- **把這兩個模組直接搬進 `functions/` 底下測試**：`functions/` 在語意上是「Cloud Functions 原始碼」，硬塞前端會用到的純函式模組進去會混淆兩邊的部署邊界（`functions/` 會被 `firebase deploy --only functions` 整包上傳），不採用。
- **在 `js/` 底下新增一個只給模組型別宣告用的 `package.json`（現行做法）**：`{"type": "module", "private": true}`，讓 Node 的 ESM 判定在 `js/` 這層停下來，`node --test`（在 `js/` 目錄下執行）就能正常 `import`/`export` 被測檔案，不需要引入任何新的 npm 依賴或建置工具，也不影響 `js/*.js` 其餘沒有測試的傳統全域 `<script>` 檔案（它們照樣是傳統寫法，只是共用同一個 `type: module` 宣告不影響全域 `<script>` 引入方式）。

## Consequences

- `js/package.json` 只放模組型別宣告跟一個 `"test": "node --test"` script，不裝任何 npm 依賴，`js/` 底下不會出現 `node_modules/`。
- 之後只有「刻意設計成不碰 DOM 的純函式模組」才適用這個慣例（測試檔跟被測檔同資料夾、命名 `<原始檔名>.test.js`），例如 `school-popularity.js`／`card-name-suggest.js`。`index.html`/`game.html` 內嵌 `<script>` 或會直接操作 DOM 的 `js/*.js`（例如 `cloud-sync.js`、`deck-scan.js`）**不受這份 ADR 影響**，繼續維持手動瀏覽器測試，`CODING_STANDARDS.md` 原本那段話對它們依然成立。
- `functions/` 仍然是唯一會被 `npm install`/有 `node_modules`/有第三方依賴的 Node 專案；`js/package.json` 純粹是 ESM 邊界宣告，不構成第二個「npm 專案」意義上的例外。
