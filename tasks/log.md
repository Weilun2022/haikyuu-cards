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

## 2026-08-24

### Google Search Console 網站收錄設定（`327fb51`／`f28308f`／`8504f43`）

目的：讓 `https://weilun2022.github.io/haikyuu-cards/` 能被 Google 搜尋收錄，之前完全沒設定過任何 SEO 相關檔案。

- `327fb51`：根目錄加入 `google11f71f7789257c95.html`（Search Console「HTML 檔案」驗證法用，內容固定是 `google-site-verification: google11f71f7789257c95.html`），完成網站擁有權驗證。**這個檔案不要刪**，Google 會持續靠它確認擁有權，日後若要移除驗證要先去 Search Console 解除關聯再刪檔。
- `f28308f`：新增 `robots.txt`（允許全站爬取，但 `Disallow: /admin.html`、`/order-status.html`——這兩頁是內部管理／使用者訂單查詢頁，不該被搜尋引擎收錄）與 `sitemap.xml`。
- `8504f43`：`sitemap.xml` 從原本列 5 個公開頁面（首頁/game/campaign/promo/shop）精簡成只留 `index.html` 與 `promo.html`——使用者明確表示現階段只想讓這兩頁被搜尋到。**之後如果要讓 `game.html`／`campaign.html`／`shop.html` 也被收錄，只要把對應 `<url><loc>` 加回 `sitemap.xml` 即可，不影響 robots.txt。**
- 已在 Search Console 提交 sitemap，首次提交時 GitHub Pages 尚未部署完成，狀態顯示「無法擷取」；事後用 curl 確認 `sitemap.xml`／`robots.txt` 皆回應 `200 OK`，判斷純粹是 Google 抓取時機問題，非檔案本身有誤。
- 收錄進度可用 `site:weilun2022.github.io/haikyuu-cards` 在 Google 搜尋確認，通常需數天到一兩週才會出現結果。

---

## 2026-08-15

### 翻譯字型殘留修正（`#107`／`#108`，`4ca7215`）+ 兩筆技術債盤點

上次「全站人名統一無空格」重構（`#103`～`#106`）過程中順帶稽核發現、當時刻意排除的三件事，這次 session 逐一查證現況（記憶檔案快照跟現狀有落差，例如 MANUAL_OVERRIDES 筆數 168→167，已修正）：

**1. 5 筆「・」複合人名標籤字型殘留（黒/国/瀬→黑/國/瀨），已完整走完 Matt Pocock 流程並落地：**
- 用平行 workflow 查證：三個未提交文件（見下）內容完整自洽；セット→覆蓋誤譯規則其實已寫在 `clean_qa_text()`（`build_data.py:1494`），只是沒接進 `translate_skill()` 呼叫鏈；属→屬完全沒有通用轉換步驟，純靠 4 筆 MANUAL_OVERRIDES 頂著。
- `/diagnosing-bugs` 建立 feedback loop（以 `name_zh_data.py` 的 `status=confirmed/auto` 條目為權威來源反查殘留），確認這 5 筆是封閉集合、不會外溢到一般規則鏈輸出，判定跟項目「規則鏈技術債」完全獨立、可任意排序。過程中一度誤判 `HV-P03-080-N`「探せ」殘留也是同類 bug，後來查出那張卡本身就是 EVENT 卡「探せ」，`_protect_terms()`/`restore_event_names()`（`build_data.py:121-133`／`834-836`）刻意保留 EVENT 卡名稱引號引用的日文原文，是設計行為不是缺陷，已撤回排除。
- `/to-spec`（`#107`）→ `/to-tickets`（`#108`，單一垂直切片）→ `/implement`：TDD 沿用 `test_build_data.py` 既有縫，反轉舊的「維持原樣」釘住斷言＋新增涵蓋全部 5 筆的參數化測試；`/code-review` 兩軸抓到 2 筆 Standards 問題（註解殘留會過時的 issue 編號、新舊測試重複斷言），當場修正合併；86 個測試全過；`python build_data.py` 重新產生 `cards_data.js`/`cards_zh.json` 並逐一核對 5 張卡 `skill_zh` 正確。
- Push 前發現本機 `main` 落後 `origin/main` 3 個自動排程 commit（`promo_data.js`/`schedule_data.js`/`schedule_registry.json`，跟本次改動檔案無交集），`git pull --rebase --autostash` 安全接上後推送，`#107`/`#108` 隨 push 自動關閉。

**2. 未完成，寫入代辦（見 Task #1/#2）：**
- 三個從重構前就未提交的文件（`CLAUDE.md`／`docs/agents/a2a-hybrid-workflow.md`／`docs/agents/issue-tracker.md`）——內容查證過完整自洽，但 `CLAUDE.md` 新增段落引用的 `docs/agents/triage-labels.md` 目前是 untracked，commit 時要一併加入才不會產生斷鏈引用。
- `translate_skill()` 規則鏈技術債（166/167 筆 MANUAL_OVERRIDES 頂著規則鏈真實缺陷：89 筆贅字「的」、51 筆漏「若/當」、22 筆語序錯誤、7 筆假名殘留、4 筆属→屬、2 筆セット/覆蓋規則接線缺失）——量體大、風險高（會波及所有未重新審查過的卡片，且診斷發現還有 360 張從未被稽核過的卡片，範圍可能不只 167 筆），需要另開正式 `/to-spec` 處理，不適合輕量修復。

