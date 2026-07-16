# 開發日誌

---

## 📌 顏色架構設計參考（v3，2026-07-15 定案，目前僅套用於 promo.html + index.html）

**檔案位置**：`css/theme.css`（色票 token + base reset）、`css/components.css`（`.chip`/`.empty`/`input[type=text]`/`.overlay-backdrop` 共用元件樣式）。之後其他頁面要遷移時直接 `<link>` 這兩個檔案，不要在頁面自己的 `<style>` 裡重複定義這些 token。

**目前進度範圍（重要）**：**只有 `promo.html` 和 `index.html` 完成遷移。`game.html`／`shop.html`／`order-status.html`／`admin.html` 都還是舊的全黑主題，尚未開始，沒有使用者明確要求前不要主動繼續做。** 之前稽核發現 `game.html` 規模是 promo.html 的 5-8 倍（2565 行 CSS、色票已跟其他頁「悄悄分歧」、大量硬編色），`admin.html` 色票也已分歧，這兩頁風險最高，之後真的要做建議另開專門的 plan。

**色票 token（`css/theme.css`）**：
```css
:root {
  --bg: #FAFAFA;        --surface: #FFFFFF;    --surface2: #F3EFEA;
  --border: #E2DCD3;    --text: #0D0506;       --text-dim: #6B6B6B;
  --accent: #BE520B;    --accent2: #9C6209;    --focus: #FFB066;
  --on-accent: #FFFFFF;
  --success: #237A52;   --warning: #B86B00;    --danger: #C63D3D;    --info: #2D6FA3;
}
```
外加 40×40px 淡格線背景（純 CSS `linear-gradient` 重現官方卡表頁紋理，不是圖檔）。

**設計方法論（為什麼是這幾個值，不要亂改）**：
1. 方向定案：GPT-5.6-Luna 規劃「暖白球館」風格取代原本全黑主題，之後使用者陸續要求更貼近官方
2. v1（自訂暖米色，已棄用）→ v2（canvas 採樣官方 key visual 圖片像素）→ **v3（現行版本）：直接讀官方卡表搜尋頁 `/cardlist/` 真正在用的 UI 元件 computed style**，比圖片採樣準確：官方按鈕實色 `#DF600D`、內文黑 `#0D0506`、導覽列選中色是琥珀金 `#EDA613`（不是紅——v2 從某張 key visual 猜的紅色點綴證實猜錯）
3. `--accent`/`--accent2` 刻意比官方原色再加深一點（`#DF600D`→`#BE520B`、`#EDA613`→`#9C6209`）：官方原色套用在我們的小字白字 badge 上對比度不到 4.5:1（官方自己在大按鈕上也沒完全達標，但我們的用法字更小，需要更保守）
4. 學校色票（`--s-*`）與稀有度色票（`--r-*`）**刻意不放進共用 theme.css**：`index.html`（綁定 `cards_zh.json`，日文漢字鍵）跟 `promo.html`（綁定 `promo_tags.js`，繁中字鍵）是兩份獨立資料源，鍵名與部分顏色本來就不一致，不可合併，各自留在頁面本地 `:root`，只微調明度以符合新背景對比度
5. **改 accent/accent2 之後務必連帶檢查跟九校色票有沒有新的撞色**（曾經發生過：accent 加深後跟「烏野」幾乎撞色、accent2 改金色後跟「梟谷」幾乎撞色，兩校都已個別微調拉開距離）
6. 黑底元件是刻意的例外，不是「沒改乾淨」：DC 社群 hero（燒橘色調深色 scrim，不用灰黑）、頂部 header／分頁標籤（黑底白字，比照官方黑底導覽列與 promo.html `.tabs`）
7. 官方美術素材（角色照片、logo 圖檔）涉及著作權，跟純色票/幾何圖案不同——遇到官方素材要先判斷「有創作內容的美術/角色圖」（要問使用者連結 vs 下載）還是「純幾何/機械式圖案」（可以直接用 CSS 重現，不算複製）。曾經下載官方 mv6 主視覺人物圖當 DC hero 背景，後來因為跟社群自己的徽章疊在一起風格衝突而移除

