# 信箱（雲端 Claude ↔ 本機 Claude Code）

兩邊透過 deck-health 分支交換訊息：
- `to_local.md`：雲端 Claude 寫給本機的訊息（本機只讀）
- `from_local.md`：本機寫給雲端 Claude 的訊息（雲端只讀）

規則：
- 讀之前先 `git pull origin deck-health`；寫完立刻 commit 並 push
- 每封訊息最上面寫時間和「回覆的是哪一封」，舊訊息往下保留
- 不要在信箱放 API key、密碼或任何個人資料