---

## 2026-08-05（Session 38）

### 牌組轉圖片版面重新設計（#93 主票，子票 #94/#95/#96 全數完成，`bb7bfb0`~`a7a997e`）

Matt Pocock 流程走完 `/to-tickets` 後拆出三張序列票，`/implement` 一次跑完：

- **`#94`**：新增 `js/deck-image-layout.js`（`computeDeckImageLayout()`），不碰 DOM 的純函式算固定 8 欄卡格幾何（畫布寬高/列數/每格 x,y），`js/deck-image-layout.test.js` 覆蓋 0/1-7/8/16/40/39 張等邊界，`cd js && npm test` 全過。
- **`#95`**：`drawDeckCanvas()`（`index.html`）頭部改版——舊版「品牌名+牌組名一塊、統計徽章列另起一條」雙層結構，改成單一黑框橫條（品牌 lockup 三行堆疊／牌組名／統計膠囊兩子組）。
- **`#96`**：卡格區改用 `#94` 的純函式算座標，固定 8 欄不再用 `Math.min(8, entries.length)`；卡格外框 1.5px/6px 圓角/陰影；畫布底色改白、內距改 28/32/22/32。回歸驗證：匯出的 PNG 走 `importDeckFromImage()` 讀回，內嵌牌組 JSON 正確重建。

`bb7bfb0` 首次落地後，兩軸 code-review（Standards/Spec）當場抓到兩個真問題（kicker 細線沒延伸到橫條右側、統計膠囊「枚」字級沒縮小），`e99f6a1` 修正。

### 頭部橫條後續 4 輪視覺 bug（使用者實測匯出真牌組後陸續回報）

這幾輪都是「先在 code-review 通過、單元測試也過，但實際匯出圖片後才發現的視覺問題」，說明 `index.html` 這類會碰 DOM/Canvas 的模組沒有自動化視覺測試 seam（見 `CODING_STANDARDS.md`），只能靠「本地渲染 canvas → 裁切截圖 → 像素掃描量測」這套手動迴圈驗證，這次 session 反覆用了很多次，記錄下來給下次類似情境參考：

1. **細線壓字＋卡格間距過大**（`dd50cd4`）：kicker 細線 y 座標落在 11px 粗體字的字身範圍內，線直接切過字；`headH` 已加了 `HEADER_GAP(22)`，又把整個 `headH` 傳進 `computeDeckImageLayout()`，其 `pad` 參數（32）在函式內部又疊加一次，雙重計算出 54px 間距。
2. **細線橫跨整條牌組名/統計膠囊**（`e23d8b3`）：上一輪照 issue 文字「延伸至橫條右側」把線終點改成橫條最右側 `contentX1`，結果牌組名字一長線就穿過整段牌組名。改回只延伸到 lockup 欄寬（跟第二行 wordmark 同寬對齊）。
3. **細線黏字模型錯誤＋統計字級對齊設計稿**（`3959ace`）：對照設計稿原始碼（`design_handoff_card_collection/card-collection.dc.html`）才發現細線根本不是「文字底線」，是跟文字同排 flex 垂直置中並排——之前用 baseline+descent 的底線模型硬塞進窄橫條，模型本身就跟設計稿不一樣，不管怎麼調 offset 都會覺得黏。改成用 `actualBoundingBoxAscent` 算文字視覺中心，線跟文字並排。
4. **統計膠囊字級再放大＋LOGO 垂直置中**（`cb24385`、`a7a997e`）：套用設計稿字面 px 值後使用者仍覺得偏小——canvas 用的 Segoe UI/Noto Sans TC 字體跟設計稿 Hiragino Sans/Yu Gothic 同字級視覺大小不同，且 canvas `bold` 對應字重比設計稿標示的 800 輕；直接加大字級/字重/膠囊高度後，橫條加高但左側 LOGO 三行的 y 偏移沒跟著重新置中，左右兩塊視覺不對齊，最後統一用 `contentMidY` 重新置中兩塊。

---

## 2026-08-02（Session 37）

### 修復伊達工業推薦影片打字錯誤（`f7de4ff`）

使用者回報：`index.html` 篩選「伊達工業」時沒有跳出情報站推薦影片，但 `promo.html` 明明有伊達工業標籤的影片。用 `/diagnosing-bugs` 流程排查：

