---
status: accepted
---

# 大廳依 presence 隱藏雙離線對局，過期清理改成定時＋墓碑交易

issue #114：雙方直接關掉分頁（或都按離開）後，大廳一直列著那場「對戰中」。原因有三：大廳只監聽 `rooms`，對 `playing2` 不看 presence；30 分鐘過期清理只在 `rooms` 有事件時才跑，沒有其他房間變動就永遠不清；對局中離房只刪自己的 presence，`rooms` 沒有任何變化。

本 ADR 補充 [0008](0008-per-match-node-rematch.md) 的「房間存活（TTL）」與 [0002](0002-mobile-reconnect-persistent-presence-watcher.md) 結尾列的清房路徑，不改寫它們的決策：30 分鐘租約、每 10 分鐘與切回／重連續租、`playing2` 不因暫時雙離線就刪房，全部維持。

## Decision

- **顯示與資料分開**：`playing2` 房間大廳另外監聽 `games/<room>/presence/host`、`presence/guest`。兩個都讀到且都不在線才不列出；資料照租約保留，任一方回來就重新列出（presence 變動就重繪，不等 `rooms` 事件）。還沒讀到是「未知」，照常列出，不從缺資料推斷離線、也不為了推斷寫任何東西。觀戰者不寫 presence，本來就不算。
- 監聽子路徑而不是 `presence` 本身：房內玩家的 `listenGame` 監聽 `presence`，而 `ref.off()` 不帶 callback 會拿掉同一路徑上所有監聽，路徑分開兩邊才不會互相拔掉。大廳一律用 `off('value', cb)` 解除。
- **定時清理**：大廳每 60 秒（`LOBBY_SWEEP_MS`）與頁面切回前景時掃一次，`rooms` 事件也照常觸發。自己所在的房間（非觀戰）略過——自己是續租的一方。過期門檻不變：`playing` 4 小時，其他 30 分鐘。已過期但還沒清掉的房間不列出。
- **墓碑清理（`reapRoom`）**，取代「拿快照直接 remove rooms 再 remove games」：
  1. **先決定身分**（在認領之前）：新版房間用 `inst`——建房時寫進 `rooms/<id>` 與 `games/<id>` 的房間實例 id（第一場的 push key），房號會重用、`inst` 不會。沒有 `inst` 的舊版 proto 2 房間，讀 `games/<id>/ctl.activeMatch` 當**見證**：它是 `m/` 底下唯一的 push key，已啟用的場節點不刪、重開後仍在。舊根佈局房間沒有可靠的唯一見證，身分**未知**。缺值一律不當成身分相等。
  2. **認領**：`rooms/<id>` transaction，最新值必須與讀見證「之前」看到的房間紀錄完全相同（`createdAt` 是伺服器時間，之後的新房不會相同）且仍過期，才換成 `{ id, status: 'reaping', createdAt, inst | witness }`。所以見證的讀取就算晚到、讀到同房號的新房，認領也會失敗。墓碑不能加入（只認等待狀態）、續租會中止（`touchRoomLease` 排除 `reaping`），也佔住房號，`createRoom` 不會挑到它。
  3. `games/<id>` transaction：`inst` 相同，或沒有 `inst` 且見證的場節點仍在，才刪。身分未知不刪 games（保守留下沒有入口的舊資料，不誤刪別人的房）。
  4. `rooms/<id>` transaction：仍是同一個墓碑（狀態、id、原 `createdAt`、身分欄位相同）才刪。只比墓碑自己的欄位，因為既有的單欄位寫入（重開後的 `rooms/<id>/deckName` 等）可能落在墓碑上。
  每一步都可重複執行；失敗就留著墓碑。接手別人的墓碑沿用墓碑記下的身分，不重新讀現在的 games。別人留下的墓碑，本機看到超過 `ROOM_REAP_TAKEOVER_MS`（15 秒，以本機看到的時間計，不比對寫墓碑那台的時鐘）還在就接手。
