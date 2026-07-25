# 收尾任務：整合第 01 批子 Chat 輸出

## 背景
子 Chat 01 已完成開發，輸出存在 tasks/output_01.md。
修復目標：build_data.py 的 Q&A 事件牌名無法還原為日文的問題（共 20 個事件牌名、48 筆 Q&A 條目受影響）。

## 目標
1. 將 output_01.md 中的兩處修改套入 build_data.py
2. 執行 python build_data.py，確認生成 364 張 + HV-P01-056 id=261 已還原
3. 寫回報至 tasks/collect_result.md

## 操作範圍
- 讀：tasks/output_01.md、build_data.py
- 改：build_data.py
- 執行：python build_data.py（在專案根目錄）
- 寫：tasks/collect_result.md

## 禁止事項
- 不能修改其他任何檔案
- 不能 git commit / push

## 修改 1：插入 QA_EVENT_ZH_MAP 常數

**位置**：build_data.py 第 752 行之後（`return t.strip()` 結束的空行，MANUAL_OVERRIDES 區塊注釋之前）

精確比對字串（用此定位插入點）：
```
    return t.strip()


# ── 手動覆蓋翻譯（image_file → 正確的 skill_zh）
```

插入內容：output_01.md 的【QA_EVENT_ZH_MAP 內容】程式碼區塊，加上前後各一空行。

## 修改 2：更新 restore_event_names() 函式

**位置**：build_data.py 第 97～103 行

精確比對字串（舊版）：
```python
def restore_event_names(text: str, zh_to_jp: dict) -> str:
    """將 Q&A 文字中已翻譯的中文事件牌名還原為日文原文。"""
    if not text:
        return text
    for zh, jp in zh_to_jp.items():
        text = text.replace(zh, jp)
    return text
```

替換為 output_01.md 的【restore_event_names 修改後完整程式碼】。

## 驗證步驟
執行 `python build_data.py`，確認：
1. 輸出「[OK] 生成完成，364張」
2. 在生成的 cards_data.js 中，HV-P01-056 的 Q&A id=261 question 欄位包含 `誰だろうと受けて立つ`（日文），而非 `無論是誰我都會接受`（中文）

## 回報格式（tasks/collect_result.md）

### 【完成項目】
[兩處修改各自的插入結果]

### 【結果】
[成功 / 失敗 / 部分完成]

### 【驗證】
[build_data.py 執行結果；HV-P01-056 id=261 的 question 欄位實際內容]

### 【遺留問題】
[沒有則填「無」]

### 【待中樞決策】
[沒有則填「無」]