- **建立 feedback loop**：寫一支 Node 腳本，`eval` 出 `promo_data.js` + `promo_tags.js`，重現 `index.html` 內 `SCHOOL_VIDEO_COUNT` 的計數邏輯，比對「用 `DB2PROMO_SCHOOL` 對照表查出的 key」vs「正確 key」各自算出幾部影片，兩秒內可重跑、可紅可綠。
- **根因**：`DB2PROMO_SCHOOL` 這張「卡牌庫日文校名 → 情報站繁中校名」對照表裡，`'伊達工業'` 誤對應到 `'伊達工'`（少打一個「業」字），跟 `promo_tags.js`／`promo.html` 自己的 `SCHOOLS` 陣列實際用的完整拼法 `'伊達工業'` 對不上，導致查表永遠算出 0 部影片，banner 跟卡片上的 `🎬 相關影片` 標籤都被隱藏。其餘 7 校（烏野/音駒/稲荷崎/白鳥沢/青葉城西/梟谷/鴎台）從一開始拼法就是對的，只有這一項是孤立的打字錯誤。
- **修復**：把該項改成 `'伊達工業':'伊達工業'`，一行修正。
- **`/code-review` 雙軸驗證**：Standards／Spec 兩軸子代理各自審查，皆無發現——確認範圍精準、無 scope creep、無其他相同 typo（另外交叉比對過 `cards_data.js` 實際 27 種校名值、`DB2PROMO_SCHOOL` 全部 8 個 key/value、`promo_tags.js`+`promo_data.js` 標註用到的所有校名字串，三方逐一核對，確認目前沒有其他學校有同樣的問題）。
- 沒有自動化測試 seam（`index.html` 屬於「會碰 DOM、沒有模組系統」的既有分界，見 `CODING_STANDARDS.md`），驗證方式是上述 Node repro 腳本 + 手動走查，不是遺漏。

---

## 2026-08-01（Session 36）

### 熱門學校標籤 + 卡名搜尋建議 大功能上線（#80，子 ticket #81~#90 全數完成並部署，`91b7f55`~`de3bb46`）

Matt Pocock 流程走完 `/to-tickets` 之後，`#80` 拆成 10 張子 ticket（A~J），這個 session 用 `/implement` 逐張跑完 `#81`~`#90`，每張都有獨立 commit + code-review（Standards/Spec 兩軸）+ GPT A2A 第二意見審查，重點記錄幾個「光靠單元測試抓不到、實測才發現」的真 bug：

- **`#81`（資料契約）～`#86`（本地狀態機）**：純函式部分（`computeTopSchools`/`buildSuggestions`/`addView` 等）用 `node:test` 覆蓋，跟 `functions/` 共用慣例，補了 ADR 0005 記錄「`js/` 底下刻意不碰 DOM 的模組也能用 `node:test`，靠 `js/package.json` 只宣告 ESM 邊界、不裝依賴」這個決定的理由。
- **`#82`（Firestore emulator）**：本機需要 Java（JRE）才能跑 emulator，環境原本沒裝，用 `winget` 裝 Temurin 21 解決。
- **`#89`（Firestore 同步整合）**：這張是全部子 ticket 裡踩坑最多的一張，全部是「連上本地 emulator 實測」才抓到的：
  1. `initSchoolViewCountSync()` 原本靠 `DOMContentLoaded` 判斷「type=module 橋接腳本一定跑完了」——實測發現不可靠（`school-popularity-firestore.js` 動態 `import` 外部 CDN 的 `firebase-firestore.js`，DOMContentLoaded 有時候會搶在這個 import 完成前就先觸發），改成跟 `cloud-sync.js` 一樣自己廣播一個 `hv-school-popularity-ready` 事件才可靠。
  2. `#87` 的 `renderTopSchools()` 裡 `computeTopSchools({}, ...)` 寫死傳空物件（`#87` 完成當下還沒有真實資料，這樣寫沒錯），但 `#89` 把真實快照接上以後忘記把呼叫點一起改掉，導致熱門標籤永遠停在 fallback 清單、`#89` 做的東西完全不會反映在畫面上——這個是實測「重新整理後應該要顯示真實排行」這條驗收才抓到的。
  3. `visibilitychange` 跟 `pagehide` 幾乎同時觸發時會把同一筆 `pendingDelta` 送兩次，Firestore atomic increment 各自疊加造成重複計數，加了 in-flight guard。
  4. **`file://` 開發預覽會把 URL query string 吃掉**：一開始想用 `?use-emulator` 這種 query 參數手動切換 emulator/正式環境，結果瀏覽器預覽工具對「專案資料夾外的 `file://` 路徑」是用靜態快照渲染，會把 query string 整個丟掉，導致原本以為連到 emulator，其實一直在打正式環境（好在正式環境當時規則還沒放行，只是一直 permission-denied，沒有真的寫入垃圾資料）。改用本機 `python -m http.server` 起一個真正的 HTTP server 才解決。
- **`#90`（Firestore 安全規則）**：白名單學校 key + 單次 increment 上限（9）用 Firestore Rules 的 `diff().affectedKeys()` 逐一檢查（規則語言沒有迴圈，10 個白名單 key 手動展開是刻意寫法）。GPT 複審時抓到規則允許小數增量（`next > prev` 沒檢查整數），補上 `math.floor(delta)==delta`；也抓到新規則上線後 `#82` 原本的 smoke test 會因為寫入路徑不在白名單裡被連坐擋下，另外開了 `_smoke-test/` 專用路徑解耦。
- **`#91`（整合驗收，人工執行）**：在合併後的 main 上重跑一輪端到端手動驗收（含用真實 `CompositionEvent` 模擬 IME 組字防呆、手機直橫式），GPT 複審這輪驗收本身的嚴謹度後，多補了失敗補送流程重驗、既有功能回歸檢查、規則測試在乾淨 emulator 上重新跑一次（不只是沿用之前 session 的結果）。

