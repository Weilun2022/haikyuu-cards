# 任務 04 輸出：下方 Deck Tray 在 Mobile 滾動時隱藏/顯示

---

### 【插入位置 1 — CSS】

找到 `index.html` 第 601 行：

```css
  .deck-tray.visible { transform: translateY(0); }
```

在此行**之後**（第 601 行後面）插入以下程式碼。

---

### 【程式碼 1 — CSS】

```css
  .deck-tray.visible.tray-scroll-hidden { transform: translateY(100%); }
```

---

### 【插入位置 2 — JS】

找到 `index.html` 第 1658–1662 行的 scroll listener 中的 if/else 區塊：

```js
      if (y > lastY && y > 60) {
        wrapper.classList.add('header-hidden');
      } else {
        wrapper.classList.remove('header-hidden');
      }
```

- 在 **if 區塊**（`wrapper.classList.add('header-hidden');` 之後）新增一行
- 在 **else 區塊**（`wrapper.classList.remove('header-hidden');` 之後）新增一行

---

### 【程式碼 2 — JS】

修改後的完整 if/else 區塊如下（新增行以註解標示）：

```js
      if (y > lastY && y > 60) {
        wrapper.classList.add('header-hidden');
        document.querySelector('.deck-tray').classList.add('tray-scroll-hidden');    // 新增
      } else {
        wrapper.classList.remove('header-hidden');
        document.querySelector('.deck-tray').classList.remove('tray-scroll-hidden'); // 新增
      }
```

---

### 【說明】

**CSS 部分：**  
新增 `.deck-tray.visible.tray-scroll-hidden` 選擇器，使用三重 class 確保優先度高於 `.deck-tray.visible`，將 tray 推回畫面底部外（`translateY(100%)`）。`.mini` 狀態屬於 `.visible` 的子集，同樣受此規則影響，行為一致。

**JS 部分：**  
在現有 scroll listener 的 if/else 內分別加一行，操作 `.deck-tray` 的 `tray-scroll-hidden` class：
- 向下滾動且超過 60px → 加上 `tray-scroll-hidden`，tray 滑出底部
- 向上滾動（或位置 ≤ 60px）→ 移除 `tray-scroll-hidden`，tray 回到原位

條件與上方 `#sticky-wrapper` 完全一致，兩列行為同步。桌機（`innerWidth > 600`）因為 `return` 提前退出，行為不受影響。

**整合注意事項：**  
- `document.querySelector('.deck-tray')` 假設頁面只有一個 `.deck-tray` 元素，符合現有 HTML 結構
- 當 `.deck-tray` 沒有 `.visible` 時，tray 本已在畫面外（`translateY(100%)`），加不加 `tray-scroll-hidden` 視覺上無差異，邏輯安全
- `filter-panel` 開啟時 scroll listener 直接 return，tray 狀態不會被異動，符合預期

---

### 【遺留問題】

無
