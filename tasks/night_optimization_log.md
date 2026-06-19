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

(以下為夜間各 round 紀錄)
