# 夜間優化工作日誌

> 自主執行：四方協作（mimo/minimax/deepseek/hunyuan）設計 → Claude 整合 → preview 幾何驗證 → commit+push
> 起始：2026-06-20 夜間。使用者早上檢視成果。

## 規則
- 所有程式碼修改必須經四方 agent 協作設計，Claude 僅整合
- 每個改動 preview 幾何驗證後才 commit+push
- 保守：只做有共識且驗證通過的明確改善，不做高風險臆測性改動

## 進度

### Round 0（起點狀態）
已完成（先前 session）：
- 手機版 viewport 用 100svh + visualViewport，無溢出
- 雙方場地格子對稱 82px（iPhone14）/55px（SE）
- 攻擊格與其他格等大（移除 flex:1.4）
- 卡片放置 bug 修復（triggerPlace null dragData）
- 雙方 SET 加入牌組同列最左 + 自己 SET 帶輸一球

已知待修：
- 牌組列 tile 寬度不對稱：自己場 116px 撐滿、對手場 53px 置中

---

### Round 1 ✅ 牌組列寬度對稱（commit 已推）
- 問題：對手牌組列 tile 53px 置中、自己場 116px 撐滿
- 根因：#opp-area 有 align-items:center，導致 board-side 不撐滿
- 修法（四方共識 MiMo+DeepSeek）：對手牌組列加 align-self:stretch 覆蓋父層 center
- 驗證：opp/self 牌組列皆 116px×3、x 座標一致（widthsMatch:true），court 仍 82px 對稱

### 四方稽核發現（待辦清單，依優先級）
高（安全、CSS 為主，夜間自動做）：
- [ ] R2 放置視覺回饋：拖曳/點選時可放置格高亮（檢查 mobile-drop-target/mobile-tap-selected 是否有可見樣式）
- [ ] R3 回合方提示：當前回合方場地發光（檢查 my-turn-glow 在手機是否可見）
- [ ] R4 邊界：牌庫空時禁用抽牌、空手牌提示、手牌可捲動指示

中（留紀錄，視風險）：
- 頂欄字級放大、格子標籤可讀性

高風險／改互動模型（不自動做，等使用者早上決定）：
- 輸一球 改獨立 FAB 浮動按鈕（MiMo 建議）
- 事件/發球格 180px → 拆成獨立 82px 格（改變牌桌結構）

### Round 2+3 ✅ 回合發光增強 + 修選中卡裁切 bug（commit 已推）
- R2 回合提示：my-turn-glow 在手機 alpha 0.06→inset 0.16+0.38 邊框，明顯但不外擴（不裁切/不擠 court）。驗證：glow 套用、court 仍 82px 對稱
- R3 真 bug：選中手牌 translateY(-8px) 被 #hand-area overflow:hidden 裁掉、outline 在 z-slot 被祖先裁。四方一致改 scale(1.06)+box-shadow 環。驗證（關 transition 量測）：49→51.94px 放大、box-shadow 環生效、不被裁
- 註：preview fine-pointer 模擬，getComputedStyle 在 transition 進行中會回插值，量測需關 transition

### R4 評估：空牌庫已有功能防呆（drawCard toast「牌庫已空」），純視覺灰化為低優先，暫緩
### 高風險項（保留待使用者決定）：輸一球改FAB、事件/發球格拆分、頂欄字級

### Round 4 ✅ 空牌庫灰化（commit 已推）
- 獨立 MutationObserver 監看 #self-deck，為 0 時對 #pile-tile 加 deck-empty（opacity .45 + grayscale）
- 不用 pointer-events:none（牌組 tile 也是放回牌庫的拖放目標）
- 驗證：pile5 不灰 / pile0 灰、pointer-events 維持 auto

### 全解析度回歸驗證 ✅（四輪改動組合）
| 解析度 | 無溢出 | court對稱 | 牌組列對稱 | SET在場 | 輸一球 | 回合發光 |
|---|---|---|---|---|---|---|
| SE 375×667 | ✅ | ✅55 | ✅111×3 | ✅ | ✅ | ✅ |
| 13Pro 390×844 | ✅ | ✅82 | ✅116×3 | ✅ | ✅ | ✅ |
| ProMax 430×932 | ✅ | ✅96 | ✅129×3 | ✅ | ✅ | ✅ |
桌面版：R1/R2 僅 @media mobile；R3 class 僅手機 A3 流程觸發；R4 通用（桌面空牌庫也灰，屬改善）。不影響桌面排版。

