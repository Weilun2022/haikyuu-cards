# 信箱（工作單與結果）

## 大樣本運算（2026-10-15 起：GitHub Actions）
- 雲端 Claude 把工作寫進 `jobs.json` 並 push 到 deck-health 分支
- GitHub Actions（`.github/workflows/deck-health-jobs.yml`）自動為每個還沒完成的工作開一台 4 核機器，平行執行
- 結果自動推回 `results/<工作編號>/`（status.json、log.txt、out.jsonl）；`git pull` 即可讀
- 查進度：`gh run list -R Weilun2022/haikyuu-cards --branch deck-health -L 5`
- 只允許白名單程式（compare2、gauntlet、vs_deck、optimize、optimize_guard、solo、template），參數只能是數字、deck_health 內的檔名、{cards}、{out}
- 已有 status.json 的工作不會重跑；要重跑請用新編號（加主題前綴：FUKU-、SHIRA-、INARI-…）
- 不需要 Weilun 的電腦，也不需要任何人操作

## 本機 Claude 訊息（只在需要本機檔案、API key、Windows 環境時才用）
- `to_local.md`：雲端 Claude 寫給本機的訊息（本機只讀）
- `from_local.md`：本機寫給雲端 Claude 的訊息（雲端只讀）
- 讀之前先 `git pull origin deck-health`；寫完立刻 commit 並 push
- 每封訊息最上面寫時間和「回覆的是哪一封」，舊訊息往下保留
- 不要在信箱放 API key、密碼或任何個人資料
- 本機 Claude 不執行 repo 裡的程式（舊的 runner 排程方式已停用）
