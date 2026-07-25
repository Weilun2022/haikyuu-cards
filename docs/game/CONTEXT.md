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

## 跟 game_engine/ 的關係

`game_engine/`（`ai`/`effects`/`engine` 子資料夾）是**獨立的 Python AI 對戰模擬器**，用來自動測試牌組強度，不是這個 context 的一部分、也不是 `game.html` 讀取或呼叫的東西。它有自己一套已知問題待修清單（例如模擬對戰裡 rally 可能因為棄牌堆一直洗回牌庫而打不完），目前擱置不處理，且**跟這裡的瀏覽器對戰引擎完全無關**，不要因為兩邊都出現「rally」字樣就互相牽連。

## docs/adr/

- [0001](docs/adr/0001-mobile-pinch-zoom-three-layer-lock.md) — 手機 pinch zoom 鎖定用三層防護，touch-action:manipulation 是陷阱不是解法
- [0002](docs/adr/0002-mobile-reconnect-persistent-presence-watcher.md) — 手機斷線重連改用持久 presence watcher
- [0003](docs/adr/0003-module-scope-state-not-window.md) — 遊戲狀態變數用 module-scope，不掛在 window 上
- [0004](docs/adr/0004-fab-drawer-clone-node.md) — 手機版側邊欄用 cloneNode 複製，不是重寫一份
- [0005](docs/adr/0005-two-stage-move-mode.md) — 手機版移動卡片用兩段式 tap
- [0006](docs/adr/0006-processed-round-reset-first-sync-guard.md) — _processedRoundReset 用 _firstSync 旗標對齊，避免進場誤清手牌
