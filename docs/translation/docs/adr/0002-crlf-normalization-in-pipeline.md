---
status: accepted
---

# Pipeline 主迴圈對 skill/annotation 原文做 CRLF→LF 正規化

`build_data.py` 讀入每張卡時，開頭就把 `skill`/`annotation` 欄位的 `\r\n` 換成 `\n`，才送進 `translate_skill()`/`translate_annotation()`。

## Considered Options

- 不特別處理換行符——原本的做法，結果 HV-P01-013/031、HV-P02-011/035/041、HV-D01-003、HV-D02-002 等卡片因為原始資料用 `\r\n` 而非 `\n`，所有寫死 `\n` 的 regex 規則跟 `ANNOTATION_ZH` 查表全部比對失敗，整段譯文假名殘留，且長期沒被舊版假名殘留掃描腳本抓到（舊腳本只掃 P03 系列）。
- **在 pipeline 入口統一正規化（現行）**：一次性修復，不用逐卡開 MANUAL_OVERRIDE，也不用把每條規則都改成同時支援 `\n`/`\r\n` 兩種寫法。

## Consequences

這行正規化看起來像多餘的防呆，容易被誤以為可以刪掉——**不能刪**，刪了會讓上述那批卡片的假名殘留 bug 原封不動地重新出現，而且很可能又要等下一次全庫掃描才會被發現。假名殘留掃描工具（`check_translations.js` 等）也必須掃**全庫**而非只掃特定系列，才能真正抓到這類編碼層級的假陰性。
