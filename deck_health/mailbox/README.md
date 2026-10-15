# 信箱（工作單與結果）

## 大樣本運算（2026-10-15 17:50 起：本機排程優先、GitHub Actions 備援）
- 雲端 Claude 把工作寫進 `jobs.json` 並 push 到 deck-health 分支（加工作前先 git pull）
- 工作單有 `"where": "local"` → Weilun 電腦上的排程 HaikyuuDeckRunner（每 5 分鐘、16 程序）執行 `runner.py`，結果自動推回；電腦關機時不會跑
- 沒有 where → GitHub Actions（`.github/workflows/deck-health-jobs.yml`）為每個工作開一台 4 核機器，平行執行
- 速度：本機約 270 場/秒，GitHub 每台約 54 場/秒（compare2 fuku 1 萬場：36.5 秒 vs 185 秒）
- 標 local 後 15 分鐘還沒結果 → 視為電腦沒開，改新編號、不加 where 交給 GitHub
- 結果都在 `results/<工作編號>/`（status.json、log.txt、out.jsonl）；`git pull` 即可讀
- 查 GitHub 進度：`gh run list -R Weilun2022/haikyuu-cards --branch deck-health -L 5`
- 只允許白名單程式（compare2、gauntlet、vs_deck、optimize、optimize_guard、solo、template），參數只能是數字、deck_health 內的檔名、{cards}、{out}
- 已有 status.json 的工作不會重跑；要重跑請用新編號（加主題前綴：FUKU-、SHIRA-、INARI-…）
- 不需要 Weilun 操作任何東西
- 安全：本機排程會執行這個分支上最新的程式碼，只有 Weilun 能有推送權限

## 本機 Claude 訊息（只在需要本機檔案、API key、Windows 環境時才用）
- `to_local.md`：雲端 Claude 寫給本機的訊息（本機只讀）
- `from_local.md`：本機寫給雲端 Claude 的訊息（雲端只讀）
- 讀之前先 `git pull origin deck-health`；寫完立刻 commit 並 push
- 每封訊息最上面寫時間和「回覆的是哪一封」，舊訊息往下保留
- 不要在信箱放 API key、密碼或任何個人資料
- 運算交給排程 HaikyuuDeckRunner，本機 Claude 不需要介入