- 不對 `rooms`／`games` 整個集合或資料庫根做 transaction，只鎖單一房間的兩個節點；不依賴 transaction 與一般寫入是否保序。本機沒快取時 transaction 第一次拿 null 執行：games 那步回傳 null（伺服器其實有資料會駁回並用真值重跑），rooms 那步中止；中止時回傳的快照可能是舊的本機值，拿它接手也只會走到由伺服器驗證身分的兩個 transaction。
- 舊版 `playing` 房間的 presence 清房路徑（`rooms` 事件時讀 presence，雙空就刪）原樣保留。

## Considered Options

- **雙離線時直接刪房**：違反 0008——手機背景、切去改牌組是正常的暫時雙離線，重連要能回來。
- **只加計時器，沿用快照 remove**：大廳判斷過期後、刪除送達前房主剛好續租，房間會被刪；或自己的刪除晚到時，房號已被新房重用，刪掉別人的新房。
- **不用墓碑，先 transaction 刪 rooms 再刪 games**：刪完 rooms 就當機的話 games 變成沒有入口的孤兒，再也沒人清。墓碑讓中斷可接手。
- **只用墓碑，不驗身分**：多個大廳同時接手時，某一個的 games 刪除可能在墓碑已被別人移除、房號被新房重用之後才抵達；只有能辨識房間實例的條件式刪除擋得住任意延遲。
- **把缺 `inst` 當成相同身分**（本 ADR 第一版的做法，Codex 審查以 mock 重現後否決）：兩間都由舊版客戶端建立的房間都沒有 `inst`，晚到的刪除會把同房號的新房 games 刪掉。
- **刪 games 前再讀一次 rooms**：兩個節點之間沒有原子性，讀完到刪之間仍可能換房。

## Consequences

- 新建房間多一個 `inst` 欄位（`rooms/<id>.inst`、`games/<id>/inst`）。修正前建立的 proto 2 房間改用見證；舊根佈局房間過期時只清 `rooms` 紀錄，`games/<id>` 留著（之後同房號建房會整個覆寫）。
- **這不保證所有舊客戶端的清理都沒有競態**：已部署的舊版大廳仍用快照直接 remove（含過期清理，以及舊版 `playing` 雙離線時讀 presence 就刪的路徑，後者本次刻意不動）；舊版大廳看到 `reaping` 會當成未知狀態以 30 分鐘過期直接刪；舊版的續租不認得墓碑，可能改到它的 `createdAt`，墓碑因此對不上時會留到下一次掃描以新快照重新認領。
- 既有的單欄位寫入（`rooms/<id>/status`、重開後的 `rooms/<id>/deckName`、等待中的 guest `onDisconnect`）在房間被清掉後才落地，會留下缺欄位的殘骸紀錄；它沒有 `createdAt` 而被視為過期，身分未知，只清 `rooms` 紀錄、不碰 games。本次沒有改這些寫入。
- 見證的前提是「已啟用的場節點不會被刪」。審查時發現 `sweepPreparedMatches()` 不會把已提交的 requestId 從 `_rmPrepared` 移除，同一頁再重開一次後可能刪掉那個歷史場節點（與 0008「歷史場節點不刪除」不符，另案處理）。對清理而言是安全側失敗：見證消失時 games 不刪，只留下舊資料。
- 雙方都確定離線時，旁人看不到也無法從清單觀戰該局（觀戰本來就看不到東西在動）；回來的玩家用「重新加入」，不依賴清單。
- 等待中超過 30 分鐘的房間現在會準時被清（以前要等別的房間有變動），門檻本身沒變。
- 測試：`tests/game-lobby-lifecycle.test.js`（多頁 mock：關頁隱藏、單方在線、重連顯示、觀戰不算、計時清除、未過期不清、續租競爭、墓碑擋加入／續租／重用、晚到回覆不刪新房、接手、無 `inst` 舊房晚到刪除、見證讀取晚到、冷快取、舊根佈局不刪 games、無 `inst` 跨重開、監聽不累積、手機背景）；`tests/game-rematch-static.test.js` 檢查清理只用 transaction、不以缺值當身分相等、續租排除墓碑。
