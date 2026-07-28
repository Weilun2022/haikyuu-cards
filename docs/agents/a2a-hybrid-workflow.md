# A2A 協作(Pocock 混合模式)

在 `/grilling`(或 `/grill-with-docs`)、`/to-spec`、`/to-tickets` 這幾個關卡被使用者觸發之後，用 A2A(Agent2Agent 協議)工具讓 Claude 跟一個獨立的 GPT 模型自主收斂決策，取代逐題問使用者。原始設計文件來源：[a2a-collab-poc/docs/pocock-a2a-hybrid-workflow.md](https://github.com/Weilun2022/a2a-collab-poc/blob/main/docs/pocock-a2a-hybrid-workflow.md)。

## 本機工具位置

- 工具原始碼：`~/.claude/tools/a2a-collab-poc`(clone 自 [Weilun2022/a2a-collab-poc](https://github.com/Weilun2022/a2a-collab-poc)）
- 執行環境：獨立 venv，`~/.claude/tools/a2a-collab-poc/.venv` — **只給這個工具用，不要跟其他 Python 工具共用環境**（這條是踩過坑才定的：曾經誤用系統 `python` 裝套件，結果動到另一個不相干系統 hermes-agent 共用的套件版本，導致其環境被破壞）。之後任何要更新這個工具依賴的操作，一律針對這個 `.venv`，不要對系統 `python`/其他共用環境下 `pip install`。
- 呼叫入口：`~/.claude/tools/a2a-ask/ask_openrouter.ps1`（PowerShell 包裝腳本，故意放在 repo 外面，不隨 repo 更新而變動）

```powershell
~/.claude/tools/a2a-ask/ask_openrouter.ps1 -Prompt "your question" [-Model "openai/gpt-5.6-luna"] [-System "system prompt"]
~/.claude/tools/a2a-ask/ask_openrouter.ps1 -PromptFile "C:\path\to\long-prompt.txt"
```

- `-Prompt` 帶多行/特殊符號/超過 200 字元的內容會被擋下，改用 `-PromptFile`（先寫成 UTF-8 暫存檔）。
- 這是「一次性問答」模式，只啟動 OpenRouter 端。**辯論模式**（`common/debate_coordinator.py` 的 `run_debate_session()`，真正多輪雙向、OpenRouter 端可反問 Claude）目前只能直接寫 Python 呼叫，沒有 CLI 包裝——見 repo README 的用法範例。

## 核心規則

1. **改成 Claude↔GPT 自主討論收斂，不逐題問使用者。** Claude 仍然負責探索程式碼、蒐集事實、做出實際決策/取捨；GPT（透過 A2A）扮演對這些決策施壓的角色。「一問一答收斂」這個迴圈跑在 Claude 與 GPT 之間，不是 Claude 與使用者之間。
2. **使用者的 slash command 關卡不變。** Claude 仍然不能自己觸發 `/grilling`/`/to-spec`/`/to-tickets`/`/implement`——這些指令必須由使用者親自打。改變的只是「關卡打開之後、裡面怎麼跑」。
3. **遇到只有使用者才知道答案的業務/情境判斷**（不是 GPT 能幫忙解決的技術分歧），**用最合理的猜測繼續走，不中斷 loop**，但在最後總結裡明確標出「這點是用猜的」。真的卡死、猜不出合理答案才中斷詢問使用者。
4. **`/implement` 前，只給使用者看一次白話文總結**：涵蓋 grilling/spec/tickets 全程決議的關鍵決策、理由，以及哪些地方是用猜的（要明確標出）。使用者看的是這一份總結，不是每個關卡的原始討論記錄。滿意後才打 `/implement`——這之後的實作、`/code-review` 流程完全不變。

## 下 prompt 的原則

對 A2A 下 prompt 要刻意要求「唱反調」（`ask_openrouter.py` 沒指定 `-System` 時會自動套用懷疑資深工程師的預設 system prompt），不要問「你同意嗎」這種誘導同意的問法；同時要求精簡（不要情緒鋪陳開場、同根因問題合併列），否則回覆會有贅詞降低訊噪比。

## 什麼時候不適用

- 純技術性、範圍明確的單點決策：適合拿來壓力測試。
- 真正的實測/驗證類問題（例如「這功能在真實瀏覽器裡到底跑不跑得動」）：A2A 沒有能力驗證，不該當作驗證手段的替代品，還是要實際跑。

## 與舊工具的關係

原本的 `web-collab` skill（`reviewer.js`，呼叫 GPT-5.6-Luna/Gemini 的舊機制）已停用，統一改走這套 A2A 工具。
