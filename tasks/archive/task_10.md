# task_10 — 庫存分析：缺牌排序 + 分段顯示

## 背景
排球少年卡牌網站 `index.html`（單檔前端，約 3600 行）。
庫存分析面板（`#analysis-overlay`）目前每張卡顯示：左上角持有數 input、右下角 `×N`（需求數）badge。

## 需求
1. **右下角 badge 改為缺牌數**：`max(0, need - have)` = 缺 N 張。已完成（deficit = 0）顯示 `✓`。
2. **依缺牌數排序**：缺越多的排越前面（deficit 降冪）。已完成的全排在後。
3. **分兩個 section**：
   - 「未完成」section：deficit > 0 的卡
   - 「已完成」section：deficit = 0 的卡
   - 各 section 加標題列（顯示 section 名稱 + 卡片數量，e.g.「未完成（5張）」「已完成（3張）」）
   - 若某 section 為空則不顯示

## 操作範圍
**只修改** `index.html` 中的：
1. `renderAnalysis()` 函式（約 2696–2768 行）
2. `saveAnCount` 閉包內（約 2738–2759 行）：owned 更新後要同步更新同一張卡的 badge 元素（改為顯示最新 deficit）
3. 如需新增 CSS（section header 樣式），加在現有 `.an-card` 附近的 CSS 區塊（約 950–1140 行）

**禁止修改** 其他任何部分。

## 現有程式碼片段（供參考）

```js
// renderAnalysis() 目前的卡片 HTML 模板（2726–2732）
div.innerHTML = `
  <img class="an-card-img" src="${imgSrc}" alt="" onerror="this.style.background='var(--surface2)'">
  <div class="an-own-counter">
    <input type="number" class="an-count-input" data-img="${entry.image_file}" data-need="${need}" value="${have}" min="0" title="持有數（需要 ${need} 張）">
  </div>
  <div class="an-need-badge">×${need}</div>
  <div class="an-card-name">${displayName}</div>`;
```

`an-need-badge` = 要改為顯示 deficit 的那個元素。

```js
// saveAnCount 更新 class 的地方（2754）
div.className = `an-card ${have2 >= need2 ? 'owned' : have2 > 0 ? 'partial' : 'not-owned'}`;
// 這行後面要補：更新 badge 元素內容
```

## section header CSS 建議
```css
.analysis-section-header {
  grid-column: 1 / -1;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-dim);
  padding: 8px 4px 4px;
  border-bottom: 1px solid var(--border);
  margin-top: 4px;
}
```

## 輸出格式
把完整修改內容寫入 `tasks/output_10.md`，格式：

### CSS 新增
（要加在 `.an-card` 附近的 CSS）

### renderAnalysis() 完整替換
（從 `function renderAnalysis() {` 到最後的 `}` 的完整新版本）

不要修改任何其他檔案。