**詳細背景**（設計討論過程、GPT 對話紀錄摘要、每個 bug 的來龍去脈）另存於 assistant 記憶檔 `project_visual_restyle.md`，這裡只列最終定案結果方便查找。

**追加 token（2026-07-16，缺卡清單專用「持有狀態」色，不在 theme.css 共用檔裡，只有 index.html 在用）**：
```css
--an-owned: #2E7D32;  /* 已持有（深綠，刻意跟 COLOR_TAGS 的舉球綠 #22c55e 拉開差異，避免混淆） */
/* 缺卡沿用 var(--accent) 燒橘、共計沿用 var(--text) 深黑，不用另外開新 token */
```

---

## 2026-07-16（Session 31）

### 跟 GPT-5.6-Luna 一起系統性 review index.html + promo.html（避免同類 bug 再發生）
使用者要求主動健檢，開兩個背景 agent 分別做系統性掃描（所有頂層 `let`/`const` 宣告 vs 所有函式呼叫鏈）+ 瀏覽器實測（含 `localStorage.clear()` 模擬全新訪客）+ GPT 交叉複審：

- **index.html**：沒有新的 TDZ 案例，但抓到 `normalizeDeck()`（原 `sortDeckCardsDefault`）排序規則只補在「新增卡片」跟「頁面載入」，**分享連結匯入**（`checkSharedDeck()`）、**雲端同步下載合併**（`hvRunAutoSync()` 的 `applyDownload`）、**雲端覆蓋本機**（`downloadCloudToLocalDestructive`）三條路徑都繞過了排序
- **promo.html**：沒有 TDZ 問題，但發現更嚴重的「未防呆裸引用」：`PROMO_DATA`（684行）/`PROMO_NEWS`（969行）沒有 `typeof` 防呆，資料檔（排程自動產生）萬一載入失敗會讓整個 `<script>` 從那行中斷——`PROMO_DATA` 失敗甚至會讓**三個分頁按鈕全部點不動**（tab 事件綁定排在後面沒機會執行）。另外賽程篩選對「新手交流」混合類型的賽事有篩選死角（目前資料沒觸發過，屬於潛在雷）

**三個決策點使用者直接說「給GPT決定」，GPT 拍板**（`4f4e45e`）：
1. 排序缺口修法：改成統一收斂點 `normalizeDeck(deck)`，5 個寫入 `decks` 陣列的地方全部呼叫同一函式，不再各自零星補（含 null 防呆）
2. 資料失敗 UX：補 `typeof` 防呆改空陣列 fallback + 新增 `#data-load-error` 明確提示 banner，跟一般「查無資料」空狀態區分開
3. mixed 類型篩選：讓同時符合「新手」「交流」字樣的賽事在兩個篩選 chip 下都會顯示

驗證：分享連結匯入測過排序正確；刻意把 `promo_data.js` 改 404 測過 banner 正常顯示且分頁按鈕仍可點（賽程分頁完全正常運作，因為資料源獨立）；塞測試資料驗證 mixed 賽事雙篩選命中。

### build_data.py：翻譯系統修復——CRLF 導致 annotation 假名殘留（pipeline 層級 bug）
使用者要求優化 HV-P03-001 的翻譯，順帶對全庫（不只 P03 系列）跑了一次假名殘留掃描，抓出 9 張卡的問題，分兩類：

