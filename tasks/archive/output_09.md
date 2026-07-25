# 任務 09 輸出：翻譯回報處理

執行日期：2026-04-17（最終結案）

---

## 【摘要】

- 共抓到 **2** 筆 Issue（label: `translation`，state: all）
- 待審核：**2** 筆
- 待補充：**0** 筆
- 已關閉（closed）：**2** 筆

---

## 【修正清單】

---
Issue #3 | 狀態: closed（疑似測試，人工關閉）
卡號: HV-P01-002
卡名: 日向 翔陽
image_file: HV-P01-002-I.webp
當前 skill_zh: [=登場][=攻擊區] 支付3 Guts後可發動。此角色的攻擊值 +4，對手下回合中，對手原本接球值6或以上的接球角色不能出場
建議翻譯: 再填一張單
補充說明: （無）
GitHub 連結: https://github.com/Weilun2022/haikyuu-cards/issues/3
備注: 建議翻譯內容「再填一張單」語意不明，疑為測試送出，建議人工確認是否為有效回報。
---

---
Issue #4 | 狀態: closed（已採納，cards_zh.json 已更新）
卡號: HV-P02-003
卡名: 月島 蛍
image_file: HV-P02-003-I.webp
當前 skill_zh: [=登場][=攔網區] 對手的Event區中的牌有2張或以上時，從自己的手牌將Event牌1張放置至Event區後可發動。抽1張牌，此角色的攔網值 +6
建議翻譯: [=登場][=攔網區] 對手的事件區中的牌有2張或以上時，從自己的手牌將1張事件卡放置於事件區後可發動。抽1張牌，此角色的攔網值 +6
補充說明: （無）
差異說明:
  - 「Event區」→「事件區」（術語中文化）
  - 「Event牌1張放置至Event區」→「1張事件卡放置於事件區」（用語統一）
  - 回報者另附 Q&A 翻譯建議（非 skill_zh 範圍，僅供參考）：
    Q: 放置在事件區的卡片的技能可以與該角色的技能一起使用嗎？
    A: 不能。事件卡的技能只能在自由打出時使用。
GitHub 連結: https://github.com/Weilun2022/haikyuu-cards/issues/4
---

---

## 【無法解析的 Issue】

無。兩筆 Issue 格式均正常，所有欄位可解析。

---

## 【遺留問題】

無。

---

## 【結案紀錄】

| 日期 | 動作 |
|------|------|
| 2026-04-17 | 抓取 translation Issues，產出修正清單 |
| 2026-04-17 | 採納 Issue #4，更新 cards_zh.json（HV-P02-003 I + IP，Event→事件） |
| 2026-04-17 | Issue #3、#4 人工 closed，GitHub 翻譯回報清單歸零 |
| 2026-04-17 | 發現 cards_zh.json 非 build 來源，改正確修改 build_data.py MANUAL_OVERRIDES + qa_data_zh.json（id=344） |
| 2026-04-17 | 重新 build cards_data.js，push 至 GitHub（commit 6bd1594） |