**部署 `firebase deploy --only firestore` 到正式環境的認證問題**：Firebase CLI 本身在這個 Bash 工具環境裡偵測到「非互動式」直接拒絕跑 `firebase login`（不是權限問題，是這個指令本身認定沒有真正的終端機輸入）。使用者一度想授權我直接跑登入流程，堅持拒絕——OAuth 登入這件事不管使用者怎麼授權都不會由 agent 代為完成，最後請使用者自己在終端機跑 `firebase login`，登入完成後才由我接手 `firebase deploy`。部署後直接讀正式 Firestore 驗證規則生效（含刻意送一筆超額/白名單外的寫入，確認正確被拒絕、沒有污染真實資料）。

**部署後使用者一連串「為什麼沒看到更新」的疑問**，逐一實測排除：不是離線模式（程式沒有離線判斷邏輯）、不是篩選會影響計數（篩選跟計數互不相干，逐步驗證過）、不是特定學校壞掉（梟谷用真實 UI 流程測過完全正常）——真正原因是：①「切分頁/關分頁才會觸發同步」跟「使用者還停留在畫面上」的時間差，容易誤判成沒生效；②既有的頁面版本偵測機制（`#79`）「同一 session 最多自動 reload 一次」，如果手機分頁在這次功能開發期間已經因為前面某次推送而重整過一次，之後就不會再偵測到後續更新，需要使用者真的關掉分頁重開。

### HV-PR-050 卡名翻譯修正「忠——！」（`de3bb46`）

使用者猜測卡名「ただーし！」原譯「只不過呢！」有誤，應該是人名。查證：這張卡自己的 `skill_zh`（技能文字）早就正確把同一句譯成「忠——！」、並提到角色「山口 忠」——卡名欄位（`name_zh_data.py`）跟技能欄位翻譯沒對齊，是本來就標記 `status: low`／「查無明確出處」的低信心翻譯。修正後 status 提升為 `high`，重跑 `build_data.py` 確認 521 張卡正常無新錯誤。

---

## 2026-07-31（Session 35）

### promo.html：影片抓取改累積歷史，修復相關影片被擠出視窗消失（`b62c779`、回填 `fa3db87`、補洞 `e74ddd3`）

使用者反映「promo.html 以往有許多從 YOUTUBE 被標住進來的影片，最近一次整合消失了」。用 `/diagnosing-bugs` 排查：先重放頻道公開 RSS feed（不用 API key）比對相關性關鍵字，跟實際 GitHub Actions log 吻合——`fetch_promo.js` 每次只看頻道最新 15 部影片（`MAX_RESULTS`），過濾後**整批覆寫** `promo_data.js`，完全沒有歷史累積。商家近期發了大量非排球少年內容的日常 vlog，稀釋比例後，舊的相關影片被擠出這個抓取視窗，就從網站上永久消失——不是「整合」壞掉，是設計上的固定視窗被頻道內容比例變化暴露出來。用 git 歷史驗證下滑趨勢（9→7→4 部）也對得上，且程式碼本身從建立以來從未變過、最近一次改動時間點跟下滑時間對不上，排除「最近整合弄壞」的假設。

給使用者選修法方向，選了「累積歷史記錄」：新增 `mergeVideos()` 用 `videoId` 去重合併新舊資料，一旦被判定相關就留著，`MAX_STORED=300` 上限只淘汰最舊的。寫了 `fetch_promo.test.js`（`node --test`，覆蓋「舊相關影片不因這次沒抓到而消失」「同影片重新分類覆蓋」「超過上限淘汰最舊」三案例），並手動確認修復前的邏輯（直接回傳 fresh）在同樣輸入下真的會弄丟資料，證明測試真的在抓這個 bug。

使用者接著要求「盡可能恢復所有排球相關影片」——加了 `workflow_dispatch` 手動回填模式（`getPlaylistVideos(..., {full:true})` 翻頁掃描整個上傳播放清單，`MAX_PAGES=20` 安全閥），觸發一次後從 4 部找回 **67 部**歷史相關影片。

### A2A GPT 品管複審一次，抓到一個真漏洞（`e74ddd3`）

三個本 session 修復（見下方兩節）做完後，使用者問「A2A GPT 當品管 REVIEW 一次是否 OKAY」——判斷屬於 `docs/agents/a2a-hybrid-workflow.md` 講的「純技術性、範圍明確的單點決策，適合拿來壓力測試」，跑了一次一次性問答（`ask_openrouter.ps1 -PromptFile`，附完整 diff + 三個修法的根因摘要，要求唱反調）。

**逐條驗證後只有一條站得住腳**：`getPlaylistVideos()` 回填翻頁到 `MAX_PAGES` 上限時，如果 `nextPageToken` 還在（代表還有更舊的影片沒抓完），迴圈靜默停止，沒有任何警告——跟這次修的「影片消失」是同一種症狀模式，只是換一個成因，補了一行 `console.warn`。

