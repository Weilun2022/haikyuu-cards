# 對戰遊戲引擎（game.html）

即時連線的回合制卡牌對戰遊戲，用自貼的 Firebase 專案做雙方即時同步。跟「卡片目錄／牌組管理」context 是不同領域語言，只共用卡片基本資料，見根目錄 `CONTEXT-MAP.md` 的 Relationships。

## Language

**Zone（區域）**：
場上的一個卡片放置位置，共 8 種：`serve`（發球）、`block`（攔網，唯一是 3 格陣列，其餘皆單格）、`receive`（接球）、`toss`（舉球）、`attack`（攻擊）、`event`（事件）、`drop`（棄牌）、`set`（見下方 SET 條目）。

**SET**：
比賽局數/分數追蹤 tile，隨 rally（回合內的攻防交換）輸贏增減，輸一球會讓組數 -1 並自動結束回合。
_Avoid_: 不要跟「卡片目錄／牌組管理」context 的顏色標籤「舉球」（英文 key 剛好也是 `set`）搞混——兩者語意完全無關，這裡的「舉球」格子英文 key 是 `toss`，不是 `set`。

**GUTS**：
官方既有規則用語，卡片技能發動的資源/代價（例如「支付 3 Guts 後可發動」），存在每張場上卡的 `guts` 陣列裡。

**Turn（回合）**：
目前輪到誰操作，值是 `host` 或 `guest`。`endTurn()` 換人時同步更新。

**Action（當前動作）**：
目前這個回合的人宣告的單一動作（`currentAction` 欄位，值是 `serve`/`block`/`receive` 其中一個），由 `selectAction()` 設定、`endTurn()` 換人時清空。一個回合只會宣告一個動作，不是循環走過三個階段。

