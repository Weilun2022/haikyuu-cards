# 任務 01：修復 Q&A 事件牌名未還原為日文的問題

## 背景
build_data.py 的 `restore_event_names()` 函式負責將 Q&A 文字中被翻成中文的事件牌名還原為日文原文。
但 `translate_skill()` 對部分事件牌名翻譯結果有誤（例如 `誰だろうと受けて立つ` → `誰だろう和受けて立つ`，日中混雜），
導致反查表（`zh_to_jp_event`）裡存的中文譯名，和 `qa_data_zh.json` 裡 AI 翻譯的中文不一致，無法還原。

已確認案例：
- HV-P01-056 的 Q&A id=261，`question` 欄位含 `HV-P01-093"無論是誰我都會接受"`，應為 `HV-P01-093「誰だろうと受けて立つ」`

## 目標
1. 掃描 `haikyuu_output/qa_data_zh.json`，找出所有出現在 `question_zh` / `answer_zh` 中但尚未還原的事件牌名中文版本
2. 在 `build_data.py` 新增 `QA_EVENT_ZH_MAP` 常數（日文→中文對照表），補齊這些映射
3. 更新 `restore_event_names()` 邏輯，讓它同時查 `QA_EVENT_ZH_MAP`
4. 重跑 `python build_data.py`，確認 HV-P01-056 的 Q&A id=261 中事件牌名已還原為日文

## 技術細節

**關鍵函式位置（build_data.py）：**
- `restore_event_names()` — 約第 97 行
- `zh_to_jp_event` 建立邏輯 — 約第 1132～1137 行
- Q&A 寫入邏輯 — 約第 1183～1192 行
- `_EVENT_NAMES` 動態清單 — 約第 1121～1130 行

**`QA_EVENT_ZH_MAP` 放置位置：**
放在 MANUAL_OVERRIDES 附近的常數區（檔案上半部），格式如下：
```python
# Q&A 文字中事件牌名的中文譯名 → 日文原名
# （用於補救 translate_skill 翻譯不準確時的反查失敗）
QA_EVENT_ZH_MAP: dict = {
    '無論是誰我都會接受': '誰だろうと受けて立つ',
    # ... 其他需補的項目
}
```

**`restore_event_names()` 修改方式：**
在現有 `zh_to_jp` 替換完成後，再跑一次 `QA_EVENT_ZH_MAP` 替換：
```python
def restore_event_names(text: str, zh_to_jp: dict) -> str:
    if not text:
        return text
    for zh, jp in zh_to_jp.items():
        text = text.replace(zh, jp)
    for zh, jp in QA_EVENT_ZH_MAP.items():  # 補救層
        text = text.replace(zh, jp)
    return text
```

**掃描邏輯（找出所有受影響案例）：**
讀取 `haikyuu_output/qa_data_zh.json`，對每個 `question_zh` / `answer_zh`，
檢查是否包含 `_EVENT_NAMES` 裡任何一個事件牌名的中文譯名（用 `translate_skill(name, event_names=[])` 取得），
也要額外比對是否包含 `QA_EVENT_ZH_MAP` 裡的 key，用來驗證修復是否完整。

## 操作範圍
- 只能讀：build_data.py、haikyuu_output/qa_data_zh.json、all_cards.json
- 只能寫：tasks/output_01.md
- 禁止直接修改 build_data.py 或任何其他檔案

## 禁止事項
- 不能修改 build_data.py、index.html、cards_data.js 或任何 .json
- 不能 git commit / push
- 不能自行擴大範圍（只修這個 bug）

## 輸出格式（寫入 tasks/output_01.md）

### 【掃描結果】
列出 qa_data_zh.json 中所有含未還原事件牌名的案例（卡號、Q&A id、問題或答案片段）

### 【QA_EVENT_ZH_MAP 內容】
完整的 dict 常數程式碼（含所有需補的項目）

### 【restore_event_names 修改後完整程式碼】
修改後的完整函式

### 【插入位置】
QA_EVENT_ZH_MAP 要插入 build_data.py 的哪一行之後（給整合 Chat 用）

### 【說明】
修改邏輯說明與任何注意事項

### 【遺留問題】
執行中發現的問題或需中樞決策的事項，沒有則填「無」