**其餘幾條驗證後是誤判或範圍外**，記錄下來避免以後對 GPT review 結果照單全收：
- GPT 說 `moveCardFromStack`/`moveGutsCard` 「無空位時可能呼叫 `resetCounterDelta('block:-1')`」——重讀程式碼確認 `if (idx === -1) { toast(...); return; }` 在賦值 `resolvedTarget` 之前就先 return，這個路徑走不到。
- GPT 說「diff 沒證明傳入 `resetCounterDelta` 的已經是解析後的 `block:i`，根因可能沒修完」——這點在改完當下就已經用瀏覽器 mock 注入實測驗證過（見下方攔網 bug 段落），GPT 不具備瀏覽器實測能力，這條踩到 `a2a-hybrid-workflow.md` 明確寫的「不適用」邊界（「真正的實測/驗證類問題，A2A 沒有能力驗證，不該當作驗證手段的替代品」）。
- 「reset 沒跟 zone 寫入形成交易」「並行操作非原子讀改寫」——這是整個 `game.html` 一直以來的寫法，不是這次改動引入或應該一併解決的範圍。
- schedule 腳本「靜默丟棄」解析失敗的列——不準確，程式碼本來就對每個跳過的列印 `console.warn`，會留在 GitHub Actions log。

**教訓**：A2A 品管複審值得跑，但複審意見要照 `receiving-code-review` 的紀律逐條驗證（回去讀實際程式碼、對照已經做過的實測結果），不能因為是「唱反調」語氣就照單全收；花時間驗證後省下了改一堆不需要改的地方，只留真正有價值的那一條。

### game.html：攔網手動調整值放新卡時沒有真的歸零（`4b38309`）

使用者反映「下一回合放攔網角色上去時，上一回合有什麼操作會影響到沒有重置的」。舊記憶裡有一條 30 天前記的類似線索（`block_zones[0]` INTERVAL 後不清），查證後發現那條講的是完全不同的東西——`game_engine/` 是另一個未進 git 的 Python 對戰引擎原型，跟 `game.html`（實際上線、純 JS）互不相關，已在記憶裡加註釐清避免以後搞混。

實際根因：`ZONE_TO_STAT` 把三格攔網（`block:0`/`block:1`/`block:2`）都對應到同一個共用鍵 `blk`（`counterDelta[role].blk` 是三格加總的手動調整值），但 `placeCard`/`moveCard`/`moveCardFromStack`/`moveGutsCard` 這四處放新卡後呼叫 `resetCounterDelta()` 時，傳的是 `zoneName.split(':')[0]` 算出來的裸字串 `'block'`——`ZONE_TO_STAT` 查無這個 key，函式直接提早 return，從未真的歸零。修法：四處都改傳 resolve 完位置索引後的 zone 名稱（`'block:i'`）。用瀏覽器 mock 盤面注入（`(0,eval)` 設 module-scoped `gameState`/`myRole`，stub `db.ref()`/`pushZones`）**逐一**直接呼叫這四個函式驗證過，修復前 delta 會沿用到下一次放卡，修復後正確歸零。

這是繼 2026-07-19 那次「攻擊值沒重置」bug（`a2855b3`，見上方 Session 記錄）之後，同一類「殘留狀態沒清乾淨」問題的第二個實例，但根因不同：前次是攻擊分數用錯 fallback 邏輯，這次是 reset 函式的 key 對不上。順手發現 `game.html` 有兩個同名但參數簽名不同的 `reorderStack` 函式（JS 會讓後面那個蓋掉前面的），跟這次的 bug 無關，已用 `spawn_task` 開一張獨立票追蹤。

### fetch_schedule.js：更新賽程來源網址（`ff9f19a`→`6884676`）

使用者要求把賽程來源換成新的 Google Sheet 網址。抓下新表快照本機驗證：欄位結構、表頭列位置都跟舊表一致，可以直接沿用既有解析邏輯，但只解析出 21~25 筆有效資料（舊表約 85 筆）。查證確認是真實資料量變小（新表標題「排球少年TCG_26年8月招賽」，看起來是月份制），不是解析壞掉——原本 `MIN_VALID_ROWS=30`（有效資料太少視為異常、中止不覆寫）的安全閥是照舊表規模訂的，會讓新表每次都被擋下來。問使用者怎麼處理，選擇直接取消這個閘門檻（不是調低數字），只保留「完全零筆」才中止的最低保護。

**Push 時撞到 rebase 衝突**：本機 commit 完成後才發現 GitHub Actions 排程在這之間又用舊來源跑了一次自動更新，`schedule_data.js`/`schedule_registry.json`（自動產生檔）產生衝突。判斷這類自動生成檔案手動解 conflict 沒意義且風險高，改成 rebase 時暫時取 origin 那版當佔位、code 部分正常套用，rebase 完成後**直接重新執行 `fetch_schedule.js`** 對新來源重新抓一次產生乾淨資料，這才是正確可信的結果，不是手動 merge 兩份自動產生的 diff。

---

## 2026-07-25（Session 34）

### 導入 Matt Pocock 開發流程 skill chain（開源 MIT，github.com/mattpocock/skills）

