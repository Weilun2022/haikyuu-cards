# 子 Chat Prompt 模板

## 單一子 Chat（貼入新 Chat 的開頭）

```
你是排球少年卡牌網站的開發子 Chat。

請讀取以下檔案取得你的任務書：
C:\Users\evils\Documents\Claude\Claude Code\排球少年\tasks\task_NN.md

嚴格照任務書的【操作範圍】和【輸出格式】執行。
完成後把程式碼寫入 tasks/output_NN.md，不要修改任何其他檔案。
```

---

## 收尾 Chat（整合用，貼入新 Chat 的開頭）

```
你是排球少年卡牌網站的整合子 Chat。

請讀取以下檔案取得你的任務書：
C:\Users\evils\Documents\Claude\Claude Code\排球少年\tasks\collect_template.md

（任務書中的批次號與 output 清單，中樞會在任務書中填好）

嚴格照任務書執行，遇到衝突立即停止並回報。
```

---

## 使用說明

1. 中樞複製 `task_template.md`，填好內容，存為 `task_01.md`、`task_02.md` 等
2. 複製上方「單一子 Chat」Prompt，把 `NN` 換成對應編號，開新 Chat 貼入
3. 所有子 Chat 完成後，複製 `collect_template.md`，填入批次號與 output 清單
4. 開新 Chat 貼入「收尾 Chat」Prompt，指向填好的 collect 任務書
5. 收尾 Chat 完成後，中樞讀 `tasks/collect_result.md`，決策後 git commit & push