## 夜間總結
完成（已 commit+push，4 個 commit）：R1 牌組列對稱、R2 回合發光增強、R3 修選中卡裁切 bug、R4 空牌庫灰化。
全部四方協作設計 + preview 幾何驗證 + 三解析度回歸。

---

### Round 5 ✅ 手機版看不到手牌 — 接上死碼 --dvh（commit 已推）
- 回報：iPhone 13 Pro / Chrome iOS，手牌列被瀏覽器底部工具列蓋住看不到
- 根因：遊戲畫面用 `height:100svh`，但 iOS 上 100svh 比真實可見高度高，最底的 #hand-area 被推到工具列下又被 overflow:hidden 裁。專案早寫了 visualViewport 量真高的 JS 寫進 `--dvh`，但 CSS 從沒用到（死碼）。
- 四方協作設計：#screen-game.active 高度三層降級 `100vh→100svh→calc(var(--dvh,1svh)*100)`；#hand-area 同步 `14svh→calc(14*var(--dvh,1svh))` 保持基準一致。
- 四方抓出原案 bug：fallback 若用 `1vh`，--dvh 未設時第三行解析成有效的 100vh(lvh) 會蓋掉 100svh、更糟 → 改用 `1svh`（MiniMax+Hunyuan）。
- 幾何驗證再抓真兇：`.screen{min-height:100vh}`(game.html:50) 繼承到 #screen-game 把高度頂回滿高、容器不縮 → 補 `min-height:0` + `max-height:calc(...)`。
- 驗證（390 寬，模擬工具列佔位）：可見 844/704/620 → 容器 844/704/620、手牌底部齊可見下緣、皆不裁、無 console 錯誤。改動全在 @media max-width:768px，桌面版不受影響。
- **✅ 使用者 13 Pro / Chrome 實機驗收通過，手牌已正常顯示。**
- 分歧（見下）：body min-height:100vh 底部多出空白，DeepSeek/MiniMax 想鎖、MiMo 認為可接受；MiniMax 全域寫法會誤傷 lobby 捲動，正解需 body:has(#screen-game.active) 或加 class。**使用者決定：先不動，實機觀察是否會被滑到再說。**

---

### Round 6 ✅ 手機卡片：停用跑出畫面的小提示 + 長按 500ms 叫翻譯詳情（已推，待實機）
- 回報：手機點卡片時小提示 #card-hover 跑到畫面左外被切掉。
- 根因：#card-hover 原是桌面 hover（綁 mouseenter），iOS 合成 mouseenter 漏出；寬 490px 在 390 螢幕必翻到左界外。
- 四方討論定案：時長 500ms（四方一致否決使用者原提的 1.5s，太久像沒反應）；移動>8px 取消長按改拖曳；所有卡片統一長按；手機停用 #card-hover；視覺回饋為主（震動 iOS 無效選配）；整合進現有 pointer 流程。**使用者拍板 500ms。**
- 四方出碼（deepseek/mimo），Claude 整合修正了 4 個佔位錯誤：場上卡 class 是 .z-hstack-card/.z-slot 非 .card；showDetail 的 key 含副檔名不可去；用真實 onPD/PM/PU 簽名；board pointerdown 不 preventDefault 以保留 tap→移動模式。
- 實作：(A) showCardHover 加 coarse guard 停用手機小提示；(B) 手牌 A3 長按用 data-img；(C) #game-board 委派長按 .z-slot img；(D) 單一 _lpFired 旗標 + window capture 吞掉 iOS 合成 click（避免長按後又選牌/進移動模式）；視覺 .lp-fire scale1.08。
- 驗證（preview，coarse-gated 無法模擬真觸控，改驗邏輯鏈）：載入無 console 錯誤；coarse 桌面=false（桌面 hover/排版不受影響）；檔名抽取 roundtrip 與 allCards(364) 對得上；showDetail 開/填/關正常。**真實長按手勢待使用者實機驗收。**

---

### Round 7 ✅ 手機詳情視窗直向堆疊 + 點圖看原圖（已推，待實機）
- 回報：長按開的 #detail-overlay（IMG_6602）左圖寫死 200px、橫向 flex，手機 box 僅 ~359px，文字被擠到 ~135px 看不清。無任何手機 media query。
- 使用者要：左圖盡量縮、文字給足；點圖→跳原圖。
- 四方一致（deepseek/mimo/minimax/hunyuan 全到齊）建議**直向堆疊**（圖縮上方置中、文字滿寬）優於「小圖留左」，因橫向縮圖後 5 格數值+技能仍擠。**回報使用者，使用者拍板直向堆疊。**
- 四方出碼但 showDetail 改寫都用假資料欄位（cardData.stats 等），與實際不符；Claude 只加「手機 CSS + lightbox + _detailImg 綁定」，**不動 showDetail 既有資料邏輯**（c.name/affiliation/5格srv-atk/skill_zh）。
- 實作：(A) @media max-width:768px #detail-box flex-direction:column、#d-img 96px 置中、.detail-info 滿寬、數值/技能放大；(B) 新增 #img-lightbox（z-1100，點任意處/✕ 關）；showDetail 設 _detailImg 並綁 #d-img onclick→openLightbox(img)；closeDetail 連帶 closeLightbox。
- 驗證（preview）：手機 box=column/圖96px/文字329px(原~135)；lightbox 開啟載入正確原圖、z-1100、開關正常、關詳情連帶關 lightbox；桌面 1280 仍 row/圖200px 不受影響；無 console 錯誤。**實機待驗收。**

---

### Round 8 ✅ 手機手牌放回牌組（tap 版，已推待實機）
- BUG：手機點手牌(選牌)再點牌組 → 走 `drawCard()` 變抽牌，沒有放回。教學 (game.html:3039) 早設計此功能但只實作「拖曳」版，tap 版沒接。
- 修法（四方協作，全到齊）：`_onPileTileClick` 在 drawCard 前插入手機選牌分支——讀 `.hand-card.mobile-tap-selected` 的 data-idx，用 `clientY-rect`（minimax 確認比 offsetY 穩，因 e.target 可能是 .t-val 子元素）判上半=牌頂/下半=牌底 → `returnHandToPile(idx,pos)` → `window.__clearMobileTapSelect()`。
- A3：setTapSelect/clearTapSelect toggle `#pile-tile.pile-return-mode`，並暴露 `window.__clearMobileTapSelect=clearTapSelect`。
- CSS：`.pile-return-mode` ::before='牌頂'(上半)/::after='牌底'(下半) 文字標籤 + 分隔線 + 淡化原數字；pointer-events:none 點擊穿透。class 只由 coarse A3 加，桌面不出現故不需 media gate；與桌面拖曳 .pile-top/.pile-bottom 不同 class 不衝突。
- 整合修正：四方多給 demo/佔位碼，Claude 用真實 setTapSelect/clearTapSelect/_onPileTileClick 整合。
- 驗證（preview，需給 pile-tile 真實高度否則 rect 塌縮誤判）：上半→return top、下半→return bottom、每次連帶 clear、無選取→draw；牌頂/牌底渲染、pointer-events none、暴露 OK；桌面無 .mobile-tap-selected 故分支跳過不受影響。**實機待驗收。**

---

### Round 9 ✅ 牌組改左右切 + 點手牌再點棄牌可棄牌（已推待實機）
- 回報1：R8 牌組切上下，但 tile 偏寬 → 改左右切。回報2：點手牌再點棄牌不會棄。
- 修1（四方一致）：`.pile-return-mode::before/::after` 由上下半(height:50%)改左右半(width:50%,top/bottom:0)，左=牌頂/右=牌底；`_onPileTileClick` 判定由 `clientY-rect/offsetHeight` 改 `clientX-rect/offsetWidth`（左半=top、右半=bottom，returnHandToPile 語意不變）。
- 修2（同 R8 模式）：棄牌 tile（game.html:2729）onclick `openDropViewer('self')` 只開檢視器、桌面靠 ondrop→handleDrop('drop')。新增 `_onSelfDropTileClick(e)`：有 `.hand-card.mobile-tap-selected` 就 `dragData={src:'hand',idx,img:L.hand[idx]}; handleDrop('drop',false)`（沿用桌面「確定送入棄牌區？」確認框）+ `__clearMobileTapSelect()`；否則 openDropViewer。HTML onclick 改呼叫它。
- 取捨 D：四方一致沿用確認框（防誤觸/與桌面一致/不可逆）。
- 提示 C：A3 setTapSelect/clearTapSelect 順手 toggle 棄牌 tile `.drop-tap-hint`（靜態紅框；**不用 mimo 的 pulse 動畫**，因 MiniMax 早反對分心耗電；也不加會被裁的文字 tooltip）。
- 整合修正：四方多寫 `window.dragData=` 與假 fetch API → 錯。`dragData`/`L` 是模組級（L 還是 const），須 bare 賦值。preview indirect eval 讀 dragData 確認 bare 賦值生效。
- 驗證（preview）：CSS 牌頂左半/牌底右半；clientX 左→top 右→bottom；棄牌有選取→dragData 正確(hand:3:d.webp)+真實 handleDrop 跳出確認框「確定送入棄牌區？」+清選取，無選取→openDropViewer；無 console 錯誤。**實機待驗收。**

---

### Round 10 ✅ 棄牌免確認 + 長按牌組翻牌頂(手機版面) （已推待實機）
- 需求1：棄牌移除確認框（桌面+手機都直接送棄牌區）。改 handleDrop('drop') 把確認框那段刪掉，直接 hand→discardFromHand / zone→discardTopFromZone / guts→moveGutsCard 後 return。place-confirm-overlay 仍供放回牌堆用，不孤兒。
- 需求2A：手機長按牌組 → 開桌面 openPeekSetup（翻牌頂 N 張，公開/私下）。桌面靠右鍵 oncontextmenu，手機無右鍵 → 接進 A3 長按框架：新增 `_lpStartAction(action,el)`（複用 IIFE 既有 _lpFired/_lpTimer/_lpSX/Y + 既有 board pointermove 取消 + window capture 吞 click），board pointerdown 加 `#pile-tile` 分支 → 長按 openPeekSetup、短按仍 _onPileTileClick（抽牌/放回，click 被 _lpFired 吞）。
- 需求2B：peek 手機觸控優化（@media≤768px，真實 selector + 深色主題）：peek-step-btn 44×44、peek-mode-btn ≥44、peek-card 兩欄(150px)、peek-card-actions button 13px/40px（原 10px 太小）、peek-panel-close 36px。
- 整合修正：四方（deepseek/hunyuan，mimo/minimax 空）的 _lpStartAction 用 window 全域 + 自加重複 listener → 改用 A3 IIFE 既有變數最小版；CSS 用了不存在 class（.stepper-group/.to-hand…）+ 淺色背景 → 改真實 selector + 深色主題。
- 驗證（preview 手機寬）：棄牌 discardFromHand 直接呼叫且確認框不開；openPeekSetup 開啟、step 鈕44/模式鈕47；面板 3 卡渲染、操作鈕40px/13px、4 鈕齊；無 console 錯誤；桌面（@media 外）不受影響。長按手勢實機待驗收。

---

### Round 11 ✅ 翻牌面板一排 3 張（已推待實機）
- 回報：R10 翻牌面板手機一排只 2 張，要至少 3 張。
- 修（四方一致推 Grid 最穩）：`.peek-cards-row` 手機改 `display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px`，`.peek-card` width:auto/max-width:none；操作鈕收緊 font12/min-height38/padding7 避免 3 欄擠裁。
- 驗證（preview 390）：5 張→3+2（首列 3 張），卡寬 111px、操作鈕 54×38px 文字無裁切、無 console 錯誤、桌面（@media 外）不受影響。

---

### Round 12 ✅ 回合發光改底邊光條（不再像「整區被選取」）（已推待實機）
- 回報：手機「整個區域一直是選擇起來的狀態很怪」。診斷：那是 R2 加強版 my-turn-glow（#self-area.my-turn-glow，game.html:2277）的 `border-color:var(--accent)` + `inset 0 0 0 2px .38` 全環，看起來就像被框選，且整個回合常駐。
- 修（四方分 a 純柔光 / b 底邊光條；採 b，因純柔光仍是整框、底邊條徹底破除「框」感）：改成 `border-color:transparent` + `inset 0 -4px 10px .22`（底邊光暈）+ `inset 0 -2px 0 .55`（底邊細線）。無動畫/無新元素/無 layout 改動。只在 @media≤768 的 #self-area.my-turn-glow，桌面 .player-area.my-turn-glow（game.html:654）不動。
- 驗證（preview）：box-shadow 已底邊版、全環2px消失、border 透明、無 console 錯誤。實機待驗收。

### 另案待查：手牌消失（非本次改動造成）
- 回報「放一張卡手牌全不見」。查全專案：唯一清空整手牌的是 handleRoundReset（重置本局，由 declareLost 經 Firebase roundReset 觸發，對手按也會清你的）。placeCard 放牌只 splice 一張、不清空。輸一球(loseRallySetPool) 也不觸發 roundReset。使用者稱非重置/穩定連線 → 程式上無法重現，需實機錄影/完整截圖（含是否跳 toast、是否換局）才能定位。**未改動。**

---

### Round 13 ✅✅ 重大 bug：放牌→整手牌消失 根因修復（已推待實機）
- 症狀：手機穩定連線、非主動重置，放一張牌後整手牌全不見、牌庫變~40。
- 根因（Explore agent 搜尋 + 四方確認）：`_processedRoundReset` 初始=0（game.html:3747），`rejoinRoom` 有對齊它（3682）防誤觸，但 `enterGame/create/join/start` 正常進場**都沒初始化**。若這場 Firebase 已有舊 `roundReset` 時戳（稍早任一方重置過），進場後放牌觸發的首次 'value' 回呼 → handleRoundReset 見 rv(舊時戳)≠0 → 誤判新重置 → L.hand=[]、手牌洗回牌庫（self-deck→~40）。
- 修法（Option C，四方一致最周全）：在 listenGame（所有進場路徑唯一監聽樞紐）加閉包旗標 `_firstSync`，首次回呼即 `_processedRoundReset = data.roundReset || 0`，把進場當下既有 roundReset 視為已處理。涵蓋 host/guest/觀戰/重連，與 rejoinRoom 冪等，不吞真正的新重置（非首次回呼）。
- 驗證（preview，indirect eval 直測 handleRoundReset）：**未對齊→手牌3變0（重現bug）；對齊後→維持3（修復生效）**；修法碼在 listenGame；無 console 錯誤。實機待驗收。
- 註：「整區像被選取」確認是 tap 選牌的 .mobile-drop-target 放置提示（正常）+ R12 已改的回合發光，與本 bug 無關。

---

### Round 14 ✅ bug：移動 guts 牌選「當 Guts」仍放最上方（已推待實機）
- 症狀：選場上 guts 牌移到占用格，選「當 Guts」結果還是放最上方。
- 根因：executeMoveToZone（game.html:6473）對 m.type==='guts' 的「最上方」「當 Guts」兩 callback 呼叫同一個 moveGutsCard（無區分），而 moveGutsCard（6687）目標格分支永遠 `{img:gutsImg, guts:[...,old]}`（移動牌恆在上）、無 top/guts 參數。對照頂牌移動 moveCard(asGuts) 邏輯本來就對。
- 修（四方一致）：moveGutsCard 加 `asGuts=false` 參數，目標一般格分支區分（asGuts? 原牌留上、移動牌墊下 : 移動牌上、原牌墊下）；executeMoveToZone 兩 callback 分別傳 false/true。其他呼叫者（handleDrop guts→drop、_peekPlace）走 hand/pile/drop target 不進此分支，默認 false 行為不變。
- 驗證（preview，stub Firebase 攔截 zones）：asGuts=false→{img:移動牌,guts:[原牌]}（上）；asGuts=true→{img:原牌,guts:[移動牌]}（下）；correctTop/correctGuts 皆 true；無 console 錯誤。實機待驗收。
- 重設計（top/guts 更順手）：四方分歧——DeepSeek/MiniMax 傾向格子切上下半 inline；MiMo/Hunyuan 反對（場上格~44px 太小、切半22px 易誤觸），主張改良 modal（底部 sheet + 圖示預覽 + 大按鈕）。屬主觀 UX，回報使用者定方向（未動）。

---

### Round 15 ✅ 重設計：場上占用格移動改「左右切」取代彈窗（已推待實機）
- 使用者定案：跟牌組一致，左=Guts(墊下)、右=角色(最上方)，免 modal。
- 實作（四方 hunyuan/mimo 設計，Claude 對接真實碼）：executeMoveToZone 加 e 參數，占用格 zone/guts 分支不跳 showPlaceConfirm，改用 `(e.clientX-rect.left)<width/2` 判左右→moveCard/moveGutsCard(asGuts)。呼叫點 cardEl.onclick(4390)/slot.onclick(4450) 傳 e（onEmptyZoneClick 是空格不需）。視覺：enterMoveMode 對占用 z-slot 加 .zone-split-hint，clearZoneHighlights 移除。CSS .zone-split-hint ::before左Guts(綠)/::after右角色(紫) 半透明覆蓋、pointer-events穿透。
- 整合修正：四方用佔位(game[zoneName]/自製modal/#self-court 假設)，改用真實 m=moveMode/getZoneCard/既有 #self-court .z-slot/clearZoneHighlights。CSS ::after 被既有 `.z-slot::after{content:none!important;display:none!important}`(手機隱藏區域名)蓋掉→加 !important 覆蓋。
- 驗證（preview）：左半→moveCard(true) 右半→moveCard(false)；Guts/角色 標籤都顯示；真實 z-slot 119×82px、半邊59px 觸控充裕；無 console 錯誤。實機待驗收。

---

### Round 16 ✅ 占用格左右切只看到「角色」修正（已推待實機）
- 回報：R15 占用格左右切只看到右「角色」，看不到左「Guts」；要整個區域明確左右切。
- 根因（preview 實測）：stat 計數器 .z-stat-overlay 在格子右側 74-96%、z-index:5，而 zone-split-hint 標籤 z-index 只有 3 → 被計數器壓住、加上卡圖對比，左半 Guts 不明顯。
- 修：zone-split-hint ::before/::after z-index 3→6（高於計數器 5）、底色 .42→.55 加濃、中間改 2px 實心白分隔線、字陰影加強。整個格子明確兩半、標籤都在最上。
- 驗證（preview attack 占用格）：Guts/角色 都 z-index 6、labelsAboveOverlay:true、底色 .55、無 console 錯誤。實機待驗收。

---

### Round 17 ✅ 移動模式隱藏 stat 計數器，左右切乾淨（已推待實機）
- 回報：占用格左右切「左半看到角色、右邊空的」，行為其實正確（左guts右置頂），是顯示亂。優化建議：移動選位置時隱藏 +/− 計數器專注左右半。
- 查證（preview）：標籤沒搞反——左 ::before=Guts、右 ::after=角色 都 z-6。亂的主因是右側 stat 計數器 .z-stat-overlay（z-5，74-96%彩色塊）遮蔽右半「角色」造成「右邊空」錯覺。
- 修（四方一致，CSS 一行）：`.z-slot.zone-split-hint .z-stat-overlay { display:none !important; }`。只隱藏占用格（移動模式）計數器，其他格保留作參考；退出移動模式 class 移除即恢復。
- 驗證（preview）：計數器 移動前flex→移動中none→退出flex（恢復正常、無副作用）；hint 啟用時 left=Guts/right=角色；無 console 錯誤。實機待驗收。

---

### Round 18 ✅ 場上移動改兩段式 + 根因比對（已推待實機）
- 回報：占用格左右切「都卡在左邊」，要兩段式（第一階段整區亮燈、第二階段點某格才切左右）。使用者要求多 agent 獨立搜尋比對。
- **根因比對（兩 agent 不一致）**：Explore agent（讀碼）說 CSS `.z-slot::after{display:none!important}` 蓋掉「角色」；Claude（preview 實測）說「角色」其實有顯示（兩 class+!important，specificity 高者勝），真因＝卡片 48px 靠左(佔格 6%-46%)+所有占用格同時切。**四方一致裁決 B(Claude) 正確**，A 漏算 specificity。
- 修（四方一致兩段式狀態機，Claude 用真實碼整合——source 資料已在 moveMode 不需另存）：新增 `movePendingZone`。enterMoveMode 只加 .target 不加 zone-split-hint。executeMoveToZone 占用格分支：無 pending 或別格→設 pending+只給該格加 zone-split-hint+return 不放；同格第二次→clientX 判左右 moveCard/moveGutsCard(asGuts) 後 exitMoveMode。exitMoveMode/clearZoneHighlights 清 movePendingZone。空格分支既有 exitMoveMode 自動清。
- 驗證（preview 狀態機）：進入 8格亮燈/0切；點占用→pending設+該格切+不放+仍移動模式；切別格→pending轉移；同格左半→moveCard(true)、右半→moveCard(false)+退出；pending中點空格→直接放+清pending；無 console 錯誤。實機待驗收。

---

## Session 總結（2026-06-20 日間 → 2026-06-21，手機版 R8–R18）
四方協作（deepseek/minimax/hunyuan/mimo）設計 → Claude 整合 → preview 幾何/邏輯驗證 → commit+push。

| 輪 | 成果 | 狀態 |
|---|---|---|
| R8 | 手機 tap 手牌→點牌組放回（左=牌頂/右=牌底，`pile-return-mode` CSS） | 已推待實機 |
| R9 | 棄牌改左右切 + tap 手牌→點棄牌直接棄（`_onSelfDropTileClick`） | 已推待實機 |
| R10 | 棄牌免確認 + 長按牌組 → `openPeekSetup` 翻牌頂 + peek 面板手機優化 | 已推待實機 |
| R11 | 翻牌面板 grid 三欄（原二欄太窄） | 已推待實機 |
| R12 | 回合發光改底邊光條（消除「整區被選取」感） | 已推待實機 |
| R13 ⭐ | **重大 bug：放牌→整手牌消失**（`_processedRoundReset` 未初始化）修復 | 已推待實機 |
| R14 | bug：移動 guts 選「當 Guts」仍放最上方（`moveGutsCard` 缺 `asGuts` 參數） | 已推待實機 |
| R15 | 重設計：占用格移動改「左右切」（`zone-split-hint` CSS，免 modal） | 已推待實機 |
| R16 | 占用格左右切只看到「角色」→ z-index 3→6 + 底色加濃 | 已推待實機 |
| R17 | 移動模式隱藏 stat 計數器（`display:none !important`），左右乾淨 | 已推待實機 |
| R18 | 兩段式移動（第一段全區亮燈，第二段點同格才切左右，`movePendingZone` 狀態機） | 已推待實機 |

⭐ R13 最重要：根因是 `listenGame()` 首次 Firebase 回呼未對齊 `_processedRoundReset`，若該場曾有舊 `roundReset` 紀錄，進場放第一張牌後 `handleRoundReset` 誤觸 → 手牌清空。修法：`listenGame` 閉包 `_firstSync` 旗標，首次回呼即對齊，涵蓋所有進場路徑。

---

## 📘 版面開發經驗教訓（給後續 session）

1. **先查「半成品死碼」再動手**：本輪根因是 `--dvh`（visualViewport 量真高）JS 早就寫好，但 CSS 從沒引用。修 bug 前先 grep 既有變數/工具函式，往往正解只差「接線」，不必重寫。
2. **iOS viewport 單位順序陷阱**：CSS 同屬性多行「後者覆蓋前者，但僅限有效值才覆蓋」。`calc(var(--X, 1vh)*100)` 在 --X 未設時是**有效**的 100vh，會蓋掉上一行 100svh；fallback 要用 `1svh` 才安全。iOS：`100vh=lvh(最大)` > `100svh(最小)` > 真實可見(`--dvh`)。
3. **改了高度沒反應 → 先找 min-height 繼承**：`#screen-game` 改 height 卻不縮，真兇是 `.screen{min-height:100vh}`(line 50) 繼承上來頂住。**幾何驗證才抓得到**——光看 CSS 容易漏掉跨規則繼承。改容器高度時必同查 min-height/max-height 來源。
4. **節錄 snippet 給四方審的盲點**：第一輪只貼了目標規則，沒貼 `.screen` 繼承規則，四方因此沒抓到 min-height 真兇。**發審時要連同祖先/繼承相關規則一起貼**，否則審查有結構性盲區。
5. **preview 驗證手法（補充 [[reference-game-preview-testing]]）**：驗 viewport/高度類改動，用「停用其他 #screen-* + 啟用 #screen-game.active + 在同一個 eval 內掃多個 --dvh 值量 getBoundingClientRect」最可靠，能模擬不同工具列佔位、且避開狀態被 showScreen 重設。先用 probe div 套同一 calc 表達式可快速判斷「是表達式無效還是被別的規則頂住」。
6. **四方分歧 + 對方方案有副作用時**：不盲從多數決（MiniMax 全域 body 鎖會誤傷 lobby），先查證副作用，回報使用者並給出無副作用的正解選項。

## 待使用者決定（高風險/改互動模型/主觀）
0. ~~【R5 後續】body 底部空白~~ ✅ 已修正
1. ~~輸一球 → 獨立浮動 FAB 按鈕~~ ✅ 已修正
2. 事件/發球格 180px → 拆成獨立 82px 格（改牌桌結構）
3. 可放置格 pulse 呼吸動畫（MiniMax 反對：分心耗電；其他可選）
4. 頂欄字級放大、格子標籤圖示化（主觀美感）
5. 手牌 mask 漸層提示（>6張時，可選；靜態 mask 會淡化邊緣卡）
6. landscape 橫向：寬>768px 會走桌面版佈局（既有行為，非本次改動）
備註：截圖工具與本頁不相容（7+ 次 timeout），改用 getBoundingClientRect 幾何量測驗證。

---

## Session 總結（2026-06-21，卡片詳情 modal 重構）
四方協作（deepseek/minimax/hunyuan/mimo）設計 → Claude 整合 → preview 邏輯/幾何驗證 → commit+push。

| 輪 | 成果 | commit |
|---|---|---|
| R19 | guts 非頂牌短按直接進移動模式；長按改觸發卡片資訊 modal（`cardEl._gutsActionData` 橋接 A3 scope） | `9f6e27e` |
| R20 | `showDetail` 統一改顯示 `#hand-action-overlay`（移除 `#detail-overlay` 路徑）；`#ha-img` 改 `openLightbox`；`closeDetail` 輕量化不清 selection | `8b2b6b2` |
| R21 | `.ha-modal-img` 圖片改 flex stretch + `object-position:top center` 裁底部（仿翻譯網站效果）；修正手機 media query 順序 | `f1102bd` |
| R22 | lightbox z-index 1100→4000，確保蓋過 `#hand-action-overlay`(3500) | `5c83fa8` |

**R20 重點**：`showDetail(img)` 重寫為呼叫 `_fillModalCardInfo` + 隱藏移動按鈕 + 開 `#hand-action-overlay`，桌面/手機統一入口。`closeDetail` 改為輕量關閉，不呼叫 `clearSelection/clearZoneHighlights`（escape handler 另行處理，避免清掉 peek 狀態）。

**R21 關鍵教訓**：`align-self:stretch`（flex 預設）讓圖片容器隨右欄撐滿高度，需配合 `img{height:100%; object-fit:cover; object-position:top center}` 才能裁底部。若設 `height:130px` 固定值會阻斷 stretch，只出現小方塊。

---

## Session 總結（2026-06-20 日間）
手機版多方協力：四方協作（mimo/minimax/deepseek/hunyuan）設計 → Claude 整合 → preview 驗證 → commit/push。三項皆**使用者 13 Pro / Chrome 實機驗收通過**。

| 輪 | 成果 | commit |
|---|---|---|
| R5 | 接上死碼 `--dvh` 修手機看不到手牌（含 `.screen{min-height:100vh}` 真兇 → `min-height:0`） | `e5ac1bb` |
| R6 | 卡片長按 500ms → showDetail 詳情；停用跑出畫面的 `#card-hover` 小提示 | `32fa577` |
| R7 | 詳情視窗手機直向堆疊（圖縮上方、文字滿寬）+ 點卡圖看原圖 lightbox | `5ea68bf` |

待決（使用者暫不動）：body 底部空白只在真機工具列存在時出現，正解 `body:has(#screen-game.active){overflow:hidden}`（只鎖遊戲畫面，不傷 lobby）。
手機互動模型與彈窗清單已存入 memory `reference_game_mobile_ui`。