使用者要求導入這套流程（`setup-matt-pocock-skills` → `grill-with-docs` → `to-spec` → `to-tickets` → `implement` → `code-review`，`improve-codebase-architecture` 為定期維護）。安裝前先查證 repo 真的存在、MIT 授權屬實、逐一讀過每個 skill 的 SKILL.md 跟附屬範本檔內容確認沒有可疑指令，才下載安裝到 `~/.claude/skills/`（10 個 skill 資料夾，含 `setup-matt-pocock-skills` 的 issue-tracker/domain/triage-labels 範本、`domain-modeling` 的 ADR/CONTEXT 格式、`tdd` 的 mocking/tests 規則、`improve-codebase-architecture` 的 HTML report 格式）。

**`/setup-matt-pocock-skills` 執行結果**：
- **Issue tracker**：改用 GitHub Issues（`Weilun2022/haikyuu-cards`）。本機沒裝 `gh` CLI，用 winget 裝好後還要 OAuth 授權——用 device code flow（`gh auth login --web`），代碼交給使用者自己在瀏覽器確認（OAuth 授權屬於「使用者必須親自同意」的動作，不能代為點擊），完成後登入為 `Weilun2022`。設定寫在 `docs/agents/issue-tracker.md`。
- **Triage labels**：略過——`triage` skill 使用者原始清單沒列，沒裝。
- **Domain docs**：single-context（`CONTEXT.md` + `docs/adr/`，之後 `/domain-modeling` 實際需要時才建立），設定寫在 `docs/agents/domain.md`。
- 這個 repo 原本沒有 `CLAUDE.md`，新建，寫入上述兩個小節 + 使用者要求的「Matt Pocock 開發流程」硬性規則（流程順序、skill 全部 user-invoked 不能 agent 自己判斷觸發、tickets 發布完不代表能動手寫 code、`/implement` 不能再轉包給其他 subagent）。

### tasks/ 目錄改結構，配合新流程

使用者要求「完整轉換」到新流程、確保專案正常運作。關鍵決定是舊的 `tasks/` 目錄（原本中樞→子 Chat 跨 session 平行發包用的系統，見 `tasks/README.md`）怎麼處理。檢查發現 `task_01~10.md`/`output_01~10.md`/`collect_01.md`/`collect_result.md` 全部是 2026-04-15~04-20 建立、之後 3 個多月沒再碰過的**已結案批次**——不是還在追蹤的待辦。`tasks/README.md` 自己的慣例本來就寫「所有 task/output 檔完成後可歸檔（移至 `tasks/archive/`）」（第 31 行），所以直接照這個既有慣例歸檔，不是新發明規則。

**最終結構**：
- `tasks/archive/` — 舊批次全部檔案（歷史保留，不刪除）
- `tasks/log.md`、`tasks/night_optimization_log.md` — 繼續當開發日誌用，跟「追蹤待辦」性質不同，不受這次轉換影響
- `tasks/README.md`、`task_template.md`、`collect_template.md`、`subchat_prompt_template.md` — 平行發包機制本身保留（跟 GitHub Issues 不衝突，是兩件事：Issues 管「這張票要不要做」，這套機制管「怎麼把大票拆給多個子 Chat 平行執行」），`README.md` 補一段說明新舊分工
- 之後新功能一律先進 GitHub Issues，不再新增 `task_NN.md` 當追蹤用

---

## 2026-07-24（Session 33）

### js/cloud-sync.js：修正換裝置首次同步時空白本機覆蓋雲端顏色資料（`316aaf1`）

使用者回報「雲端上傳沒有上傳牌組顏色的設定」。逐層讀 `autoReconcile()` 後發現顏色欄位本身在 payload/hash/baseline 每個環節都有正確包進去，不是欄位漏傳的問題——真正根因在換新裝置第一次同步的 LWW（last-write-wins）判斷：`QUICK_DECK_ID`（快速查詢）是每個瀏覽器一啟動就會自動建立的固定 id 空牌組，新裝置對它從沒有 `baseline`，這時候「兩邊都有資料但 hash 不同」會落入「雙邊都改過，比時間戳」分支，而新裝置的 `state.dirty` 也是空的，原本的 fallback 邏輯把「沒有 dirty 紀錄」預設成「剛剛才改」（`Date.now()`），永遠贏過雲端的真實修改時間，導致新裝置的空白內容反過來覆蓋掉雲端已經上色的資料。修法：`baseHash` 是 `undefined`（這台裝置從沒同步過這副牌）又沒有 `dirty` 紀錄時，改成直接信任雲端、下載覆蓋本機，不再假設本機比較新。

**教訓**：`QUICK_DECK_ID` 這種「每個裝置都會自動生成、id 卻固定相同」的牌組，是這類同步 bug 的高風險點——一般牌組 id 是隨機產生，兩台裝置本來就不會撞到同一個 id 去踩中「沒有 baseline」的邊界情況，只有這種固定 id 的特例才會讓「新裝置」變成「常見情境」而不是原本註解講的「極端情況」。

### 牌組照片辨識功能：從 OpenCV.js/ORB 走到 Gemini Vision API 的完整過程（進行中，未部署完成）

使用者想要「上傳別人做的牌組總覽圖／實拍照，自動辨識卡片+張數組成牌組」。先走 `anthropic-skills:brainstorming` 流程定案技術路線：**方案 A** 純前端 OpenCV.js（ORB 特徵比對 522 張卡圖）+ Tesseract.js（張數 OCR），使用者選這個是因為想完全避開後端/成本。

