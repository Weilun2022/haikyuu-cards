# 任務 08：Modal 加入「回報翻譯問題」按鈕

## 背景
卡牌翻譯仍有改進空間，需要開放使用者回報錯誤或建議。網站在 GitHub Pages 靜態託管，採用 **GitHub Issue 預填連結** 方案：點按鈕開新分頁到 GitHub Issue 新建頁，URL 自動帶入卡號、卡名、當前技能文字，使用者只需補「建議翻譯」即可送出。

## 目標
1. 建立 Issue 模板檔 `.github/ISSUE_TEMPLATE/translation.md`
2. Modal 底部（QA 區塊之後）加入「🚩 回報翻譯問題」按鈕
3. 點擊按鈕開新分頁到 GitHub Issue 新建頁，title 與 body 已預填
4. 失敗關閉只需隱藏按鈕（CSS `display: none`）或 `git revert`，不影響其他功能

## 技術細節

### Repo 位置
GitHub Repo：`https://github.com/Weilun2022/haikyuu-cards`
Issue 新建 URL 格式：
```
https://github.com/Weilun2022/haikyuu-cards/issues/new?labels=translation&title={ENCODED}&body={ENCODED}
```
（使用 `labels=translation` 參數自動打標籤；`template=` 與 `body=` 同時存在時 `body=` 會覆蓋模板內容，模板僅用於使用者手動從 Issues 頁面建立時）

### Title 格式
```
[翻譯] {card_no} {card_name}
```
例：`[翻譯] HV-P01-001 日向翔陽`

### Body 格式（預填 Markdown，使用者只需補「建議翻譯」）
```markdown
## 卡號
{card_no}

## 卡名
{card_name}

## 當前技能文字
{card.skill_zh || card.skill || '（無）'}

## 建議翻譯
<!-- 請填寫您建議的翻譯 -->


## 補充說明
<!-- 選填 -->

```

### Modal 插入位置
`index.html` line 1265 `<div class="modal-qa-section" id="modal-qa"></div>` 之後、`</div><!-- /modal-body -->` 之前：
```html
<a class="modal-feedback-btn" id="modal-feedback-btn" href="#" target="_blank" rel="noopener">
  🚩 回報翻譯問題
</a>
```

### CSS 位置
放在 `/* ── Modal Q&A ── */` 區塊之後（約 line 513 附近）：
```css
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

### JS 位置
在 `openModal` 函式末端（line 1931 `document.getElementById('modal-overlay').classList.add('open');` 之前）加入：
```js
// Feedback button
const fbBtn = document.getElementById('modal-feedback-btn');
const feedbackTitle = `[翻譯] ${card.card_no || ''} ${card.name || ''}`.trim();
const currentSkill = card.skill_zh || card.skill || '（無）';
const feedbackBody = `## 卡號\n${card.card_no || ''}\n\n## 卡名\n${card.name || ''}\n\n## 當前技能文字\n${currentSkill}\n\n## 建議翻譯\n<!-- 請填寫您建議的翻譯 -->\n\n\n## 補充說明\n<!-- 選填 -->\n`;
fbBtn.href = `https://github.com/Weilun2022/haikyuu-cards/issues/new?labels=translation&title=${encodeURIComponent(feedbackTitle)}&body=${encodeURIComponent(feedbackBody)}`;
```

### Issue 模板檔內容
`.github/ISSUE_TEMPLATE/translation.md`：
```markdown
---
name: 翻譯問題回報
about: 回報卡牌翻譯錯誤或改進建議
title: '[翻譯] '
labels: translation
---

## 卡號


## 卡名


## 當前技能文字


## 建議翻譯
<!-- 請填寫您建議的翻譯 -->


## 補充說明
<!-- 選填 -->
```

## 操作範圍
- 只能讀：index.html（禁止直接修改）
- 只能寫：
  - tasks/output_08.md（所有要整合進 index.html 的片段）
  - **本任務可直接建立** `.github/ISSUE_TEMPLATE/translation.md`（因為這是新檔，不涉及 index.html 衝突）

## 禁止事項
- 不能修改任何既有 .html / .js / .py 檔案
- 不能 git commit / push
- 不能自行擴大功能範圍

## 輸出格式（寫入 tasks/output_08.md）

### 【建立的新檔案】
列出 `.github/ISSUE_TEMPLATE/translation.md` 已建立，並附上路徑

### 【插入位置 1 — CSS】
找到 CSS 中 `.qa-prefix-a { font-weight: 700; color: var(--text-dim); margin-right: 4px; }` 區塊之後（即 Modal Q&A 區段末端）

### 【程式碼 1 — CSS】
```
（完整 CSS 片段）
```

### 【插入位置 2 — HTML】
找到 `<div class="modal-qa-section" id="modal-qa"></div>` 之後、`</div>` 關閉 modal-body 之前

### 【程式碼 2 — HTML】
```
（完整 HTML 片段）
```

### 【插入位置 3 — JS】
在 `openModal` 函式內，`document.getElementById('modal-overlay').classList.add('open');` 之前

### 【程式碼 3 — JS】
```
（完整 JS 片段）
```

### 【說明】
（簡述三處修改與 Issue 模板建立的效果）

### 【遺留問題】
（無則填「無」）
