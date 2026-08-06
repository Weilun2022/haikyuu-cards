---
status: accepted
---

# `qa_data_zh.json` 進版控，`all_cards.json`／`qa_data.json`／`cards_zh.json` 維持 gitignore

`.gitignore` 對 `*.json` 是 blanket 排除，`qa_data_zh.json` 目前跟其他三個資料檔一樣沒有 git history、只存在維護者本機。2026-08 實作 `apply_qa_fixes.py` 時發生真實事故：因為本機沒有 `qa_data_zh.json`、git 全部歷史／所有 branch／release／gist／既有 worktree 都找不到，只能回頭挖對應的 GitHub issue 內文重建修正內容的比對錨點，湊不齊的部分只能用近似值。

`qa_data_zh.json` 混有 Google Translate 機翻結果跟人工審核修正過的內容（`apply_qa_fixes.py` 套用的那些修正），一旦遺失無法從官方來源重新產生——`translate_qa.py` 全量重跑也只會覆蓋掉這些人工修正，不會還原。這跟 `all_cards.json`／`qa_data.json`（官方原始資料，可從 API 完全重抓）、`cards_zh.json`（`all_cards.json`+`qa_data_zh.json`+`build_data.py` 規則鏈的確定性衍生產物，且已有 `cards_data.js` 進版控）性質不同——只有 `qa_data_zh.json` 帶有不可重建的人工判斷。

## Considered Options

- **維持現狀，四個資料檔都不進版控**：跟 `all_cards.json` 等一致，但代價是人工修正沒有任何回溯機制，2026-08 的事故會重演，且下次可能真的湊不齊。
- **`qa_data_zh.json` 進版控，其餘三個維持 gitignore（現行）**：比照這個 repo既有的 9 支 Python 腳本（原本也被 `.gitignore` 的 blanket 規則排除，2026-08 逐一 `git add -f` 加回）的做法——只保護真的無法重建的東西，不是照抄前端的「全部進版控」也不是照抄目前 JSON 資料檔的「全部排除」。

## Consequences

- 往後每次 `translate_qa_new.py`／`apply_qa_fixes.py` 改動 `qa_data_zh.json`，`docs/translation/SOP.md` 的 commit 步驟要一併 `git add haikyuu_output/qa_data_zh.json`（第一次要 `git add -f`，之後正常追蹤）。
- `translate_qa.py`（全量重跑）覆蓋人工修正的既有風險不會被這個決定加重——反而因為有 git history，誤覆蓋會變成看得到、可以 `git diff`/`git checkout` 復原的異動，而不是靜默且永久遺失。
- 三支寫檔的腳本（`translate_qa.py`/`translate_qa_new.py`/`apply_qa_fixes.py`）已經統一用 `json.dump(..., ensure_ascii=False, indent=2)`，diff 不會因為格式不一致而雜訊化。
- 這個決定不改變 `.gitignore` 的 blanket `*.py`/`*.json` 規則本身——只針對這一個檔案個別 `git add -f`，維持跟既有 Python 腳本一致的處理方式。
- 目前這個 repo 是單人手動維護、沒有 CI／多人協作寫入同一份檔案的情境——並行寫入衝突、CI schema gate、Git LFS、獨立 remote 備份等企業規模的治理機制暫不適用，規模真的成長到需要時再重新評估。
