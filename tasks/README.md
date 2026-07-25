# tasks/ 目錄說明

> **2026-07-25 起**：待辦/進度追蹤改用 GitHub Issues（見 `docs/agents/issue-tracker.md`），
> 不再用這個目錄的 `task_NN.md` 記錄「有什麼要做」。這個目錄現在只保留兩種用途：
> 1. **開發日誌**（`log.md`、`night_optimization_log.md`）——事後記錄怎麼做的、踩過什麼坑，
>    跟「追蹤還有什麼待辦」是不同性質，繼續沿用。
> 2. **跨 session 平行發包機制**（本檔案其餘內容）——如果某張 GitHub Issue 的實作量大到需要
>    拆給多個子 Chat 平行處理，還是可以用這套機制執行，只是「這張票要不要做、做到哪」的狀態
>    現在記在 GitHub Issue 上，不是這裡的 `task_NN.md`。
>
> 4 月批次的舊 `task_01~10.md`/`output_01~10.md`/`collect_*.md` 已依下方「所有 task/output 檔
> 完成後可歸檔」的既有慣例搬進 `tasks/archive/`。

## 用途
中樞（主 Chat）透過此目錄向子 Chat 發包，實現跨 session 並行開發。

## 檔案命名規則
| 檔案 | 說明 |
|------|------|
| `task_NN.md` | 中樞寫給第 NN 個子 Chat 的任務書 |
| `output_NN.md` | 子 Chat NN 的程式碼產出（子 Chat 寫） |
| `collect_BATCH.md` | 收尾 Chat 的任務書（中樞寫） |
| `collect_result.md` | 收尾 Chat 的整合回報（收尾 Chat 寫） |
| `task_template.md` | 任務書範本 |
| `collect_template.md` | 收尾任務書範本 |
| `subchat_prompt_template.md` | 開子 Chat 時貼的 Prompt 範本 |

## 執行流程
```
中樞 → 寫 task_01~NN.md
     → 同時開 N 個子 Chat（各自讀自己的 task）
     → 子 Chat 各自寫 output_NN.md（並行，不碰 index.html）
     → 全部完成後，開收尾 Chat
     → 收尾 Chat 整合所有 output 進 index.html
     → 收尾 Chat 寫 collect_result.md
     → 中樞讀 collect_result.md → git commit & push
```

## 注意事項
- 子 Chat **禁止直接修改 index.html**，只能輸出程式碼到 output_NN.md
- 衝突偵測由收尾 Chat 負責，衝突時停止並回報，不自行決策
- 所有 task/output 檔完成後可歸檔（移至 tasks/archive/）
