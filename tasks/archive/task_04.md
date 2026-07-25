# 任務 04：下方 Deck Tray 在 Mobile 滾動時隱藏/顯示

## 背景
目前上方列（`#sticky-wrapper`）在 mobile 已有「滾下隱藏、滾上顯示」行為。
下方固定列（`.deck-tray`）目前只依牌組狀態顯示/隱藏，沒有滾動行為。
本任務讓兩者行為一致，提升 mobile 瀏覽空間。

## 目標
1. Mobile（`window.innerWidth <= 600`）滾動下時，`.deck-tray.visible` 隱藏至畫面底部外
2. Mobile 滾動上時，`.deck-tray.visible` 回到原位
3. 桌機（> 600px）行為不變

## 技術細節

### 現有 CSS（約 line 587–601）
```css
.deck-tray {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  transform: translateY(100%);       /* 預設隱藏 */
  transition: transform 0.3s ease;
}
.deck-tray.visible { transform: translateY(0); }   /* 有牌組時顯示 */
```
`.deck-tray.mini` 是收合狀態（細帶），也屬於 visible 狀態的子集。

### 現有 JS 滾動邏輯（約 line 1649–1665）
```js
// Mobile: hide header on scroll down, show on scroll up
(function() {
  const wrapper = document.getElementById('sticky-wrapper');
  const panel   = document.getElementById('filter-panel');
  let lastY = window.scrollY;
  window.addEventListener('scroll', () => {
    if (window.innerWidth > 600) return;
    if (panel.classList.contains('open')) return;
    const y = window.scrollY;
    if (y > lastY && y > 60) {
      wrapper.classList.add('header-hidden');
    } else {
      wrapper.classList.remove('header-hidden');
    }
    lastY = y;
  }, { passive: true });
})();
```

### 實作方式
**CSS**：新增一個 class，優先度要蓋過 `.visible`：
```css
.deck-tray.visible.tray-scroll-hidden { transform: translateY(100%); }
```

**JS**：在同一個 scroll listener 內，對 `.deck-tray` 加/移除 `.tray-scroll-hidden`：
- 條件與上方列相同（`y > lastY && y > 60` → 加，否則 → 移除）
- 不需要額外判斷 `.visible`，因為沒有 `.visible` 時 tray 本來就是 `translateY(100%)`

## 操作範圍
- 只能讀：index.html（禁止直接修改）
- 只能寫：tasks/output_04.md

## 禁止事項
- 不能修改任何 .html / .js / .py 檔案
- 不能 git commit / push
- 不能自行擴大功能範圍

## 輸出格式（寫入 tasks/output_04.md）

### 【插入位置 1 — CSS】
找到 `.deck-tray.visible { transform: translateY(0); }` 這行之後插入

### 【程式碼 1 — CSS】
```
（完整可貼入的 CSS 片段）
```

### 【插入位置 2 — JS】
找到現有 scroll listener 內 `wrapper.classList.remove('header-hidden');` 之後插入（仍在 else 區塊內）
並在 `if (y > lastY && y > 60)` 區塊內的 `wrapper.classList.add('header-hidden');` 之後也插入對應行

### 【程式碼 2 — JS】
```
（完整說明：在 if 區塊加什麼、在 else 區塊加什麼）
```

### 【說明】
（這段程式碼做什麼，以及任何整合注意事項）

### 【遺留問題】
（執行中發現的問題或需中樞決策的事項，沒有則填「無」）
