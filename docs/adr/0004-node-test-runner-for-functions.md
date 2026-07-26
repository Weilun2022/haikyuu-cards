---
status: accepted
---

# `functions/` 的測試框架用 Node 內建 `node:test`，不裝 Jest/Vitest

`functions/package.json` 的 `"test"` script是 `node --test`，測試檔案用 `node:test` + `node:assert/strict` 寫，沒有新增任何 npm 依賴。這是這個 repo 目前唯一有自動化測試的地方；`index.html`/`game.html` 等沒有模組系統的頁面暫不在範圍內（見 `CODING_STANDARDS.md` 測試現狀段落）。

## Considered Options

- **Jest**：生態最大、範例最多，但預設走 CJS，這個專案的 `functions/package.json` 是 `"type": "module"`（ESM），要嘛額外設定 transform、要嘛裝 `babel-jest` 之類的橋接套件，跟這個專案「盡量不引入不必要建置工具」的一貫立場不符。
- **Vitest**：ESM 原生、速度快，但終究是一個新的 npm 依賴（且通常會拉進一個不小的依賴樹），對目前只有 1 個函式庫檔案要測的規模來說不成比例。
- **Node 內建 `node:test`（現行）**：Node 18+ 就有，這個專案 `engines.node` 已經指定 `"20"`，不需要額外安裝任何東西；內建的 `mock` API（`mock.method`）已經足夠處理「把全域 `fetch` 換成假資料」這類需求，不用另外裝 mocking 套件。

## Consequences

之後 `functions/` 底下要加新測試，直接照現有慣例：測試檔案取名 `<原始檔名>.test.js`，跟被測的原始檔放同一個資料夾，`node --test` 會自動掃描到，不用改 `package.json` 或任何設定檔登記。如果之後測試規模變大到需要 `node:test` 沒有的功能（例如更複雜的 snapshot 比對、覆蓋率報表），才需要重新評估要不要換成 Vitest——不要因為「大家都用 Vitest」就無故升級，除非現有的 `node:test` 真的卡到具體需求。

這個決定只涵蓋 `functions/`。`index.html`/`game.html` 因為沒有模組系統，`node:test` 這套「直接 import 被測函式」的做法在那邊行不通，要不要幫這兩個檔案補測試是完全獨立的決定（可能需要瀏覽器層級的測試工具，例如 Playwright），不要把這份 ADR 當成「其他地方也該用 node:test」的理由。
