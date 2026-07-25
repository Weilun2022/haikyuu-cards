# Task 08 — Modal 加入「回報翻譯問題」按鈕

## 【建立的新檔案】
- 已建立：`.github/ISSUE_TEMPLATE/translation.md`
- 絕對路徑：`C:\Users\evils\Documents\Claude\Claude Code\排球少年\.github\ISSUE_TEMPLATE\translation.md`
- 內容為 GitHub Issue 模板（供使用者從 Issues 頁面手動建立時使用）

---

## 【插入位置 1 — CSS】
找到 CSS 中 `.qa-prefix-a { font-weight: 700; color: var(--text-dim); margin-right: 4px; }` 區塊之後（即 Modal Q&A 區段末端，約 line 513 附近）插入下列 CSS。

## 【程式碼 1 — CSS】
```css
/* ── Modal Feedback Button ── */
.modal-feedback-btn {
  display: block;
  text-align: center;
  margin-top: 14px;
  padding: 9px 12px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-dim);
  font-size: 12px;
  text-decoration: none;
  transition: border-color 0.15s, color 0.15s;
}
.modal-feedback-btn:hover {
  border-color: var(--accent2);
  color: var(--accent2);
}
```

---

## 【插入位置 2 — HTML】
找到 `<div class="modal-qa-section" id="modal-qa"></div>`（約 line 1265）之後、關閉 modal-body 的 `</div><!-- /modal-body -->` 之前，插入下列 HTML。

## 【程式碼 2 — HTML】
```html
<a class="modal-feedback-btn" id="modal-feedback-btn" href="#" target="_blank" rel="noopener">
  🚩 回報翻譯問題
</a>
```

---

## 【插入位置 3 — JS】
在 `openModal` 函式內，`document.getElementById('modal-overlay').classList.add('open');`（約 line 1931）之前加入下列 JS。

## 【程式碼 3 — JS】
```js
// Feedback button
const fbBtn = document.getElementById('modal-feedback-btn');
const feedbackTitle = `[翻譯] ${card.card_no || ''} ${card.name || ''}`.trim();
const currentSkill = card.skill_zh || card.skill || '（無）';
const feedbackBody = `## 卡號\n${card.card_no || ''}\n\n## 卡名\n${card.name || ''}\n\n## 當前技能文字\n${currentSkill}\n\n## 建議翻譯\n<!-- 請填寫您建議的翻譯 -->\n\n\n## 補充說明\n<!-- 選填 -->\n`;
fbBtn.href = `https://github.com/Weilun2022/haikyuu-cards/issues/new?labels=translation&title=${encodeURIComponent(feedbackTitle)}&body=${encodeURIComponent(feedbackBody)}`;
```

---

## 【說明】
- **Issue 模板**：`.github/ISSUE_TEMPLATE/translation.md` 供 GitHub Issues 頁面手動建立時套用；當使用者從 Modal 按鈕進入時，URL 上的 `body=` 參數會覆蓋模板內容（Modal 預填完整資訊，模板僅作備援）。
- **CSS**：新增 `.modal-feedback-btn` 樣式，為一個低調的灰色外框按鈕，hover 時邊框與文字轉為 accent2 色，與 Modal 其他元素視覺一致。
- **HTML**：在 Modal Q&A 區塊後方加入「🚩 回報翻譯問題」連結按鈕，使用 `target="_blank"` 開新分頁，`rel="noopener"` 防止 tabnabbing。
- **JS**：每次開啟 Modal 時動態組出 title 與 body（含卡號、卡名、當前技能文字），以 `encodeURIComponent` 編碼後塞入 GitHub Issue 新建頁 URL；使用者只需填寫「建議翻譯」即可送出。
- **失敗回退**：若要隱藏按鈕，僅需在 CSS 加入 `.modal-feedback-btn { display: none; }`；或 `git revert` 即可完整還原。

## 【遺留問題】
無