**Python 原型階段**：離線用 `cv2.ORB_create` 幫 521 張卡圖建特徵庫（`build_card_feature_index.py`，未進 git，`*.py` 本來就 gitignore），寫 `scan_deck_photo.py` 做 knnMatch+RANSAC+NMS。合成測試（把卡圖直接貼到背景圖，加旋轉縮放）5/5 全對，驗證演算法本身沒問題。

**真實照片測試才是转折點**：使用者提供 6 張實拍牌組照片（社群帳號 MR_BOARD 的實拍分享圖、店家優勝牌組展示照），跑下去**幾乎全滅**（6 張只抓到個位數張正確卡，好幾張 0 偵測）。逐步排查：不是解析度問題（2048px 高解析度的照片一樣失敗）、不是反光單一因素（試過 CLAHE 對比增強、只用左側名字欄避開反光區都沒用，後者甚至更差——文字欄本身鑑別度不夠，卡跟卡長得太像）。**根因是官方數位卡圖跟任何一張實體卡實拍照之間的視覺落差，比 ORB/BRIEF 這類局部特徵比對能補的範圍還大**（印刷色偏、鏡頭角度、卡套反光、JPEG 壓縮），不是調參數能解決的系統性問題。

**改用 Gemini Vision API 徹底翻盤**：使用者主動問「Google AI 辨識度夠不夠、OpenRouter 有沒有免費額度」。查證後直接用 Gemini 官方 API（`gemini-3.5-flash`，2026-07 現行免費模型，`gemini-2.5-flash` 這時已經對新用戶下架）取代整套 CV pipeline，設計兩段呼叫：Pass 1 讀照片列出每組卡片的日文名/卡號猜測/張數/信心度；Pass 2 從資料庫撈同名候選版本圖片，讓 Gemini 對照片再次比對選出正確版本。同一份最難的照片（IMG_7843，先前 0 偵測）Pass 1 幾乎完美讀出所有卡（14 組，總張數 40 剛好對上合法牌組上限），Pass 2 候選池從 6 張放寬到 12 張後（因為及川徹單角色就有 10 種版本，原本 cap=6 直接排除掉正確答案）11/14 組自動解析出精確 card_no，剩下 3 組是事件卡長標題 OCR 沒完全對上資料庫文字，留給人工確認畫面處理。

**架構**：`functions/`（Firebase Cloud Functions v2，`scanDeckPhoto` callable，要求已登入）代理呼叫 Gemini（key 用 `functions/.env`，不進 git，也沒用 Secret Manager——見下方教訓）；`js/deck-scan.js` + `index.html` 的 `#deck-scan-overlay` 做確認/修正 UI（縮圖、張數輸入、候選版本切換、手動搜尋補漏抓的卡），接在既有「圖片轉牌組」按鈕上：先試讀自家 PNG 內嵌 metadata，讀不到才走這套 AI 辨識流程。前端部分已完成、在瀏覽器實測過 markup/CSS 正常渲染。

**卡在 Firebase 部署的 Blaze 方案門檻，暫停等使用者決定**：
1. 第一次以為 Spark（免費）方案就夠，因為查過「Spark 只限制呼叫非 Google 服務，呼叫 Gemini 這種 Google 自家 API 不受限」——**這個判斷只對了一半**：`firebase functions:secrets:set` 背後是 Secret Manager，需要 Blaze 才能啟用，所以改用 `functions/.env` 存 key 繞過 Secret Manager。
2. 但 `firebase deploy --only functions` 本身（2nd gen functions 用 Cloud Build + Artifact Registry 建置容器映像）**不管函式執行內容是什麼，部署這個動作本身就強制要求 Blaze**，這個才是真正躲不掉的門檻，跟呼叫哪個 API 完全無關。第一次跟使用者說「不需要升級 Blaze」是誤判，已經當面更正。
3. 使用者遠端操作不方便跑 `firebase login` 互動式 OAuth，改用 GCP 服務帳戶 JSON 金鑰做非互動部署（`GOOGLE_APPLICATION_CREDENTIALS` 環境變數）——用 Claude in Chrome 直接操作使用者真實瀏覽器（已登入）在 Cloud Console 建金鑰、事後補授權（原本沿用的 `firebase-adminsdk-fbsvc` 服務帳戶預設權限只夠 Firebase Admin SDK，不夠部署+改 IAM，補加「編輯者」角色）。IAM 表單輸入被 auto mode classifier 擋下（判定為敏感操作），改請使用者自己點完最後幾步。
4. 卡在 Blaze 門檻後，使用者選擇「暫停開發、寫日誌，之後再討論」——實際月費預期 $0（Cloud Functions/Build/Artifact Registry 免費額度都遠超這種個人專案用量），但綁卡是要使用者自己決定+操作的事，不能代為進行。

**教訓**：
- CV/影像特徵比對（ORB 之類）在「官方數位素材 vs 使用者實拍照」這種跨域場景下，準確度上限遠低於直接丟給有視覺理解能力的 LLM（Gemini/Claude 這類）讀圖——這類任務不該預設「輕量純前端演算法」就夠用，尤其輸入是不受控的真實世界照片時。之後遇到類似「辨識照片內容」需求，應該先用視覺 LLM 驗證可行性，而不是預設要自己刻 CV pipeline。
- Firebase/GCP 的 Blaze 付費方案門檻不是單一規則，**「執行期網路呼叫限制」跟「部署管線需求」是兩條獨立的門檻，只查一條會誤判**。以後遇到「能不能留在 Spark 免費方案」的判斷，要同時查函式*執行內容*跟*部署機制*（Cloud Build/Artifact Registry/Secret Manager 這些底層服務）各自的方案需求，不能只驗證其中一項就下結論。

