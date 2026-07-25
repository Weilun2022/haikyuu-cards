---
status: accepted
---

# 遊戲狀態變數用 module-scope，不掛在 `window` 上

`dragData`、`moveMode`、`movePendingZone`、`L`（本地玩家狀態）都是 `<script>` 內的一般變數（`let`/`const`），不是 `window.dragData` 這種全域屬性寫法。

## Considered Options

- **掛在 `window`**：多方協作（不同 agent/worktree 各自改 game.html 不同段落）時很容易寫成 `window.dragData = …`，圖方便讓不同段落程式碼能互相存取。
- **module-scope 一般變數（現行）**：`L` 是 `const`，只能 mutate 屬性（`L.hand = […]`）不能整個重新賦值；其餘用 `let`，靠 `<script>` 的閉包作用域共享，不暴露到全域 `window`。

## Consequences

多方協作／四方 agent 整合程式碼時，容易誤用 `window.dragData = …` 這種寫法（因為看起來「更保險」，怕作用域抓不到）——這樣寫實際上會製造出兩個不同步的 `dragData`（一個 module-scope 一個 window 屬性），整合時務必檢查、改成 bare 賦值。`L` 誤寫成整個重新賦值（`L = {...}`）也會讓其他保有舊 `L` 參照的閉包拿到過期資料，只能 mutate 屬性。
