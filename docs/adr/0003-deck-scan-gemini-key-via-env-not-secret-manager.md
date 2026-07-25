---
status: accepted
---

# 牌組照片辨識的 Gemini API key 存在 functions/.env，不用 Firebase Secret Manager

`scanDeckPhoto` Cloud Function 讀 `process.env.GEMINI_API_KEY`（`functions/.env`，不進 git），沒有用 `firebase-functions/params` 的 `defineSecret`。

## Considered Options

- **Firebase Secret Manager**（`defineSecret`）：官方建議做法，key 加密存放、有存取記錄。但啟用 Secret Manager API 需要專案先升級到 Blaze（付費）方案，跟這個功能盡量留在免費 Spark 方案的目標衝突。
- **`.env` 環境變數**（現行）：一樣不會落地到前端、不進 git，安全性對個人專案規模足夠，且不需要升級付費方案。

## Consequences

如果之後這個 Firebase 專案因為別的需求無論如何都要升級 Blaze，應該重新評估改回 Secret Manager（加密存放/存取記錄對正式產品更穩健）。目前這個決定的前提是「盡量維持 Spark 免費方案」，前提改變時這個決定也該一起重新考慮。
