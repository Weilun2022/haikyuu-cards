# 任務 05：Modal QA 區塊預設展開

## 背景
Modal 的 Q&A 區塊目前預設為摺疊狀態，需要點擊 toggle 才能展開。
產品決策：若有 QA 資料，預設就展開，讓使用者直接看到內容。

## 目標
1. 開啟 modal 時，若有 QA 資料，Q&A 區塊預設為展開狀態（不需使用者點擊）

## 技術細節

### 現有 JS（約 line 1901–1928，`openModal` 函式內）
```js
qaEl.innerHTML = `
  <button class="modal-qa-toggle" id="${toggleId}" aria-expanded="false">
    <span class="modal-qa-arrow">▶</span> Q&amp;A（${qa.length} 件）
  </button>
  <div class="modal-qa-inner" style="display:none" id="${listId}">
    <div class="modal-qa-list" id="${listId}-inner">
      ...
    </div>
  </div>`;
document.getElementById(toggleId).addEventListener('click', function() {
  const isOpen = this.classList.toggle('open');
  this.setAttribute('aria-expanded', isOpen);
  const wrapper = document.getElementById(listId);
  const inner = document.getElementById(listId + '-inner');
  if (isOpen) {
    wrapper.style.display = 'block';
    requestAnimationFrame(() => inner.classList.add('open'));
  } else {
    inner.classList.remove('open');
    inner.addEventListener('transitionend', () => { wrapper.style.display = 'none'; }, { once: true });
  }
});
```

### 修改重點
HTML 字串中：
1. `<button>` 加上 `class="modal-qa-toggle open"`，`aria-expanded="true"`
2. `<div class="modal-qa-inner"` 移除 `style="display:none"`
3. `<div class="modal-qa-list"` 加上 `class="modal-qa-list open"`

addEventListener 的邏輯不需要改，因為 toggle click 已能正確切換狀態。

## 操作範圍
- 只能讀：index.html（禁止直接修改）
- 只能寫：tasks/output_05.md

## 禁止事項
- 不能修改任何 .html / .js / .py 檔案
- 不能 git commit / push
- 不能自行擴大功能範圍

## 輸出格式（寫入 tasks/output_05.md）

### 【插入位置】
找到 `openModal` 函式內 QA 區塊（約 line 1901），說明修改的完整 innerHTML 字串

### 【程式碼】
輸出修改後的完整 `qaEl.innerHTML = \`...\`` 字串（只要 innerHTML 指派那段，不含 addEventListener）

### 【說明】
（修改了哪三處，各自的效果）

### 【遺留問題】
（無則填「無」）
