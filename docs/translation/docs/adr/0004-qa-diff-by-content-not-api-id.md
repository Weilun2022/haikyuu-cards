---
status: accepted
---

# QA 更新判斷「有沒有新增」要用內容 diff，不能用官方 API 的 `id` 欄位

官方 QA API（`itemsearch.php` 的 rules QA 端點）回傳的每筆 `id` 是每次重新抓取就整批重新編號的全站流水號，不是該筆 QA 的穩定識別碼——同一筆問答內容，這次抓到 `id:400`，下次抓可能變成 `id:1317`。2026-07-09 曾經直接拿 `id` diff 新舊 QA，誤判出約 90 張卡「有新QA」，改用 `(question, answer)` 內容比對後，才發現真正新增的只有 48 張卡、114 筆。

## Considered Options

- 用 QA API 的 `id` 欄位 diff 新舊資料——實測產生大量假陽性，不能用。
- **用 `(question.strip(), answer.strip())` 內容比對（現行）**：不受官方流水號重新編碼影響，只認內容本身。

## Consequences

任何要判斷「這筆 QA 是不是新的」或「這筆 QA 有沒有被改過」的程式碼（`fetch_new_qa.py` 的差集運算、`apply_qa_fixes.py` 的定位邏輯、未來任何 QA 同步/比對工具），都必須用內容比對，不能圖方便直接比 `id` 欄位——即使 `id` 欄位看起來像是穩定主鍵，它不是。