1. **HV-P03-001（原始需求）**：`skill_zh` 的〔〕語序錯誤（比照既有 P03-013/014 的〔〕句型修正），`annotation_zh` 因為「攻擊階段+每回合1次+A」三段組合先前沒收錄進 `ANNOTATION_ZH` 查表，整段殘留日文——已補上 MANUAL_OVERRIDES（`HV-P03-001-I/IP/IA`）與新的 `ANNOTATION_ZH` 條目
2. **掃描順手抓到的 8 張同類/相關 bug**：HV-P03-057（同樣是階段組合未收錄，補了 draw-phase 版本）、HV-PR-063（`skill_zh` 大段未翻，補 MANUAL_OVERRIDE，牌名「ジャンバル最高!!」比照該卡自己已定案的 `name_zh`「Jump慶典最棒了！！」代入）、以及 **HV-P01-013/031、HV-P02-011/035/041、HV-D01-003、HV-D02-002 共 7 張**——這批的根因不是缺翻譯條目，而是**原始資料這幾張卡的 `skill`/`annotation` 用 `\r\n`（CRLF）換行，其餘卡片用 `\n`（LF）**，導致 `translate_skill()`/`translate_annotation()` 的 regex 規則與查表全部用 `\n` 撰寫、比對必然失敗。改成 pipeline 層級修復：`build_data.py` 主迴圈讀入每張卡時先 `.replace('\r\n', '\n')` 正規化，7 張全部靠既有翻譯條目自動命中，不用逐卡開 override。

**教訓**：舊的假名殘留掃描腳本只掃 P03 系列，這批 CRLF bug 潛伏在其他系列很久沒被抓到——之後要做這類健檢應該掃全庫，且不能只看「有沒有 MANUAL_OVERRIDE」判斷是否處理過。詳細記在 assistant 記憶檔 `reference_build_data_translation.md`。

驗證：`python build_data.py` 重新產生 `cards_zh.json`/`cards_data.js`（521 張），全庫假名殘留掃描（含所有系列，非只 P03）清零。

### index.html：缺卡清單改版，參考官方牌組構築頁但不借用四色語意（`6166b7f`）
使用者附官方「牌組構築」頁（`deck/edit.html`）截圖要求參考。實測官方頁面：頂部自由/接球/舉球/攻擊四個圓形色塊徽章（灰/藍/綠/紅，兩層結構：標籤在上、數字色塊在下）、卡槽 90×125px 淺灰圓角置中排球圖示代表空位。

跟 GPT 討論設計方向後**只借用視覺結構（兩層徽章、圓角比例），不借用官方四色語意**——那四色是我們自己 `COLOR_TAGS` 已經在用的策略分類色，統計如果也套同一組顏色會讓使用者搞混「這是分類色還是持有狀態」。改用獨立配色：缺卡（燒橘）/已持有（新增深綠 `#2E7D32`）/共計（深黑）。未持有卡片**不做成官方那種真空卡槽**（會讓使用者誤以為牌組資料遺失，因為缺卡清單顯示的是已設定的卡不是空位），改成保留清晰卡面+淡洗色疊層+燒橘外框+「缺」字角標，已持有維持綠框+勾勾（顏色配合新的深綠更新）。

---

## 2026-07-15（Session 30）

### promo.html：賽程搜尋改為直接篩選月曆格（`c26ebeb`）
- 原本搜尋店家名稱會切換成扁平清單畫面，比照地區/類型標籤的做法改成保持在月曆視圖、只隱藏不符合的日期，點篩選後的日期照樣可以彈出當天完整店家資訊
- 移除只有舊扁平清單模式在用的死碼（`renderSchedule`／`.sch-list`／`.sch-date-head`）

### 全站視覺改版 Phase 1+2：promo.html + index.html 全黑主題 → 官方參考淺色主題

**背景**：使用者要求全站脫離全黑深色主題（`--bg:#0f0f13`、通用紫 `#6c63ff`），改走「排球少年」主題感。先請 GPT-5.6-Luna（`web-collab`）做架構規劃，定案暖白球館方向；後續使用者多次要求「直接讀官方配色」，色票經過三輪迭代：

