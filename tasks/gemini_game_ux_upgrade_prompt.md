# 給 Gemini：game.html 整體使用者體驗升級

> 使用方式：把這份文件整份貼給 Gemini，並**附上 `game.html` 全檔**（7,831 行，單檔 HTML+CSS+JS）。
> 若 Gemini 的上下文放不下全檔，至少附上：CSS 區（第 18–2590 行）、HTML 區（第 2592–3335 行）、`updatePhaseUI`／`renderBoard`／`fillSlot`／`renderHand`／手機觸控 IIFE（第 7348 行之後）。

---

## 你的角色與任務

你是資深遊戲 UI/UX 設計師兼前端工程師。請針對下方描述的網頁卡牌對戰遊戲 `game.html`，提出**整體使用者體驗升級方案**，並產出可直接套用的程式碼修改。

目標使用者：台灣的《排球少年!!》卡牌遊戲（バボカ!! BREAK，TAKARA TOMY）玩家，用這個網頁跟朋友線上對戰或練習。**一半以上在手機上玩**（iOS Safari／Android Chrome，直向），另一半在桌機。

---

## 一、產品概況

- **是什麼**：非官方同好自製的「線上桌面模擬器」。系統**不強制執行規則**——像實體桌遊一樣，玩家自己抽牌、出牌、移動卡、疊 Guts、調分數；系統只負責雙方即時同步、自動計算場上數值、記錄行動。
- **同站其他頁面**：`index.html`（卡牌資料庫＋牌組編輯器，玩家在這裡組 40 張牌組，存在 localStorage）。game.html 讀同一份 localStorage 牌組進場。
- **技術棧**：純原生 HTML/CSS/JS 單檔，無框架、無建置步驟。Firebase Realtime Database（compat SDK 10.12）做雙人同步。卡片資料來自 `cards_data.js`（全域 `CARDS_DATA.cards[]`），卡圖在 `images/{image_file}`（webp）。字體：系統字 + Google Fonts Bebas Neue。
- **語言**：介面全部繁體中文（zh-Hant），卡名/技能有中日對照。

### 卡片資料欄位（每張）
`card_no`、`image_file`（主鍵，含副檔名）、`name`／`name_zh`、`category`（`CHARACTER`／`EVENT`）、`school`、`position_zh`、數值 `srv`（發球）`blk`（攔網）`rcv`（接球）`tos`（舉球）`atk`（攻擊）、`skill_jp`／`skill_zh`、`annotation_zh`、`qa[]`（官方 Q&A）。

### 牌組規則（進場時驗證）
40 張整；EVENT 卡最多 8 張。

---

## 二、畫面流程（4 個 screen，`.screen.active` 切換）

1. **CONFIG**（`#screen-config`）：首次使用要玩家自己去 Firebase console 建專案、把 `firebaseConfig` JSON 貼進 textarea。存在 localStorage 後就不再出現。
2. **LOBBY**（`#screen-lobby`）：頭像選擇、玩家名稱、選牌組（下拉）、「建立新房間」／輸入 4 碼房號「加入」、未完成對局的「重新加入」橫幅、公開房間清單（即時，可加入或觀戰）、返回資料庫連結、免責聲明。
3. **WAITING**（`#screen-waiting`）：大字房號、QR code、複製邀請連結、房主/挑戰者兩張玩家卡（頭像/名稱/牌組/就緒狀態）、房主按「開始對戰 ▶」。
4. **GAME**（`#screen-game`）：主對戰畫面，見下節。另有觀戰模式（看不到雙方手牌，頂部紫色橫幅）。

進場時**每次都會自動彈出遊戲說明**（`setTimeout(showTutorial, 400)`）。

---

## 三、對戰畫面結構（桌機版）

```
┌───────────────────────── #turn-indicator（輪到誰）────────────────────────┐
│ #game-body                                                   │ #sidebar  │
│ ┌ #opp-area 對手 ─────────────────────────────────────────┐  │ 局數戰績   │
│ │ [牌組][棄牌]   攔網×3                         [SET]     │  │ （±按鈕）  │
│ │               攻擊 / 舉球 / 接球                          │  │ 手牌數量   │
│ │               事件 / 發球                                │  │ 攻擊值     │
│ └─────────────────────────────────────────────────────────┘  │ （±按鈕）  │
│ ─────────────────────── NET ───────────────────────          │ 工具：     │
│ ┌ #self-area 自己 ────────────────────────────────────────┐  │ 先攻後攻骰子│
│ │ [SET]          攔網×3                    [牌組]         │  │ 遊戲說明   │
│ │ [輸一球]       接球 / 舉球 / 攻擊          [🔀洗牌]      │  │ 重置本局   │
│ │               發球 / 事件                [棄牌]         │  │ 行動記錄log │
│ └─────────────────────────────────────────────────────────┘  │           │
├──────────────────────────────────────────────────────────────┴───────────┤
│ #hand-area：手牌｜手牌資訊｜↩復原｜⚡結束回合 END TURN                        │
└──────────────────────────────────────────────────────────────────────────┘
浮動：#guts-banner（Guts 模式）、#move-banner（移動模式）、#phase-flash
```

