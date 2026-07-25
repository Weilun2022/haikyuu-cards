# 任務 09：翻譯回報處理

## 背景
index.html 的卡牌 Modal 有「🚩 回報翻譯問題」按鈕，點擊後會開 GitHub Issue（label: `translation`）。
本任務負責：從 GitHub Issues 抓取所有 `translation` 標籤的 Issue，整理成修正建議，輸出可直接套用至 cards_zh.json 的 patch 清單。

## 目標
1. 讀取 GitHub repo `Weilun2022/haikyuu-cards` 所有 open + closed Issues（label: `translation`）
2. 解析每筆 Issue 的內容（卡號、當前翻譯、建議翻譯）
3. 輸出結構化修正清單，格式見下方【輸出格式】

## 技術細節

### Issue 內容結構（由 index.html 自動填入）
```
## 卡號
HV-P01-002

## 卡名
日向 翔陽

## 當前技能文字
[=登場][=攻擊區] 支付3 Guts後可發動。...

## 建議翻譯
（用戶填寫）

## 補充說明
（選填）
```

### 資料來源
- GitHub API（無需 token，public repo）：
  `https://api.github.com/repos/Weilun2022/haikyuu-cards/issues?labels=translation&state=all&per_page=100`
- 卡牌資料對照：
  `C:\Users\evils\Documents\Claude\Claude Code\排球少年\cards_zh.json`
  → 用 `card_no` 對應，找到該卡的 `image_file` 與當前 `skill_zh`

### 判斷邏輯
- Issue body 中「建議翻譯」欄位有實質內容 → 列為「待審核」
- 「建議翻譯」欄位空白或只有 HTML 注解 → 列為「待補充」
- Issue 已 closed → 標記狀態為 `closed`

## 操作範圍
- 可讀：cards_zh.json、GitHub API（fetch）
- 只能寫：tasks/output_09.md
- 禁止修改任何 .html / .js / .py / .json 檔案

## 禁止事項
- 不能修改任何程式碼或資料檔案
- 不能 git commit / push
- 不能自行套用修正至 cards_zh.json

## 輸出格式（寫入 tasks/output_09.md）

### 【摘要】
- 共抓到幾筆 Issue
- 待審核 / 待補充 / 已關閉 各幾筆

### 【修正清單】
每筆格式：
```
---
Issue #號 | 狀態: 待審核/待補充/closed
卡號: HV-P01-002
卡名: 日向 翔陽
image_file: HV-P01-002-I.webp
當前 skill_zh: （從 cards_zh.json 取得）
建議翻譯: （從 Issue body 解析）
補充說明: （從 Issue body 解析，選填）
GitHub 連結: https://github.com/Weilun2022/haikyuu-cards/issues/N
---
```

### 【無法解析的 Issue】
列出卡號欄位空白或格式異常的 Issue 編號與標題

### 【遺留問題】
執行中發現的問題，沒有則填「無」