1. **v1**（`49fe995`）：自訂暖米色＋深藍灰＋青綠，GPT-5.6-Luna 規劃，新建 `css/theme.css`＋`css/components.css` 共用架構，promo.html 首波導入
2. **v2**（`56df22c`）：改用 canvas 採樣官方商品頁 key visual 圖片像素定色（近白背景＋鮮豔橘＋黑描邊＋紅點綴），DC hero 一度換成下載的官方 mv6 主視覺當背景圖
3. **v3**（`5a206e8`）：進一步直接讀官方卡表搜尋頁真正在用的 UI 元件顏色（比圖片採樣更準：`#DF600D`／`#0D0506`／琥珀金 `#EDA613`，證實 v2 猜的紅色點綴是猜錯），accent 比官方原色加深以符合白底文字對比度；分頁標籤（影片/賽程/入部申請）改成黑底＋白字＋橘色選中底，比照使用者提供的官方導覽列截圖

**其餘 promo.html 視覺修正**：
- 官方卡表頁淡格線背景，純 CSS `linear-gradient` 重現（40×40px、1px 線），非複製圖檔（`962413f`）
- 賽程月曆「沒有場次/已過去」淡化改用不透明淺色取代 `opacity:.4`，避免格線背景透出來看不清楚（`df29911`）
- DC hero 的官方主視覺背景圖跟社群自己的黑鴉徽章疊在一起風格衝突（水彩紋章 vs 動漫照片），使用者實測後要求移除，改回純漸層＋徽章，已下載的 `css/img/mv6_bg*.webp` 一併刪除（`1278b65`）

**index.html 淺色遷移**（Phase 2，`60fabe0`）：接上共用 `css/theme.css`/`components.css`，`--r-*`(稀有度)/`--s-*`(學校)色票留本地不搬共用檔（跟 promo.html 綁定不同資料源不可合併，注意 JS 常數 `SCHOOL_COLOR`/`RARITY_COLOR` 要跟 CSS token 同步，這次就漏改過一次卡片標籤還是舊色，補上才修好）。同時完成：
- Header/`.deck-tray` 深色漸層改淺色
- `.card:hover` 紫色光暈改中性陰影，其餘舊 accent 紫殘留 rgba／白字按鈕殘留清理
- 戰術統計「攔網」色塊深黑底改淺灰底深字（其餘四色維持彩色底不動），順便修正小卡列表對比度不足
- `.cloud-sync-compact` 獨立深色玻璃 UI 重新設計成淺色版
- `drawDeckCanvas()`（匯出牌組圖）canvas 手繪硬編色同步更新
- `share-modal-overlay` inline style 改淺色

**後續視覺微調**（使用者陸續回饋）：
- Header 背景消失格線 bug：`body { background:var(--bg) }` 簡寫蓋掉共用檔的 `background-image`，改用不用簡寫（`afa92e3`）
- Header 改比照官方黑底導覽列，標題改兩層字級 lockup 排版（小 kicker + 主字 + 橘色斜切色塊），**跟 GPT-5.6-Luna 審過一輪**採納三點修正：中日文字不用 `font-style:italic`（faux italic 對漢字/假名筆畫會變形，改成只讓英文 `BREAK` 用 `skewX`）、楔形色塊置中對齊、橘色提亮一階（`5f49149`）
- 篩選器改採官方「白黑白＋粗黑框＋硬邊陰影＋膠囊 select」視覺語言，同樣跟 GPT 討論過（官方只有 2 欄位、我們有 8 組+搜尋框，全套裝飾會變視覺噪音），改分層策略：外框粗黑線當畫框、搜尋框保留硬邊陰影當主要焦點、其餘 select 只有黑邊膠囊不加陰影（`3178f8b`）
- 桌面版搜尋框跟篩選器邊框沒對齊：CSS 特異性陷阱，同一個 `#search-row` selector 的 media query 覆寫規則被源碼順序在後面的裸規則蓋掉（`79d2b44`）
- 手機版篩選欄收合時粗黑框沒消失：邊框寫在不分裝置的基礎規則，`max-height:0` 收合不會讓 border 消失，變成固定顯示的黑線（`275dc39`）
- 牌組面板「工具」展開按鈕文字看不見：殘留舊深色主題的 `rgba(255,255,255,.45)` 白字疊在新白底上（`ceebb05`）

