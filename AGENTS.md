# AGENTS.md — Codex 接手開發指引

本 repo 是「排球少年」卡牌總站（`Weilun2022/haikyuu-cards`）。Claude Code 與 Codex 輪流開發：Claude 額度用完時由 Codex 接手，反之亦然。回覆與 commit 訊息一律用繁體中文。

## 開工前必讀
1. `CLAUDE.md`（專案規則，Codex 同樣適用，其中 Claude 專屬 skill 流程除外）
2. `CONTEXT-MAP.md` → 各 context 的 `CONTEXT.md` 與 `docs/adr/`（先讀 ADR 再改設計，別推翻已定案決策）
3. `CODING_STANDARDS.md`、`ARCHITECTURE.md`
4. `docs/agents/issue-tracker.md`、`docs/agents/triage-labels.md`

## 與 Claude 對齊的工具（Codex 要能做 Claude 做得到的事）
- **Skills**：Claude 的 21 個 skill 已同步到 `C:\Users\evils\.codex\skills`（`grilling`、`to-spec`、`to-tickets`、`implement`、`tdd`、`code-review`、`diagnosing-bugs`、`codebase-design`、`domain-modeling`、`prototype`、`research`、`resolving-merge-conflicts`、`triage`、`wayfinder`、`improve-codebase-architecture` 等）。情境符合時直接用，用法與 `CLAUDE.md`「Matt Pocock 開發流程」一致：A 類流程骨幹 skill 只有使用者親自點名才跑；B 類（diagnosing-bugs、codebase-design、prototype、research、resolving-merge-conflicts）可主動用，但僅限診斷/探索/一次性驗證，不得拿來累積要 merge 的正式功能。skill 內若提到 Claude 專屬工具（Agent/subagent、ToolSearch 等），用 Codex 自己的等效功能替代。
- **共用記憶**：專案記憶在 `C:\Users\evils\.claude\projects\C--Users-evils-Documents-Claude-Claude-Code-----\memory\`，開工先讀 `MEMORY.md` 索引，再讀與任務相關的檔案（含使用者偏好、踩過的坑、測試法）。學到新的、非顯而易見的事，照同格式（frontmatter：name/description/metadata.type）寫進同一資料夾並更新 `MEMORY.md` 索引，讓 Claude 也看得到。**這資料夾含個人資訊，絕不可複製進 repo 或 commit。**
- **Gemini 橋接**：MCP server `gemini-bridge`（設定在 `~/.codex/config.toml`，與 Claude 共用同一支 server）用於批次查證/第二意見。需重開 Codex 才會載入。
- **A2A 混合模式**（`docs/agents/a2a-hybrid-workflow.md`）：原設計是 Claude↔GPT。Codex 本身就是 GPT 系，不要自己問自己；Codex 跑 `/grilling`、`/to-spec`、`/to-tickets` 時，改以 `gemini-bridge` 當唱反調的對手，其餘規則（猜測標註、`/implement` 前白話總結、失敗改問使用者）不變。
- 不要把任何 API 金鑰、token 寫進 repo 或回覆。

## 工作來源與關卡
- 唯一的 repo 路徑：`C:\Users\evils\Documents\Claude\Claude Code\排球少年`（含大量刻意 untracked 的資料檔，不要另外 clone 一份開發）。
- 任務來自 GitHub Issues（`gh` CLI）。`ready-for-agent` 只代表規格就緒、**可以被接**，不代表可以直接動手；`ready-for-human` / `needs-info` / `needs-triage` 不碰。
- **開工關卡**：只有使用者在 Codex 對話裡明確說「做 #N」「實作 #N」「/implement」之類，才開始寫 code。沒被點名就只能讀、分析、回報；不要自己挑 issue 開工，也不要自己發明沒有 issue 的新功能。
- 使用者點名後：開工在 issue 留言「Codex 接手」，完工留言摘要與 commit，避免和 Claude 重工。
- 流程骨幹 skill（`grilling` `to-spec` `to-tickets` `implement` 等）Codex 與 Claude 權限相同：**使用者在 Codex 對話中親自點名（打 skill 名或 `/名稱`）才執行**，Codex 不得自行判斷觸發。被觸發後照 skill 本身指示執行，不再轉包給其他 subagent。Claude 專屬的 hooks / harness 機制不存在，以 skill 指示 + 本檔規則取代。
- Codex 與 Claude 產出的規格、票、ADR 一律存同一處（GitHub Issues、`docs/`、各 `CONTEXT.md`），互相可接手；接手前先讀對方留下的最新 issue 留言與 commit。

## 交接協議（避免兩個 AI 互相覆蓋）
- 動工前先 `git fetch` + `git status` + `git log origin/main -5`。
- 判斷「別人的未提交修改」的標準：**已追蹤（tracked）檔案**出現你沒改的 modified/staged 變更 → 停手回報。**untracked 檔**（如 `haikyuu_output/`、`deck_evo/*.db*`、`deck_health/`、`winning_decks/`、`*.bak`、各種 `out_*.txt`、預覽 html）是刻意留在本機的，視為背景雜訊：不動、不刪、不 add、不因它們停工。
- 小修（≤3 個檔、不改設計、有測試涵蓋）直接在 `main`，commit 後 push。大功能（跨多檔、動資料格式/ADR/雲端同步/規則引擎）開分支 `codex/<主題>`，push 分支後回報使用者，由使用者決定合併；Codex 不自己 merge 到 `main`。
- 一次只做一張 issue；做完先 commit + push，再接下一張。
- 收工時在最後回覆列出：做了什麼、改了哪些檔、測試結果、未完成/卡住的事。

## 硬性禁止
- 不動 untracked 的資料與備份：`haikyuu_output/`、`deck_evo/*.db*`、`deck_health/`、`winning_decks/`、`*.bak`、`firebase-config.local.json`。
- 人工修正過、無法重建的資料檔（如 `MANUAL_OVERRIDES`、`qa_data_zh.json`、翻譯對照）改完立刻 commit。
- 不 force push、不改寫歷史、不改 `firestore.rules` 與雲端同步邏輯（需使用者明確同意）。
- 不要自動排程的產物（`schedule_data.js` 等 `chore(schedule)` commit）手動改。
- 健檢運算由排程 `HaikyuuDeckRunner` 自動執行，不需介入。
- 測試同步功能一律 mock `hvCloudSync`，不要用真實帳號寫真牌組。

## 開發與驗證
- 靜態站，本機預覽：`python dev_server.py`。
- 測試指令與慣例以 `CODING_STANDARDS.md` 為準：根目錄 Python pipeline 用 `pytest`（先 `pip install -r requirements.txt`）；`functions/`、`js/` 用 `node:test`（如 `node --test`）。
- 改完必跑相關測試；UI 變更需實際開頁面確認（手機寬度也要看，手機不能 pinch zoom，見 `css/` 與 ADR）。
- 修 bug 先寫會失敗的測試再修（tdd）。
- 商品/卡牌翻譯規則在 `build_data.py`，改動前先跑 `test_build_data.py`。

## Commit 規範
- 格式沿用歷史：`fix(game): …`、`feat(game): …`、`docs(game): …`、`chore(…): …`。
- 說「推上去」＝ commit **且** push 到 GitHub。
- commit 訊息結尾加：`Co-Authored-By: Codex <noreply@openai.com>`
