# 開發日誌

---

## 2026-07-14（Session 27）

### 牌組管理：修正依顏色排序時事件牌未排最底部（`76b545f`）

**Bug 根因**
- 三處「依顏色排序」邏輯（`buildColorModeSlots` 上色模式格子排序 / `applyBatchColor` 套色後排序 / `reorganizeDeck('color')` 整理功能）都把事件牌排在「未上色」角色卡**之前**（事件＝第4組、無色＝第5組），本意應該是事件牌永遠排最後
- 這個排序值從最早的整理功能（`4a11ffe`，4/13）就是這樣寫，4月的上色系統重構（`906d105`）延續了同樣的值；4月改版後角色卡更容易停在「未上色」狀態，才讓問題變明顯——牌組裡只要有沒上色的角色卡，事件牌就會卡在中間而非最底部
- 修法：統一改成「有色角色卡 → 無色角色卡 → 事件牌」，事件牌固定排最後
- 用瀏覽器內注入假牌組資料測試三個排序函式，確認排序符合預期後清除測試牌組

### index.html / promo.html：修正 App 關閉重開後卡在舊頁面（`2a1628c`）

**問題**：使用者關閉整個 Chrome App 再重開，之前開過的分頁還是顯示前一版舊介面

**根因**（與 GPT-5.6-Luna 兩輪根因複審確認）
- GitHub Pages 對 HTML 回應 `Cache-Control: max-age=600`，無法自訂 header
- 早上加的版本偵測機制（`1a57c43`）只在 `pageshow(persisted)`（bfcache 還原）或 `visibilitychange→visible`（分頁切回前景）時才比對＋強制 reload
- 「關閉整個 App 再重開、用『繼續瀏覽』還原分頁」是全新 top-level navigation（非 bfcache），且分頁一開始就是前景不會觸發 `visibilitychange`，所以只會跑到「一般載入」分支——該分支原本拿到伺服器最新 tag 後**無條件覆寫 sessionStorage、不比對**，等於把「畫面其實是舊版」的 session 誤標成「已是最新」，之後同 session 內所有比對都會誤判通過，永久卡住
- GPT 提醒：sessionStorage 能否撐過整個瀏覽器 App 關閉重開本來就沒有保證，用「上次查到的伺服器版本」當比對基準這個設計本身就不可靠

**修法**：改用 `document.lastModified`（目前畫面上這份 HTML 實際的版本時間，即使是磁碟快取吐出來的舊頁面也一樣準）取代 sessionStorage 當比對基準，每次載入都直接跟伺服器當下 `Last-Modified` 比對，不依賴任何跨 session 儲存；一般載入也會檢查（不再只靠 bfcache/visibilitychange 觸發），並加上 5 分鐘定時輪詢補強前景長駐情境
- GPT 複審第二輪抓到：無 reload 上限可能演變成無限迴圈、fetch 沒有 timeout 會讓 `checking` 鎖死、沒檢查 `res.ok` — 三點都已補上（每 session 最多自動 reload 一次、6 秒 fetch timeout、檢查 res.ok）
- 兩檔案已在瀏覽器內驗證 `document.lastModified` 與伺服器 `Last-Modified` 正確對應、比對邏輯無誤、無 console 錯誤

---


### game.html：大廳桌面版佈局調整（`a0788e5`、`d663b4a`）

**操作列對齊修正**
- 將 lobby-actions（建立新房間 + 房號 + 加入）移入玩家設定卡片內，頂部加分隔線，消除左右突出問題
- 移除 join-row 嵌套包裝，改為三個元素直接 `flex:1` 均分，解決「加入」按鈕歪出去的問題
- 三物件各佔約 178px，全收在卡片邊界內

**桌面版雙欄嘗試（已放棄）**
- 嘗試 `@media (min-width:900px)` grid 雙欄（左玩家設定、右房間列表），多次修正後決定維持原始單欄佈局

---

## 2026-06-21（Session 25）

### game.html：手牌殘留修復 + 等待畫面手機版優化（`97cc015`）