### game.html：「重置本局」防重入鎖（`5c04064`）
- 開子程序＋GPT-5.6-Luna 診斷「重置本局後牌庫超過40張」：`declareLost()`（自己按重置）跟 `handleRoundReset()`（收到對手重置通知）各自獨立收牌、彼此沒有鎖，加上 `handleRoundReset()` 少一個 `await`，快速連點或雙方重置時間點重疊會把同一批場上牌重複收進 pile
- 抽出共用函式 `performLocalRoundCollect()` 搭配 module-scope 布林旗標當進行中鎖；`declareLost()` 也加自己的旗標防止整個確認流程被連點重入；`handleRoundReset()` 補上缺的 `await`
- Mock Firebase 環境驗證：併發呼叫兩次都只收一次牌，牌數跟預期吻合，正常單次呼叫行為不變

### index.html：三個潛藏 JS bug 一併修復（`60bbd98`、`1057743`）
使用者回報「QR Code 分享又失效了」、「牌組管理排序跑掉了」，查出三個 **`let` 宣告晚於使用處的 TDZ (temporal dead zone) bug**，都是這幾天視覺改版之前就存在的舊 bug（`deckPreviewSelectedImg` 4/20 引入、`_hvDeckSnapshot` 7/10 引入、缺卡清單排序邏輯 7/12 只做了一半沒同步到牌組管理），跟本次 CSS 改動無關：

1. **QR分享偶發性失效**：`openShareModal()` 第一步呼叫 `closeDeckPanel()`，該函式用到 `deckPreviewSelectedImg`/`colorModeActive`/`colorModeSlots`/`colorModeSelectedIndices`/`colorModeSortKey` 這 5 個變數，但它們的 `let` 宣告寫在檔案更後面（`showDeckPreview`/上色模式那段）。不是每次都重現，操作過幾輪（開關牌組面板數次）才會踩到 TDZ 視窗——把 5 個宣告搬到 `closeDeckPanel()` 定義之前修正
2. **牌組管理排序沒套用**：缺卡清單的排序邏輯（角色優先、事件最後、同類依卡號）註解寫著「跟牌組管理一致」，但牌組管理實際上從沒真的套用過，只是照陣列加入順序顯示。新增 `sortDeckCardsDefault()`，在 `addCardToDeck` 新增卡片、`loadDecks()` 載入既有牌組時都套用，現有牌組的排序也一併修正
3. **★首次訪客 `init()` 直接崩潰（更嚴重）**：測試時用 `localStorage.clear()` 模擬全新訪客才發現——`loadDecks()`（`init()` 第一步）在「快速查詢」牌組不存在時會同步呼叫 `saveDecks()`→`hvOnLocalChange()`→`hvSnapshotDeckState()`，讀到宣告位置太晚的 `_hvDeckSnapshot`，丟出 TDZ ReferenceError 讓 `init()` 中斷，後面的 `buildFilters`/`applyFilters`/`bindEvents`/`renderGrid` 全部不會執行——**真正第一次造訪的新玩家會看到空白卡片列表**。`_hvApplyingRemote` 旁邊本來就有「宣告提前避免 TDZ」的註解（代表這個坑之前已經有人踩過修過一次），但新增 `_hvDeckSnapshot` 時沒有比照辦理，同個坑又踩了一次。已搬到跟 `_hvApplyingRemote` 同樣的提前宣告位置

**教訓（已寫入 memory `reference_index_js_tdz_bug.md`）**：這類「功能整個沒反應、沒有肉眼可見錯誤」的回報，優先在 console 手動呼叫入口函式＋try/catch 看 stack，比反覆點按更快定位；測 `init()`/首次載入相關的東西一定要額外測「清空 localStorage 後重新整理」，用同一個瀏覽器分頁測（早就有舊資料）永遠測不出首次訪客的問題。

---

## 2026-07-14（Session 29）

