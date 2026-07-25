---
status: accepted
---

# 視覺主題色票直接讀官方卡表頁的 UI 元件 computed style，不用 key visual 圖片採樣

`css/theme.css` 的 `--accent`/`--accent2` 等色票數值來自直接讀取官方卡表搜尋頁（`/cardlist/`）實際在用的 UI 元件 computed style，而不是用 canvas 從官方 key visual 主視覺圖片採樣像素定色。

## Considered Options

- **v1**：自訂暖米色，跟官方風格無關，已棄用。
- **v2**：canvas 採樣官方 key visual 圖片像素——猜官方風格是紅色點綴，後來證實猜錯。
- **v3（現行）**：直接讀官方頁面真正在用的 UI 元件顏色，準確抓到 `#DF600D`（按鈕實色）、`#0D0506`（內文黑）、`#EDA613`（琥珀金選中色），不是 v2 猜測的紅色。

## Consequences

`--accent`/`--accent2` 刻意比官方原色再加深一點（`#DF600D`→`#BE520B`、`#EDA613`→`#9C6209`），因為官方原色套在我們的小字白字 badge 上對比度不到 4.5:1。之後如果官方改版視覺，要重新走一次「讀官方頁面 UI 元件 computed style」而不是回頭用圖片採樣。改 accent/accent2 之後務必連帶檢查跟九校色票有沒有新的撞色（過去發生過跟「烏野」「梟谷」撞色的案例）。