- **Zone（區域）**：`serve` 發球、`block` 攔網（唯一 3 格陣列）、`receive` 接球、`toss` 舉球、`attack` 攻擊、`event` 事件（可疊多張）、`drop` 棄牌、SET 池。對手區上下鏡像（攔網靠網）。
- 每格右側有直排數值 overlay（`.z-stat-overlay`）；角色卡底下可疊 **Guts**（卡片資源，`guts` 陣列），多張時水平堆疊（`.z-hstack-card`）。
- **Phase 主題色**：`PHASE_META` 依當前動作（發球 橘 `#fb923c`／攔網 藍 `#60a5fa`／接球 綠 `#4ade80`）用 JS 改 `--pc`、`--pc-bg` CSS 變數，整個畫面跟著換色。
- **攻擊警示**：對手結束回合時，其攻擊力閃爍顯示在對方場地；我方接球或攔網值達標後自動消失。

### 手機版（`@media (max-width:768px)` 與 `(pointer:coarse)`）
- 側邊欄隱藏，改成 36px **頂部列** `#mobile-topbar`（🏆組數 ⚡攻擊 🃏手牌 ＋輪到誰）＋右下 **FAB ☰** 開 **抽屜** `#mobile-drawer`（內容用 `cloneNode` 複製 sidebar，另有洗牌/復原快捷鍵）。
- 版面高度鎖死 `100svh`，禁止 pinch zoom（三層防護）。

---

## 四、核心操作

### 桌機
| 操作 | 方式 |
|---|---|
| 抽牌 | 點牌組格 / 按 `D` |
| 出牌 | 點手牌進選牌模式（高亮可放格）→ 點格；或拖曳到格子 |
| 手牌快速選單 | 右鍵手牌：移至場上 / 放回牌庫頂或底 / 棄牌 |
| 放回牌庫 | 拖到牌組格（上半=牌頂、下半=牌底）；選牌模式可多選一次放回 |
| 翻牌頂 N 張 | 右鍵牌組格 → `#peek-panel` |
| Guts | 右鍵場上角色 → Guts，或拖手牌到有角色的格子 |
| 查看棄牌 | 點棄牌格 → `#drop-overlay`，可撿回手牌或放到場上 |
| 卡片詳情 | 滑鼠 hover 出 `#card-hover`（490px 寬）；點擊開 `#detail-overlay`（中日文技能/Q&A），再點圖看大圖 |
| 結束回合 | 按鈕或 `Enter`；`Esc` 取消所有模式/關閉彈窗 |
| 復原 | 每回合最多 10 步，結束回合清空 |
| 分數 | 攻擊值大多自動計算（`calcBaseScore`），也有 ± 手動調；局數完全手動 ± |

### 手機（觸控，只在 `pointer:coarse` 綁定，不影響桌機）
| 目標 | tap | 拖曳 >8px | 長按 500ms |
|---|---|---|---|
| 手牌 `.hand-card` | 選牌（高亮可放格）→ 點格出牌 | 拖曳出牌 | 卡片詳情 |
| 牌組 `#pile-tile` | 抽牌；**有選牌時**左半=放牌頂、右半=放牌底 | — | 翻牌頂 N 張 |
| 棄牌格 | 有選牌時=直接棄掉（免確認）；否則開棄牌檢視 | — | — |
| 自己場上卡 | 進**兩段式移動模式** | — | 詳情 |
| 對手場上卡 | 詳情 | — | 詳情 |

**兩段式移動模式**：第一次 tap 自己卡 → 所有格亮起；點空格=直接放；點已占用格=該格顯示左「Guts」/右「角色」兩半提示，再點一次同格依左右半決定當 Guts 疊上或換位。

### 開局流程（目前全手動，說明頁列了 7 步）
擲骰決定先後攻 → 雙方各抽到 6 張 → **口頭討論**各要放回幾張 → 放回牌庫 → 洗牌 → 再抽到 6 張 → 先攻方點 SET 數字從牌庫頂補 2 張進 SET 池，開始第一回合。
**輸一球**：按「輸一球」→ 從牌庫補手牌到 6 張、再從 SET 池拿 1 張進手牌、自動結束回合。

### 彈窗清單
`#detail-overlay` 卡片詳情、`#img-lightbox` 大圖、`#hand-action-overlay` 手牌動作、`#msm-sheet` 移動目的地選單、`#peek-overlay` 翻牌頂、`#stack-overlay` 疊牌檢視/排序、`#drop-overlay` 棄牌區、`#place-confirm-overlay` 多張放置確認、`#gen-confirm-overlay` 通用確認、`#tutorial-overlay` 遊戲說明（兩分頁：流程/功能）、`#dice-overlay` 擲骰、`#disclaimer-overlay` 免責、`#ctx` 右鍵選單、`toast()` 提示。

---

## 五、目前我觀察到的 UX 痛點（供你參考，不限於此）