**Bug fix — 加入新局後手牌未清空**
- `enterGame()` 在 `L.hand = []` 後補上 `renderHand()` 呼叫
- 根因：資料清了但 DOM 未同步，導致上一局卡片殘留顯示
- 六方 AI 共識確認（Grok / Gemini / 混元 / DeepSeek / MiniMax / MiMo）

**手機版等待畫面優化（Gemini 設計 R25）**
- 新增 `@media (max-width:768px)` CSS 覆寫等待畫面
- `.waiting-box` padding 40→20px、`.room-code-big` 64→48px、letter-spacing 縮減
- QR Code 說明文字隱藏、canvas 縮至 80px、`.waiting-players` margin 縮半
- 「開始對戰」按鈕確認在手機視口內可見（按鈕底部 665px，視口 812px）

---

## 2026-05-07（Session 12）

### game.html：版面 CYBER 風格化 + 效能優化

**版面修正（`538e066`）**
- 我方面板恢復原始順序：SET 左、牌組+棄牌 右（對方維持鏡像：牌組+棄牌 左、SET 右）
- 場地底色移除橘色（`#7a3a00`），改為深暗 `#040810` + 藍色 CSS grid 線

**CYBER 螢光風格（`538e066`）**
- 全區域改為半透明暗底 + 螢光邊框 + 外發光（各色對應：藍/綠/紅/金/青）
- EVENT 區改為 cyan（原為灰色）
- `::before` 改為掃描線漸層 + `neonGlow` pulse 動畫
- `::after` 標籤字色改為各區螢光色 + text-shadow 發光
- Hover 狀態加強發光強度

**UX 小修（`c75505c`）**
- 左上角「思考中」badge 隱藏（`#turn-indicator { display:none }`）
- 結束回合按鈕加寬：`min-width` 96px → 140px，`padding` 18px → 32px

**頭像替換（`eccbca1`）**
- AVATARS 陣列改為排球少年吉祥物：🦅🐦🦉🐱🦊🕊️🛡️🌲🐍🦝🦦
- 大廳 hero icon 及所有 avatar fallback 由 🏐 改為 🦅

**renderHand diff 更新（`bb3f697`）**
- 抽出 `makeHandCard(img, idx)`，event listener 改讀 `+div.dataset.idx`（不再 close over idx）
- `renderHand()` 改為 pool-based diff：以 `dataset.img` 為 key 重用現有節點，`insertBefore` 對齊順序，只在空↔非空切換時才 `innerHTML=''`

**效能優化（`e4ddf4c`）**
- `syncPileCount()`/`syncHandCount()`：加 150ms debounce（pure display 值，15+ 呼叫點減少 Firebase 連發寫入）
- `_posCardHover()`：改用 `requestAnimationFrame` throttle，快照 clientX/Y 避免 event 物件過期
- `fillSlot()`：加 bail-early cache（`dataset.fillKey`），每次 Firebase sync 不重繪未變化格子；drag-state class（target/guts-target）仍每次清除

---

## 2026-05-07（Session 11）

### game.html：點擊直覺化 + 重置 bug 修正（`f8a2755`）

**點擊任意位置放牌到最上層**
- `fillSlot` 的 `slot.onclick` 原本有 `if (e.target === slot)` 守衛，導致只能點到最上方那張卡才能放置
- 修法：將 `gutsHandIdx / moveMode / selectedHandIdx` 三個「主動放置」判斷移出守衛，讓 slot 內任意點擊都能觸發
- `onZoneClick`（進入移動模式）仍保留 `if (e.target !== slot) return` 限制，避免點卡片重複觸發

**重置 bug 三項修正**
1. **`rejoinRoom()` 重複 listener**：加 `if (gameRef) gameRef.off()` 拆除舊監聽器，避免每次重連疊加一個 `onValue` callback
2. **`rejoinRoom()` 觸發舊 roundReset**：重連後立即讀 Firebase 快照中的 `roundReset` 設定 `_processedRoundReset`，防止重整頁面後 `handleRoundReset` 意外把手牌掃回牌庫
3. **`L.setPool` 重置時未收回**：`declareLost()` 與 `handleRoundReset()` 兩處都加入 `L.pile.push(...L.setPool)`，並清空 `L.setPool`、重設組數顯示為 0 及同步 Firebase `setCardsLeft`

---

## 2026-04-25（Session 8）