### web-collab 工具：重新評估 gpt-5.6-luna 的 token 控管（非本專案程式碼，屬協作工具設定）

**背景**：Session 25 把 GPT 協作夥伴從 openai/gpt-5.5 換成 openai/gpt-5.6-luna 時，直接沿用了舊模型的 token 控管邏輯（`reviewer.js` 預設 effort=high、max_tokens 固定 60000），沒有重新檢視新模型是否適用同一套假設。

**使用者指出**：gpt-5.6-luna 應該是「輕量反應迅速的模型」，要求重新評估。

**查證**：查 OpenRouter 官方模型頁＋API 確認屬實——gpt-5.6-luna 官方定位是快速、低延遲、成本效益高的模型（適合聊天/分類/輕量代理工作流），reasoning 非必選、**官方預設 effort=medium**，跟 gpt-5.5 那種重量級推理模型完全不同檔次。

**修法**（`~/.claude/skills/web-collab/reviewer.js` + `SKILL.md`）：
- 預設 effort：`high` → `medium`（官方預設值）
- max_tokens 從固定 60000 改成依 effort 分級：medium(預設)=24000／high,max=60000／low=8000
- `--preset high` 仍保留，真正需要深度架構推理時可手動指定

**實測驗證**：medium 預設回應約 2.4 秒（原本 high 常態 2-4 分鐘），`--preset high` 深度推理場合測試也正常運作。

**教訓**：換底層模型/供應商時，效能與成本相關參數（reasoning effort、max_tokens）要重新對照官方文件查證，不能預設新模型跟舊模型同量級直接沿用舊設定。已同步更新記憶檔案 `web_collab.md`／`feedback_multiagent_default.md`／`project_haikyuu.md`。

---

## 2026-07-14（Session 28）

### index.html：修正 QR Code 分享「複製連結」按了沒反應（`519fd88`）

**Bug 根因**
- `navigator.clipboard.writeText()` 在 document 焦點狀態不穩定時（例如剛關掉數量輸入框鍵盤後馬上點複製）會拋出 `NotAllowedError: Document is not focused`
- 原本的 `.catch()` 只會顯示「複製失敗」toast，但實際上完全沒有 toast 出現（另一個問題）——使用者感覺「按了沒反應」，F5 重整後焦點重置才正常

**修法**：新增 `copyShareUrlToClipboard()` + `fallbackCopyText()`，Clipboard API 失敗時改用 `document.execCommand('copy')` 透過暫時 textarea 兜底；不管哪條路都保證有 toast 提示

---

### promo.html：修正賽程搜尋清空後結果殘留（`60f01e8`、`2948435`）

**Bug 1（`60f01e8`）**：`sch-empty`（「目前沒有符合條件的賽事」）在切回月曆模式後沒有被隱藏
- `schUpdateViewMode()` 切換搜尋↔月曆模式時只處理 `sch-list` 和 `sch-cal-wrap`，完全沒有碰 `sch-empty`
- 使用者走「搜尋有結果 → 再打沒結果 → 清空搜尋」時，空白訊息會浮在月曆上方
- **修法**：在 `schUpdateViewMode()` 加一行讓 `sch-empty` 跟 `sch-list` 同步 — 不搜尋時一起隱藏

**Bug 2（`2948435`）— 根本原因**：CSS 優先級蓋掉 `hidden` class，`sch-list` 永遠顯示
- `.sch-list { display:flex }` 定義在 `.hidden { display:none }` 後面（第 415 行 vs 第 324 行），兩個 class 選擇器優先級相同時後定義者勝，導致 `display:none` 完全失效
- 所以 JS 邏輯一直是對的（`classList.toggle('hidden', ...)` 有正確被呼叫），但 CSS 讓 `sch-list` 無論有無 `hidden` class 都是 `flex`
- **修法**：改成 `.sch-list:not(.hidden) { display:flex }`，只在沒有 `hidden` class 時才套用 flex，讓 `hidden` class 可以正常覆蓋顯示

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
