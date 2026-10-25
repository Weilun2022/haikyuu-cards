---
status: accepted
---

# 再開一場用 per-match 節點隔離，不是原地清盤

同一個房間要能重開、換牌組，做法是把一場對戰的全部可變資料放在 `games/<room>/m/<matchId>/…`，房間層只留 `ctl`（誰在哪一場、重開協議進行到哪）、身分、presence。重開 = 先建立一個沒人引用的新場節點，再用 `ctl` 的單路徑 transaction 切換 `activeMatch`；舊場原封不動留著，不清、不刪。

## Context

專案沒有 RTDB rules（Firebase 專案是使用者自貼的），所以伺服器端沒辦法拒絕「舊世代的寫入」。對局裡有大量非同步寫入：去抖計數、確認框後才送出的動作、擲骰計時器、翻牌收尾計時器、SDK 離線佇列重放。原地清盤（同一組路徑清空重來）時，任何一筆晚到的舊寫入都會直接蓋到新場上。

## Considered Options

- **原地清盤 + `seq` 世代欄位**：只對控制節點做 transaction，無法同時原子清盤；改在整個對局根節點做 transaction 可以條件式清盤，但會和每個場內寫入競爭並下載整個 log。多路徑 `update` 則無法驗證取消與提交的先後。這些方法仍無法隔離清盤後才抵達的舊寫入，因此否決。
- **只靠呼叫端守衛（記 token，await 後比對）**：只擋得住「還沒發出」的寫入；已交給 SDK 的、離線佇列重放的都管不到，而且正確性取決於每個入口都有包到。保留成第二層防線，不當主要機制。
- **per-match 節點（採用）**：提交點是 `ctl` 單路徑 transaction，清盤不需要任何寫入；舊寫入落在舊場路徑，漏網也只是無效而不是污染；ADR 0006 的 `_firstSync` 風險在新場自然消失（新節點沒有舊的 `roundReset`）。

## Decision

- 新建房間一律 proto 2（`games/<room>/ctl.proto = 2`）。舊根佈局的房間繼續能玩，但不支援重開，不做熱遷移。
- `rooms/<room>.status` 用 `waiting2`／`ready`／`playing2`，讓已部署的舊版客戶端看不到也加不進新版房間；根層沒有 `started`，舊版觀戰者會被擋下。
- 所有場內寫入走 ctx（`createCtx`）。ctx 綁定房間、角色、場號；換場或離房就 `kill()`，之後經過它的寫入變成 no-op。流程的非同步續行另外用 `_roomLife`（房間生命週期憑證，離房／重進會變，換場不會）判斷自己是不是舊房間的流程——不能用 `cxLive(cx)`，因為提交成功時 listener 可能已經先把同房的 ctx 換成新場。
- 新場節點的 id 就是 requestId；準備用 transaction（已有內容就中止），提交用 `ctl` transaction（驗 request／phase／雙 ready）。提交沒成功時**不刪**自己準備的節點：transaction 中止回傳的快照可能是舊的，對方的提交可能同時成功。只在 `ctl` 已確定「req 不是它、activeMatch 也不是它」之後才清，因為 requestId 唯一，那時它再也不可能被提交。
- `ready`（值 = requestId）、`ack`（值 = matchId）是單欄位寫入，用值比對有效性；晚到的舊值不會被算進新一輪（每次邀請的 transaction 都會把 `ready`／`ack` 重置）。
- 本機先把「套用後」的完整 session 一次寫進 localStorage，成功才改本機狀態、切 ctx、ack。寫入失敗時 pending（已洗好的牌序）與鎖定原樣保留，修好後重試不重洗。
- 新版房間對局中的狀態是 `playing2`，不走舊版「`playing` 且 presence 全空就清房」的路徑，也不啟動 ADR 0002 的 60 秒雙離線清房；改用 `rooms/<room>.createdAt` 租約：房內玩家每 10 分鐘（及切回、重連、提交時）用 transaction 續租，大廳對 `playing2` 和舊版大廳對未知狀態一樣，30 分鐘沒人續租才清。這讓雙方切去卡牌資料庫改牌組、手機背景暫時離線時房間不會被立刻刪掉。
- 續租的 transaction 更新函式也檢查房間生命週期及房間紀錄是否仍存在，因為交易衝突可能在玩家離房後才重跑；只在呼叫 transaction 前檢查不足以阻止晚到的重試。
- 不依賴任何尚未查證的 Firebase 行為（例如 transaction 與一般寫入是否保序、transaction 內能否用 ServerValue 佔位符）。測試用 mock 把舊寫入扣在伺服器端路上、讓它在提交之後才落地。

## Consequences

- 路徑改了：ADR 0007 的 `peekNotif/<role>`、CONTEXT 的 `rallyLoss` 在新版房間都在 `m/<matchId>/` 底下；舊版房間不變。已接受的 ADR 內文不改寫，以此為準。
- `ctl` 的 transaction 依賴本機有 `ctl` 的快取（監聽一直開著）：快取為 null 時第一次執行會直接中止而不會問伺服器。`ctl` 監聽不可以在遊戲中被拿掉。
- 房間層的 `presence` 在 proto 2 不再自動清房，離開房間的人不會觸發清理；空房最多留 30 分鐘由大廳清掉。舊房維持原政策。
- 新增函式如果動牌或寫 Firebase，必須過 `guardAction()` 或列進 `tests/game-rematch-static.test.js` 的白名單並說明理由；手寫 `games/${room}/<場內欄位>` 路徑會讓同一個測試失敗。
- 歷史場節點不刪除（保留舊場 log，也避免「刪了又長出殘缺節點」）；只有自己準備、確定不會被提交的節點會被清。