### game.html：場上牌操作擴充
- **放回牌堆（上方/下方）**（`22ced75`）：`returnToPile()` 函式；場上牌選單新增「放回牌堆（上方）」「放回牌堆（下方）」按鈕；棄牌區整合進選單（`addBtn('→ 棄牌區', ...)`），`ha-discard-btn` 在 showZoneAction 時隱藏
- **疊牌方向修正 + 棄牌按鈕 bug 修正**（`cea9e3a`）：
  - `fillSlot` 改為 `[cardData.img, ...guts.slice().reverse()]`，top card 顯示在最左，guts 向右延伸；套用遞減 z-index 讓 top card 視覺最上層
  - `showHandAction` 開頭重設 `ha-discard-btn.style.display = ''`，避免前一次 showZoneAction 隱藏按鈕後殘留

---

## 2026-04-24（Session 7）

### DECK-BODY 縮圖格 + PREVIEW 浮動（本 session 前段延續）
- 桌機版牌組面板 `max-width: 540px` 置中（`6ec81cb`）
  - 根因：`align-items: stretch` 與 `margin: auto` 衝突，改用 `align-self: center`（`133c71b`）
  - preview float 和 deck panel 在桌機皆置中 540px、固定底部

### 庫存分析升級（`bf8b6d3`）
- badge 由 `×N`（需求數）改為**缺 N 張**（deficit），已完成顯示 `✓`
- 依缺張數降冪排序（缺最多排最前）
- 分兩 section 顯示：「未完成（N張）」/ 「已完成（N張）」，section 為空時不顯示
- `saveAnCount` 同步即時更新 badge，不需重新渲染整頁
- 子 Chat task_10 負責實作

---

## 2026-04-17（Session 6）

### 翻譯回報機制上線
- **Modal 加入「🚩 回報翻譯問題」按鈕**：點擊開新分頁到 GitHub Issue 新建頁，自動帶入卡號、卡名、當前技能文字，使用者只需填「建議翻譯」即可送出。`0beb45b`
- **GitHub Issue 模板**：`.github/ISSUE_TEMPLATE/translation.md` 建立，供從 Issues 頁面手動建立時套用。
- **`translation` label 建立**：玩家回報的 issue 自動打標籤，中樞可用 `gh issue list --label translation` 批次處理。
- **測試驗證**：Issue #3 格式正確，label 自動套上 ✅

**後續操作**（未來）：說「處理翻譯 issue」，我會批次讀取所有 `translation` open issue → 修 cards_data.js → commit → close issue。

---

## 2026-04-17（Session 5）

### Mobile UI 優化
- **下方 Deck Tray 滾動隱藏/顯示**：mobile 向下滾動時 tray 同步上方列收起，向上滾動恢復。`bb90925`
- **Modal QA 預設展開**：有 QA 資料時直接展開，不需點擊 toggle。`e98e561`
- **卡片縮圖屬性順序統一**：grid 從 `atk/blk/rcv/tos/srv` 改為 `srv/blk/rcv/tos/atk`，與 Modal 一致。`e98e561`
- **Mobile Modal 版面改為左右排版**：圖片靠左 25% 寬、資訊占右 75%，避免圖片吃掉太多版面導致文字看不到；加放大圖示提示（右下角放大鏡 icon）。`7e061e1` `02dcd69` `6df7138` `875f36c`

### 討論 / 未實作
- **自動收錄最新賽場牌組**：調查可用資料來源
  - 最佳：**Card Labo**（`c-labo.jp/recipe/` + `tournament/`）結構化 HTML，週頻爬取
  - 輔助：Note.com 社群文章、官方 X（@haikyu_vobaca）
  - 結論：目前沒有集中牌組資料庫，遊戲 2025/10 才重售，社群仍在成長；建議半自動（爬取 → 轉匯入格式 → 人工確認一鍵匯入）
  - 未動工

---

## 2026-04-16（Session 4）

### 快速查詢 / 庫存分析
- **快速查詢改名另存功能**：在快速查詢按改名，以輸入名稱建立新牌組，複製所有牌後清空快速查詢並切換到新牌組。`78fe986`
- **庫存分析卡片標示改為卡號**：由「牌名 (variant)」改為「卡號-variant」（與輸出圖片格式一致）。`1a9bf1f`

