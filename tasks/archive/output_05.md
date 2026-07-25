# 任務 05 輸出：Modal QA 區塊預設展開

## 【插入位置】

`index.html` 第 1901–1914 行，`openModal` 函式內 `qaEl.innerHTML = \`...\`` 指派段落。

---

## 【程式碼】

```js
qaEl.innerHTML = `
  <button class="modal-qa-toggle open" id="${toggleId}" aria-expanded="true">
    <span class="modal-qa-arrow">▶</span> Q&amp;A（${qa.length} 件）
  </button>
  <div class="modal-qa-inner" id="${listId}">
    <div class="modal-qa-list open" id="${listId}-inner">
      ${qa.map(item => `
        <div class="qa-item">
          <div class="qa-date">${item.date || ''}</div>
          <div class="qa-q"><span class="qa-prefix-q">Q</span>${escapeHtml(item.question || '')}</div>
          <div class="qa-a"><span class="qa-prefix-a">A</span>${escapeHtml(item.answer || '').replace(/\n/g, '<br>')}</div>
        </div>`).join('')}
    </div>
  </div>`;
```

---

## 【說明】

三處修改如下：

1. **`<button>` 加上 `class="modal-qa-toggle open"`，`aria-expanded="false"` 改為 `aria-expanded="true"`**
   - 效果：按鈕一開始就帶有 `open` class（箭頭樣式與 CSS active 狀態正確），且 ARIA 無障礙屬性也反映已展開狀態。

2. **`<div class="modal-qa-inner"` 移除 `style="display:none"`**
   - 效果：包覆 QA 列表的容器預設可見，不再被 `display:none` 隱藏，內容直接顯示。

3. **`<div class="modal-qa-list"` 加上 `class="modal-qa-list open"`**
   - 效果：列表本體帶有 `open` class，CSS transition / 展開動畫的終態樣式（opacity、max-height 等）一開始即套用，視覺上完整展開。

`addEventListener` 的 toggle 邏輯完全不變，因為 click 時 `classList.toggle('open')` 仍能正確切換開關狀態。

---

## 【遺留問題】

無
