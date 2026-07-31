# 排球少年!! バボカ!!BREAK 卡牌資料庫

開發文件散落在各個 context 自己的 `CONTEXT.md`（見根目錄 `CONTEXT-MAP.md`）。這裡只收「怎麼跑本地開發工具」這類跨 context 的操作說明。

## Firestore emulator 本地測試

**這是本地 emulator，不會碰正式的 `haikyuu-cards-cloud` Firebase 專案**，可以放心寫入/清空測試資料。

啟動 emulator（只開 Firestore，不需要登入任何真實 Firebase 帳號）：

```bash
firebase emulators:start --only firestore
```

啟動後可在 http://127.0.0.1:4000 開 Emulator UI 檢視資料，Firestore 本身監聽 `127.0.0.1:8080`（設定見根目錄 `firebase.json` 的 `emulators` 區塊）。目前的 `firestore.rules` 是刻意寬鬆的最小可跑版本（允許所有讀寫），只用來驗證 emulator 環境本身，不是正式規則。

跑範例測試（`functions/firestore-emulator-smoke.js`：寫入一筆資料、讀回驗證内容相符），需要在 emulator 環境內執行：

```bash
firebase emulators:exec --only firestore "npm --prefix functions run test:emulator"
```

`firebase emulators:exec` 會自動啟動 emulator、注入對應的環境變數、跑完指定指令後自動關閉 emulator，不用手動先 `emulators:start` 再另開一個終端機跑測試。

之後要幫 Firestore 安全規則本身寫測試（例如驗證白名單/寫入上限），或整合牌組雲端同步的測試，都可以照 `functions/firestore-emulator-smoke.js` 的寫法（`@firebase/rules-unit-testing` 的 `initializeTestEnvironment`）延伸，不需要重新摸索怎麼接上 emulator。

**注意**：Firestore emulator 需要本機安裝 Java（JRE 11+）才能啟動，`firebase-tools` 本身不含 JRE。