---

## 2026-04-16（Session 3）

### 按鈕 UI 修正
- **QR Code / 牌組轉圖片按鈕去除紫色背景**：移除 `deck-share-btn` 和 `deck-export-img-btn` 的 `primary` class，外觀統一為透明背景邊框樣式。
- **清空牌組後星號標記未刷新 BUG 修正**。

---

## 2026-04-16（Session 2）

### 翻譯強化 v1.0
依據 rules_general_v1.03.pdf（47頁規則書）全面審計翻譯品質。`600e280`

**POSITION_ZH 補齊（7張卡站位中文化）：**
- 元監督→前任教練、応援団→啦啦隊、応援団長→啦啦隊長、マスコット→吉祥物、OH→主攻手

**translate_skill 新增：**
- エンドフェイズ → 結束階段（tag_map + area_map）

**clean_qa_text Section 12（317筆 QA 術語一致性強化，30+ 誤譯模式）：**
- 技能標記：`[=外觀]`/`[=出現]`→`[=登場]`；`[=封鎖(N)]`→`[=攔網出界(N)]`；`[=拋球]`→`[=舉球]`；`[=法庭]`→`[=場地]`；`[=投擲範圍]`→`[=舉球區]`；`[=攻擊範圍]`→`[=攻擊區]`
- 區域名稱：投擲區/投球區/拋球區→舉球區；封鎖區域→攔網區；廢棄區/掉落區→棄牌區；接收區→接球區；進攻區→攻擊區；宮廷/法庭→場地
- 角色類型：投擲角色→舉球角色；接收角色→接球角色；接收階段→接球階段；服務角色→發球角色；擲球階段→舉球階段；投擲點/拋球點→舉球值
- 攔網術語：中路攔網者/中路攔網手/中央攔網者/中心攔網者/中攔網者→中間攔網手；側阻止符/側面攔網者→側翼攔網手
- 數值：攻擊力→攻擊值；防禦點→防守值；值數→值
- 其他：格斯/內臟→Guts；宣告失敗→宣告失分；蓋放→覆蓋；卡片名稱→牌名；刪除→棄置；出現→出場；另一個「X」→另一張「X」

---

## 2026-04-16（Session 1）

### 庫存分析 UI 優化
- **未入手去灰化**：`not-owned` 狀態從灰化（grayscale + opacity）改為橘色邊框，方便查看牌組內容與技能。`8505cec`
- **右下角需求張數 badge**：卡片右下角顯示 `×N`（牌組需求張數），左上角 input 維持持有數，讓使用者一眼掌握缺張狀況。`adea2cf`

### 分享 QR Code 重構
- 全螢幕 QR Code 設計、修復顯示問題。`c73f569`
- 修復星星狀態未更新 + 分享 Modal 被牌組面板遮蔽。`472d294`

### 快速查詢牌組 / 星星 / QR Code 首次上線
- 快速查詢牌組（dk_quick）：固定存在、不可刪/改名、每次開啟預設切到此牌組。
- 卡片星星按鈕：右下角 toggle ☆/★，快速加入/移除快速查詢。
- QR Code 分享：牌組面板「分享」→ 全螢幕 QR Code + 複製連結；掃描後自動匯入確認；LZString 壓縮 + qrcodejs 生成。`ef534ec`

---

## 2026-04-15

### 翻譯修正
- 修復 Q&A 技能標記誤譯：音譯/誤譯 → 正確中文標記。`8de2183`
- 修復 Q&A 事件牌名未還原日文。`2575e50`
- 事件牌名保護改為動態清單（56個唯一事件牌名），新增 Q&A 還原機制 `restore_event_names()`。`101ae82`
- Q&A 術語「原創」→「原本」（6 筆）。`fbbb36c`
- 技能翻譯審計：HV-P02-081 田中冴子位置異常修正。`54cdf74`

