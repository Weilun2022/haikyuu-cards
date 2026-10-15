# 信箱（雲端 Claude ↔ 本機 Claude Code）

兩邊透過 deck-health 分支交換訊息：
- `to_local.md`：雲端 Claude 寫給本機的訊息（本機只讀）
- `from_local.md`：本機寫給雲端 Claude 的訊息（雲端只讀）

規則：
- 讀之前先 `git pull origin deck-health`；寫完立刻 commit 並 push
- 每封訊息最上面寫時間和「回覆的是哪一封」，舊訊息往下保留
- 不要在信箱放 API key、密碼或任何個人資料

## 自動執行（不需要 AI、不需要人操作）
- 本機有一個專用資料夾 `C:\Users\evils\Documents\Claude\deck_runner`（deck-health 分支的 clone），由 Windows 工作排程器每 5 分鐘執行 `deck_health/runner.py`
- 雲端 Claude 把工作寫進 `jobs.json` 並 push；runner 自動執行還沒完成的工作，結果推回 `results/<工作編號>/`（status.json、log.txt、out.jsonl）
- 只允許白名單程式（compare2、gauntlet、vs_deck、optimize、optimize_guard、solo、template），參數只能是數字、deck_health 內的檔名、{cards}、{out}
- 程序數用工作的 workers 欄位指定（上限為本機核心數 −2）
- 本機日誌 runner.log 只留在 deck_runner 資料夾，不上傳
