---
status: accepted
---

# QA 裁定翻譯改用 Google Translate + 術語修正表，不套用 translate_skill() 規則引擎

官方 QA 裁定文字（`qa_data.json`）的結構跟卡片技能文字（`skill_jp`）差異夠大——QA 是問答體、常見敬語與疑問句形式，技能文字是固定的規則書用語——早期曾經對 QA 文字套用一批 `translate_skill()` 風格的 regex 規則（`clean_qa_text()` 現存的 Section 1-6 就是這批規則的殘跡，且規則命中結果跟 `translate_skill()` 的助詞剝離規則吻合，是同一手法的移植），後來改為：`translate_qa.py`／`translate_qa_new.py` 呼叫 Google Translate 整段機翻，`clean_qa_text()` 只負責對機翻結果做後製修正（修正 Google 常見誤譯類別，例如 Guts／攔網相關術語）。兩條管線因此輸入本質不同（原始日文 vs 機翻後中文），不應該合併成同一個規則引擎。

## Considered Options

- 沿用 `translate_skill()` 規則鏈處理 QA 文字（早期做法）——QA 文字的敬語/疑問句形態跟技能文字的固定用語差異太大，規則覆蓋率低，需要另開一大批 QA 專屬規則，等於維護兩套規則鏈卻只服務同一目標。
- **改用 Google Translate 機翻 + 術語修正表（現行）**：機翻能處理 QA 文字的自然語言變化，`clean_qa_text()` 只需要修正 Google 常見的固定誤譯類別，維護量遠低於重寫一套規則鏈。

## Consequences

- ~~`clean_qa_text()` 內殘留的 Section 1-6（對應「沿用 translate_skill() 規則」那個被放棄的做法）目前是無害的 no-op...~~ **已於 2026-08 移除**：實際範圍是 Section 1-10（不只 1-6），刪除依據不是語料快照比對（`qa_data_zh.json` 在 git 全部歷史/所有 branch/release/gist/既有 worktree 都找不到，這條路徑走不通），而是結構性論證——這批規則的比對樣式（と→和、か→或、で→，等）只有在文字先被 `translate_skill()` 的殘留助詞規則處理過才可能出現，但 `clean_qa_text()` 唯一的輸入來源是 Google Translate 的輸出，不會產生這種殘留，所以不需要語料就能證明這批規則對現在及未來的輸入都不會命中。
- 術語修正目前分散在三處（`translate_skill()` 硬編的少數 point/value 詞彙、`official_terms.json`、`translate_qa.py` 內未進版控的 `TERM_FIX`），這不是本 ADR 決定的一部分，但收斂翻譯規則引擎時應該把三處併入 `official_terms.json` 單一來源。
- `docs/translation/CONTEXT.md` 過去完全沒記錄這條 QA 管線的存在，2026-08 架構檢視時補上。
