## Agent skills

### Issue tracker

GitHub Issues on `Weilun2022/haikyuu-cards`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five canonical labels (`needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context — root `CONTEXT-MAP.md` points to three contexts（卡片目錄/牌組管理、對戰遊戲引擎、卡牌翻譯 Pipeline），各自有自己的 `CONTEXT.md` + `docs/adr/`。See `docs/agents/domain.md`.

### Matt Pocock 開發流程

流程順序：setup-matt-pocock-skills → grill-with-docs → to-spec → to-tickets → implement → code-review
（improve-codebase-architecture 為定期維護；triage 僅在採用正式 issue tracker 時才用）

硬性規則：
- 流程骨幹類 skill（A 類：setup-matt-pocock-skills、grill-with-docs、to-spec、to-tickets、implement、triage、improve-codebase-architecture）全部是 user-invoked，只能等我親自打指令觸發，agent 不能自己判斷去跑。
- tickets 發布完 ≠ 可以開始寫 code。必須等我明確打 `/implement` 才能動手，也不能用 spawn 子代理繞過這道關卡自己先做掉。
- `/implement` 被觸發後，照它本身的指示直接執行（TDD、測試、code-review、commit），不要再往下轉包給其他 subagent。
- model-invoked 類 skill（B 類：diagnosing-bugs、codebase-design、prototype、research、resolving-merge-conflicts 等）不受上述關卡限制——不管這個專案是否正式跑過 `/setup-matt-pocock-skills`，只要情境合適（回報 bug/效能問題、設計模組介面、需要驗證設計假設、需要查一手資料、解決 merge 衝突），都應該主動提醒我可以用哪個 skill，這是輕量提醒，不是硬性流程。**但範圍僅限診斷/探索/一次性驗證**——`prototype` 產出的是用完即丟的原型、`research` 產出的是文件，不能拿這些 skill 的名義去累積實際會被 merge 的正式功能程式碼；真的要做的功能還是得走 `/to-spec`→`/to-tickets`→`/implement` 這條路，或走前面談過的輕量 bug 修復迴圈（tdd + code-review），不能用「這只是在驗證設計」當藉口繞過關卡。
- `wayfinder`、`ask-matt` 是隨時可用的輔助工具（也是 A 類 user-invoked，但不屬於上面那條主線順序）：`wayfinder` 用於在 issue/spec 之間導航（map、child issue、blocking 關係），`ask-matt` 用於查詢 Matt Pocock 本人對這套流程的既有說明/FAQ。需要時我會直接打對應指令。

### A2A 協作（Pocock 混合模式）

`/grilling`、`/to-spec`、`/to-tickets` 這些關卡被使用者觸發後，關卡內部改成 Claude↔GPT 透過 A2A 協議自主收斂決策，不再逐題問使用者；只有真正只有使用者才知道的業務判斷才會中斷詢問，其餘用合理猜測繼續走，並在 `/implement` 前給使用者一次白話總結確認。上述「slash command 關卡本身仍由使用者觸發」的硬性規則不受影響。詳見 `docs/agents/a2a-hybrid-workflow.md`。

舊的 `web-collab` skill（`reviewer.js`）已停用，改用這套 A2A 工具。