### 牌組功能
- 匯出/匯入保留顏色標籤設定。`fe4864d`
- 顏色 Modal 數字欄改為可直接輸入。`4cf3678`
- 顏色 Modal 張數控制 + 輸出圖 Header 精簡。`61bc90b`
- 牌組張數超限提示：N/40 格式，超限顯示 ⚠ + 橘色。`b759c5b`
- 輸出圖片：顏色群組化排列 + 右上角統計列。`c77b5f0`
- 修正顏色標籤分裂列。`7abdb43`
- **牌組顏色標籤功能**首次上線：分群設定、彩色外框、統計列、localStorage 持久化。`0a6361f`
- 牌組選牌無上限，輸出圖片才驗證（≤40張、事件≤8）。`150db4e`

### Q&A 功能
- Q&A 升級為 Google 翻譯版：繁中顯示 + 日文原文保留。`be1f35c`
- 新增卡片 Modal Q&A 折疊顯示區塊。`300cec4`
- 整合翻譯後的 317 件問答至 cards_data.js。`9a63987`

### 手機 UI
- Header 捲動隱藏。`2575e50`

---

## 2026-04-14

### UI
- Modal 數值版面重排 + 官方配色底色。`814a5f0`

### 翻譯修正
- 全面 REVIEW：補完所有殘留翻譯問題。`e8f50e4`
- 修正 4 個系統性翻譯 bug + 伊達工業卡優化。`9bcde36`

---

## 2026-04-13

### 翻譯
- 修正「對手的從X區」語序 bug + 白鳥沢卡翻譯優化。`3a0e658`
- 修正 3 個系統性翻譯 bug + 新增 5 張 PR 卡 MANUAL_OVERRIDES。`0b1c990`
- 新增翻譯系統維護文件（HTML 注釋）。`3ba4eb4`
- 統一觸發條件語氣：「每當/每次」→「當」。`b03c8d6`
- 逐筆修正 364 張卡翻譯：系統性規則修正 + 手動覆蓋（~120 張）。`1c430b5`
- 新增 PR-043~052 共 10 張新卡 + 翻譯完整覆蓋 364 張（0 平假名殘留）。`0ef27f2`
- 強化繁中翻譯：平假名/片假名全數清除（193→0 張殘留）。`6241cf8`

### 牌組功能（首次建立）
- 修正 createDeck 後 tray select 不更新。`1e593d4`
- 修正底部牌組選單初始化未填充。`1357045`
- **缺牌分析改名庫存分析**，預設牌組名去空格，輸入框 focus 清空。`b4bedca`
- 底部 tray 改為下拉選單切換牌組。`0a800db`
- 牌組轉圖片卡片標示改為卡號。`f8663eb`
- 卡片改為左上角數字輸入框（取代 + 按鈕與徽章）。`b787131`
- 缺牌分析版面對齊主網格，blur 自動儲存，圖片匯出改回 3x。`3e1c2cb`
- 牌組轉圖片解析度提升至 5x。`f788071`
- Qty Modal 增加 +/- 按鈕，手機格彈性三欄，底部牌組列收合。`141f5c1`
- 修正牌組唯一鍵改用 image_file，新增數量輸入，手機三欄顯示。`bdd5ad9`
- 修正 +按鈕可能加入錯誤卡片。`df036bb`
- 改善牌組圖片匯出品質與版面。`b711903`
- **PNG 圖片匯出/匯入牌組功能**首次上線。`4997854`
- 缺牌分析改為各牌組獨立管理 owned。`8237b6f`
- 缺牌分析改為數量比對（方案A）。`788d2f2`
- 修正牌組功能 TDZ 錯誤。`ea26b55`
- **牌組建立 + 缺牌分析功能**首次上線。`f391c0a`

### 手機 UI
- 修復手機版篩選欄消失問題：改為常駐置頂可收合。`17b4652`（PR #1）

### 專案初始化
- Initial commit：排球少年 バボカ!!BREAK 卡牌資料庫。`2747d61`

---

## 草案 / 待決策

- **PDF 列印功能**：卡片 63×88mm，A4 直向 9 張（3×3），方案 A（獨立列印模式）vs 方案 B（FAB 浮動按鈕）未決定
- **亮色主題**：預覽 `preview-light-theme.html`（本地，未 commit），官網配色 #0066CC 藍色系
- **翻譯強化 v1.0**：✅ 完成（2026-04-16 Session 2）