---

## 2026-07-17（Session 32）

### index.html：牌組管理「統計徽章」改版——多輪迭代＋復原＋重新設計，最後收在牌組轉圖片 header

使用者要求優化牌組管理面板視覺（`c5a69a4`），把原本純文字「N/40　事件N/8」+ 扁平色點統計，比照缺卡清單頁的兩層徽章風格（標籤在上、圓角膠囊數字在下），找 GPT-5.6-Luna 討論定案配色（COLOR_TAGS 原色加深版才過 WCAG AA）。

**手機端連環 bug（`a2d20d0`→`a5434fa`→`9e08889`→`d590b89`→`c9b3184`）**：使用者實機接連回報「擠壓卡格顯示不滿5列」「點牌組名稱輸入框工具列消失」「點牌組切換下拉選單工具列消失」「收合工具列閃爍」，其中兩次根因猜測（iOS `<input>` 強制縮放、reorganize-select 尺寸）都沒解決同一症狀，最後使用者要求直接復原到整個徽章改版前的狀態（`6166b7f`）。

**真正根因找到**：找 kwaipilot/kat-coder-air-v2.5（新接入的協作模型，見 `web_collab.md`）純文字討論後判斷是 `.deck-panel` 用 `vh` 設 `max-height`，iOS 鍵盤彈出時 `vh` 不會跟著縮小（已知瀏覽器行為），改成疊加 `dvh`（`75ca5d2`）後使用者實機確認「工具列消失」問題真的解決——證實跟合併徽章到同一排這個動作本身無關，只是先前一起做才難以歸因。**教訓**：復原時要先把「純 bug 修復」跟「視覺改動」分開驗證，不要整包一起復原/重做。

確認 dvh 修復後才重新一步步套用視覺改版：先獨立一列驗證穩定（`1abf6ea`），使用者確認「工具列穩定但擠壓」後合併回排序/上色同一排（`1271e4a`），拿掉排序選項符號、面板加高到75vh顯示滿5列（`233e096`）。

### index.html：牌組轉圖片（drawDeckCanvas）統計列同步改版，兩輪視覺微調後找 GPT-5.6-Luna 圖像複審重新設計

牌組管理面板穩定後，使用者要求匯出圖片的右上角統計也改成兩層徽章（`919233b`）。使用者兩輪文字回饋（「沒質感、莫名多了一列」→ 加陰影+玻璃光澤+品牌名跟徽章合併一列 `778d20b`；「還是不夠好看，是否左側沒靠上對齊」→ 品牌名跟徽章標籤共用基線 `97b7f01`／`e64df6d`）都沒真正解決「很怪」的感覺。

**最後直接把使用者手機實測截圖丟給 GPT-5.6-Luna（Vision）看圖診斷**（`e4558f1`），而不是繼續猜測調整座標——診斷出真正問題是**資訊層級錯誤**：品牌名（識別）跟統計徽章（資料）被硬塞同一排，即使基線對齊還是像「品牌名+一排小按鈕」拼接感；六個徽章各自不同寬度+漸層+陰影+玻璃光澤視覺焦點過度分散；牌組名貼近底線主標題感不足；整條橘線太搶戲。重新設計成三塊獨立區域：左側橘色識別線框住「品牌名kicker+牌組名24px主標題」、統計徽章移到獨立淺色容器列（六欄等寬、拿掉漸層陰影改純色扁平膠囊）、底部橘線縮成一小段 accent。**教訓：文字描述「不好看」反覆猜測修正效果很差，有實際截圖時應該儘早直接送圖給有 Vision 的模型看，不要一直用純文字來回猜。**

驗證方式：這次過程中瀏覽器截圖工具一度整個卡住（`computer` 動作 timeout），改用「像素掃描」直接讀 canvas `getImageData` 驗證位置/顏色/間距（比對是否貼齊邊界、欄位是否等寬、取樣色值是否跟設定的 hex 完全吻合），比等截圖修復更可靠也更精確。

### web_collab.md：新增 kwaipilot/kat-coder-air-v2.5 協作模型

用 `/add-reviewer` 測試連線+能力（純文字，無 Vision，模型自陳僅支援文字輸入）後正式加入協作名單，用途是第二意見/交叉驗證，`reviewer.js --model kwaipilot/kat-coder-air-v2.5` 直接可用（不需要另外設別名，`MODEL_ALIASES[a]||a` 本來就支援任意 model id）。

### name_zh_data.py：HV-P02-089 事件牌重新翻譯（`ddd790c`）

使用者提供最終譯文「真想再多說幾次「怎樣，我的夥伴很厲害吧」」（原：「我還想多說幾次...啊」），status 改 `confirmed`，重跑 `build_data.py` 確認 521 張卡、無假名殘留。

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