1. **新手門檻高**：CONFIG 畫面要玩家自己設 Firebase；開局 7 個手動步驟要靠讀說明＋口頭協調；說明每次進場都強制跳出（老手很煩）。
2. **狀態可見性不足**：「現在輪到誰、我該做什麼、這回合宣告了什麼動作、攻擊值是否已被擋下」分散在 turn-indicator、phase pill、sidebar、閃爍警示多處；手機頂部列只有 36px，資訊擠。
3. **手勢可發現性差**：長按、左右半邊點擊、兩段式移動、右鍵選單等都是「隱藏操作」，畫面上沒有提示，新玩家不知道能這樣做。
4. **回饋感弱**：出牌、得分、輸一球、換回合缺少動畫/音效/明確轉場；對手做了什麼只靠 log 與小通知。
5. **視覺一致性**：game.html 是獨立的深色紫色主題（`--accent:#6c63ff`），全站其他頁已改成「白底＋鮮橘＋紅」的新色票（`css/theme.css`、`css/components.css`）；檔內有約 65 個寫死色碼與 ~187 個 `rgba()`、大量 inline style 與 emoji 圖示。
6. **手動計分易錯**：局數、攻擊值都有 ± 按鈕，雙方都能按，容易誤觸或爭議。
7. **手機抽屜**把局數、手牌數、工具、log 全塞一起，翻找不便。

---

## 六、絕對不能破壞的既有決策（踩過的坑）

1. **禁止 pinch zoom 用三層防護**：viewport `maximum-scale=1.0`＋`html,body{touch-action:pan-x pan-y}`＋JS 在 document 層攔 iOS 的 `gesturestart`/`gesturechange`（`capture:true, passive:false`）。**不要改成 `touch-action:manipulation`**——它其實允許 pinch，是陷阱。也刻意不加 `user-scalable=no`（保留無障礙）。
2. **遊戲狀態變數是 module scope**（`dragData`、`moveMode`、`movePendingZone`、`L`、`gameState` 都用 `let`/`const` 宣告），**不要寫成 `window.xxx = …`**，會跟原變數脫鉤。`L` 是 `const`，只能改屬性。
3. **手機觸控只在 `matchMedia('(pointer:coarse)')` 時綁定**，桌機 hover/click/右鍵/拖曳行為獨立，改手機不能影響桌機，反之亦然。
4. **長按後 iOS 會補發一個合成 click**，現有 `_lpFired` 旗標＋window capture 階段 click 監聽會吞掉它；新增長按互動要沿用 `_lpStartAction` 框架。
5. **抽屜內容是 sidebar 的 cloneNode**，clone 時會移除子元素 id（避免 `getElementById` 抓到 clone）；改 sidebar 結構要確認抽屜仍正常同步（例如 log 用 class `.log-wrap` 同步）。
6. **斷線重連**：持久監聽 `.info/connected` 重設 presence；不要在 `visibilitychange` 加 presence 邏輯，也不要給房間加 `onDisconnect().remove()`（手機切背景會誤刪房間）。
7. **`_processedRoundReset` 首次同步對齊**（`listenGame` 的 `_firstSync`），否則進場會誤清手牌。
8. **Firebase 資料結構不要改**（`games/{id}/players/{host|guest}/zones`、`turn`、`setScore`、`scores`、`presence`、`log`、`roundReset`…），舊房間/對手可能還在用舊版頁面。
9. 卡片 key 一律是含副檔名的 `image_file`（例 `HV-P01-001-H.webp`）。
10. 卡圖網格**不要對大量重複元素用 `backdrop-filter`**，會讓手機閒置時 GPU 滿載、點卡卡頓。

---

## 七、限制

- 維持**純原生單檔**（不引入 React/Vue/Tailwind/建置工具）；可新增小型外部 CSS 檔（例如沿用 `css/theme.css`）。
- 不改遊戲規則邏輯（這是模擬器，不做自動裁判），除非你明確標示為「選配：半自動化」並說明風險。
- 手機觸控目標 ≥ 44px；文字對比度符合 WCAG AA。
- 必須同時支援桌機與手機直向（375px 寬起跳），手機版不能出現橫向捲動或畫面縮放。
- 版權聲明與免責聲明必須保留。

---

## 八、請你產出

1. **診斷**：逐畫面（Config／Lobby／Waiting／Game 桌機／Game 手機／各彈窗）列出 UX 問題，依「影響 × 修改成本」排優先序（P0/P1/P2）。
2. **升級方案**：每項給「問題 → 改法 → 預期效果 → 風險（是否碰到第六節的雷）」。至少涵蓋：新手引導與開局流程、回合/階段狀態呈現、手勢可發現性（教學提示/coach mark）、動作回饋與動畫、手機資訊架構（topbar/抽屜）、視覺主題統一方向。
3. **分批實作計畫**：拆成可各自獨立上線、獨立驗證的小批次（每批改動範圍明確、可回退），P0 先做。
4. **程式碼**：先只給 **第一批（P0）** 的實際修改，用「原始片段 → 修改後片段」的 diff 形式並標註大約行號／函式名，不要整檔重寫。
5. **驗證清單**：每批列出桌機與手機（iOS Safari）各要手動測哪些操作，特別是第六節列出的既有行為有沒有被破壞。

不確定的地方（例如某段程式碼你沒看到）請直接標「需確認」，不要猜。
