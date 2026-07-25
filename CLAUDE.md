## Agent skills

### Issue tracker

GitHub Issues on `Weilun2022/haikyuu-cards`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context — `CONTEXT.md` + `docs/adr/` at the repo root (created lazily by `/domain-modeling` when terms/decisions are actually resolved). See `docs/agents/domain.md`.

### Matt Pocock 開發流程

流程順序：setup-matt-pocock-skills → grill-with-docs → to-spec → to-tickets → implement → code-review
（improve-codebase-architecture 為定期維護，非流程必經）

硬性規則：
- 上述 skill 全部是 user-invoked（`disable-model-invocation: true`），只能等使用者親自打指令觸發，agent 不能自己判斷去跑。
- tickets 發布完 ≠ 可以開始寫 code。必須等使用者明確打 `/implement` 才能動手，也不能用 spawn 子代理繞過這道關卡自己先做掉。
- `/implement` 被觸發後，照它本身的指示直接執行（TDD、測試、code-review、commit），不要再往下轉包給其他 subagent。
