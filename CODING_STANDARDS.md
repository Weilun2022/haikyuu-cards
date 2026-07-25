# Coding Standards

給 `code-review` skill 的 Standards 軸讀的（也適用於任何人/agent 寫這個 repo 的程式碼）。這裡只記錄**這個 repo 實際在遵守**的規範，不是理想化的通用最佳實踐。

## 技術棧

- 純前端靜態站（GitHub Pages），無建置流程、無框架。JS 直接寫在 `index.html`／`promo.html`／`game.html` 等頁面的 `<script>` 裡，或 `js/*.js`。
- 只有需要 Firebase SDK（雲端同步、Cloud Function 呼叫）的檔案用 ES module（`<script type="module">`），其餘一律是傳統全域 `<script>`，函式/變數直接掛在頁面的全域作用域。
- `functions/` 是唯一的 Node/npm 專案（Firebase Cloud Functions v2），其餘都不是 npm 專案，不要在根目錄加 `package.json`/建置工具。
- Python 腳本（`build_data.py`、`scan_deck_photo.py` 等）是離線資料處理/開發用工具，不隨網站部署（`.gitignore` 排除全部 `*.py`），不用套用前端規範。

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

**目前沒有任何自動化測試框架或測試檔案。** 沒有 `package.json` 的 `test` script，沒有 Jest/Vitest/Playwright 之類的東西。驗證方式一直是手動：改完用瀏覽器實測（截圖、`console` 手動呼叫、DOM 幾何量測），或是像 `scan_deck_photo.py` 那樣寫一次性 Python 腳本驗證演算法。

採用 `tdd` skill 是**引入新習慣**，不是「補回原本就有的測試」。第一次在某個模組用 TDD 之前，照 `tdd` skill 的規則跟使用者確認 seam 在哪，不要假設既有的手動驗證方式可以直接套用同一套 seam。