**Rally（官方排球規則概念，目前程式碼未明確建模）**：
發球到得分為止的一次連續攻防。**目前程式碼沒有把這個概念實作成獨立追蹤狀態**，只有「Turn」（誰的回合）跟「Action」（該回合宣告的單一動作），沒有任何邏輯偵測/標記「這一輪攻防到這裡算結束、算誰贏」。
_已知關聯_：`phase` 欄位（`serve`/`block`/`receive`）原本看起來像是要追蹤攻防階段循環，但查證後發現它只在遊戲開局被設成 `'serve'` 兩次，之後全程式碼再也沒有改過它，是個死欄位。**注意**：這個死欄位跟「rally 無限久」那個已知 bug **無關**——那個 bug 實際發生在 `game_engine/`（獨立的 Python AI 對戰模擬器，見下方「跟 game_engine/ 的關係」），不是這個瀏覽器對戰引擎；兩者只是剛好都用到「rally」這個字，曾經被誤連結過一次，特此註記避免以後又搞混。這個現況記錄在 [issue #54](https://github.com/Weilun2022/haikyuu-cards/issues/54)（要不要把 Rally 做成正式追蹤狀態尚未決定）。

## 輸一球後的補牌資格

任一玩家執行「輸一球」，這一場的 `rallyLoss`（新版房間在 `games/{roomId}/m/{matchId}/rallyLoss`，舊版房間在 `games/{roomId}/rallyLoss`）記錄 `{ id, role, roundReset }`，與輸球方的 SET 剩餘數及必要的換手狀態一起原子寫入。雙方各自取得補到六張的資格，直到自己下一次成功出牌；抽牌、棄牌與結束回合不消耗資格。此資格與開局教學獨立。

本機 session 保存資格與 `lastRallyLossId`，用來去除重複事件、補接離線期間的新事件；舊 session 先對齊歷史事件，避免重新授予已用掉的資格。事件帶有 `roundReset`，上一局的事件不能授予新局資格。復原只還原同一事件下的資格，不撤銷新一球取得的資格。

Firebase 會在寫入確認前發送本機事件，因此發起方用 `_pendingRallyLossId` 忽略自己的預先回呼，等伺服器確認後才移動卡片並取得資格；寫入失敗時維持卡片與資格原狀。對手端直接在同步時處理已收到的事件。請用兩個獨立瀏覽器頁面的 mock Firebase 驗證雙方連動，並涵蓋預先回呼後拒絕寫入的情況，不能只測單方函式。

## 再開一場／換牌組（房間、場、世代）

**Match（場）**：同一個房間內的一次完整對戰（比分、盤面、log、骰子、翻牌、輸一球事件都屬於它）。重開 = 同房間換一個新的場，房號、身分、presence 不動。
**Room 佈局有兩種**（`ctl.proto` 區分，新建的房間一律是 2）：

- **proto 2（新）**：`games/{room}/ctl`（`started`／`activeMatch`／`phase`／`req`／`ready`／`ack`／`epoch`／`rev`）、`games/{room}/players/{role}`（只有 name／avatar／deckName／ready）、`games/{room}/presence/{role}`、`games/{room}/m/{matchId}/…`（zones、handCount、pileCount、setCardsLeft、setScore、scores、counterDelta、turn、phase、log、roundReset、rallyLoss、diceRoll、peekNotif、peekReveal…）。`rooms/{room}` 的狀態用 `waiting2`／`ready`／`playing2`。
- **proto 1（舊）**：全部在 `games/{room}/` 根層，狀態 `waiting`／`ready`／`playing`。仍可正常對戰，**不支援再開一場**（工具列會提示雙方重新整理後重建房間）；它的 presence 清房政策沒有改。

**所有場內資料的寫入都走 ctx**（`GameRematch.createCtx`，`gx()`）：入口抓一份 ctx，之後的 `cx.ref(...)` 固定指向那一場。換場或離房就 `kill()`，沒送出的寫入變成 no-op；已經交給 SDK 的寫入落在舊場路徑，影響不到新場。不依賴 Firebase 是否保序。`tests/game-rematch-static.test.js` 禁止手寫 `games/${room}/<場內欄位>`。

**協議**（純邏輯在 `js/game-rematch.js`，接線在 game.html 的 REMATCH 區）：邀請（`ctl` transaction，`phase: inviting`，發起方 ready = requestId）→ 對手選自己的牌組，先把「已驗證、已洗牌的 40 張」存進 session（`pending`）才寫 `ready/{role} = requestId` → 任一方建立不可見的新場節點（`m/{requestId}`，已存在就不覆寫）並用 `ctl` 單路徑 transaction 驗證 request／phase／雙 ready 後切 `activeMatch`（`applyLocally=false`）→ 各端**先把套用後的完整 session 一次寫進 localStorage**，成功才改本機狀態、切 ctx／監聽、`ack/{role} = matchId` → 雙 ack 後 `phase` 回 `idle` 才解鎖。提交前任一方可取消／拒絕（也是 transaction，與提交互斥）；邀請 3 分鐘無人理會自動取消。

**鎖定**：從按下邀請那一刻（先於伺服器回應）到雙 ack 為止，所有會動牌或寫入的入口先過 `guardAction()`，不是只 disable 按鈕。進入鎖定時關掉確認框／翻牌／拖放暫態，並把 150ms 去抖中的張數立刻寫給舊場；`ready` 前要等已送出的寫入與進行中的動作落定（逾時就不 ready）。

**本機保存**（`hv_game_session`）：`appliedMatchId`、`deckSnapshot`（開局當下的原始牌組）、`pending`（對應某個 requestId、已洗好的牌庫）。重連時比對 `appliedMatchId` 與遠端 `activeMatch`：一致就還原手牌牌庫；對不上但有對應的 pending 就用它套用（不重洗）；沒有 pending 但新場剛提交就走「恢復選牌」；對不上又已不是套用階段就拒絕還原。`localStorage` 寫不進去不會假裝成功（不發邀請、不 ready、不套用）。

**房間存活（TTL）**：新版房間對局中的 `playing2` 不走舊版「`playing` 且 presence 全空就立刻清」的路徑，也不啟動 60 秒雙離線清房。房內玩家每 10 分鐘（以及切回、重連時）用 transaction 續租 `rooms/{room}.createdAt`；`rooms/{room}` 已不存在時續租會中止，不會長出幽靈房。雙方都離開超過 30 分鐘沒人續租，由大廳清理。

**已知相容限制**：舊版客戶端看不到也加不進新版房間（等待狀態是 `waiting2`、根層沒有 `started`）；舊版觀戰者無法觀戰新版房間；舊版房間不能重開；`ready`／`ack` 是單欄位寫入，以值（requestId／matchId）比對有效性而不是用 transaction；重開的歷史場節點保留在 `m/` 底下直到整個房間被清掉。

## 跟 game_engine/ 的關係

`game_engine/`（`ai`/`effects`/`engine` 子資料夾）是**獨立的 Python AI 對戰模擬器**，用來自動測試牌組強度，不是這個 context 的一部分、也不是 `game.html` 讀取或呼叫的東西。它有自己一套已知問題待修清單（例如模擬對戰裡 rally 可能因為棄牌堆一直洗回牌庫而打不完），目前擱置不處理，且**跟這裡的瀏覽器對戰引擎完全無關**，不要因為兩邊都出現「rally」字樣就互相牽連。

## docs/adr/

- [0001](docs/adr/0001-mobile-pinch-zoom-three-layer-lock.md) — 手機 pinch zoom 鎖定用三層防護，touch-action:manipulation 是陷阱不是解法
- [0002](docs/adr/0002-mobile-reconnect-persistent-presence-watcher.md) — 手機斷線重連改用持久 presence watcher
- [0003](docs/adr/0003-module-scope-state-not-window.md) — 遊戲狀態變數用 module-scope，不掛在 window 上
- [0004](docs/adr/0004-fab-drawer-clone-node.md) — 手機版側邊欄用 cloneNode 複製，不是重寫一份
- [0005](docs/adr/0005-two-stage-move-mode.md) — 手機版移動卡片用兩段式 tap
- [0006](docs/adr/0006-processed-round-reset-first-sync-guard.md) — _processedRoundReset 用 _firstSync 旗標對齊，避免進場誤清手牌
- [0007](docs/adr/0007-peek-sync-per-role-node.md) — 翻牌頂同步節點以角色分流，刻意捨棄舊分頁相容性
- [0008](docs/adr/0008-per-match-node-rematch.md) — 重開用 per-match 節點隔離，而不是原地清盤
