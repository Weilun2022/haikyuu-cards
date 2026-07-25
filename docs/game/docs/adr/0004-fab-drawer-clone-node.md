---
status: accepted
---

# 手機版側邊欄用 `cloneNode` 複製，不是重寫一份手機專用 UI

手機版的 FAB 抽屜（`#mobile-drawer-content`）用 `buildDrawerContent()` 對桌面版 `#sidebar` 做 `cloneNode(true)`，複製進抽屜裡，並移除複製體所有子元素的 `id`（避免 `getElementById` 抓到 clone 而非原版）。

## Considered Options

- **重寫一份手機專用側邊欄 markup**：內容要跟桌面版同步維護兩份，容易分岔。
- **`cloneNode` 複製現有 `#sidebar`（現行）**：`#mobile-drawer-content` 在 DOM 中比 `#sidebar` 更早出現，只有一份內容來源，桌面版改什麼手機版自動跟著變，但複製體的 `id` 全部要清掉、原本用 `id` 存取子元素的邏輯（例如 log 區）要改用 `class` 選擇器同時對應兩份。

## Consequences

`log-wrap` 這類原本用 `id` 存取的元素，改成 `.log-wrap` class + `#log-wrap, .log-wrap { … }` 雙選擇器 CSS，`renderLog()` 結尾要同時更新 `document.querySelector('.log-wrap')` 讓抽屜裡的 clone 同步。之後側邊欄新增任何用 `getElementById` 存取的子元素，都要考慮這個 clone 機制——沒有處理 id 衝突/沒有改用 class 選擇器的話，`getElementById` 會抓到抽屜裡的複製體而不是桌面版原版（因為複製體在 DOM 中排更前面）。
