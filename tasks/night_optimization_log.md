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

## 待使用者早上決定（高風險/改互動模型/主觀，未自動做）
1. 輸一球 → 獨立浮動 FAB 按鈕（MiMo 建議，改互動模型）
2. 事件/發球格 180px → 拆成獨立 82px 格（改牌桌結構）
3. 可放置格 pulse 呼吸動畫（MiniMax 反對：分心耗電；其他可選）
4. 頂欄字級放大、格子標籤圖示化（主觀美感）
5. 手牌 mask 漸層提示（>6張時，可選；靜態 mask 會淡化邊緣卡）
6. landscape 橫向：寬>768px 會走桌面版佈局（既有行為，非本次改動）
備註：截圖工具與本頁不相容（7+ 次 timeout），改用 getBoundingClientRect 幾何量測驗證。
