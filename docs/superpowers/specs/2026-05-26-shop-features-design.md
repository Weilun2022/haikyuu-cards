# 小賣部功能擴充設計文件
**日期**：2026-05-26  
**狀態**：已核准（Spec Review v2）

---

## 範圍

六項功能分三個波次：

| 波次 | 功能 |
|------|------|
| Wave 1 | 付款方式欄位、運費/取貨方式、管理端訂單搜尋 |
| Wave 2 | 老闆拍圖上架自定義商品 |
| Wave 3 | 顧客訂單查詢、預購登記 |

---

## 技術架構（不變）

- **前端**：GitHub Pages 靜態 HTML（shop.html、admin.html）
- **後端**：Google Apps Script Web App（doGet / doPost）
- **資料庫**：Google Sheets（SS_ID: `1zgoiILh2PjxWadFrdyO60ETjJjuHWE6a73JF4tdnD8Q`）
- **圖片**：現有卡片在 `images/`；自定義商品圖片存 Google Drive

---

## Wave 1：Checkout 強化 + 管理端搜尋

### 1A. 資料結構

**新 Sheets 分頁「取貨設定」**（兩欄：名稱、運費、啟用）：

```
A              B    C
7-11取貨付款   60   Y
全家取貨付款   60   Y
郵寄           80   Y
面交            0   Y
```

**新 Sheets 分頁「付款設定」**（兩欄：名稱、啟用）：
```
A          B
轉帳/匯款  Y
面交現金   Y
取貨付款   Y
```

> 取貨方式與付款方式分兩個獨立分頁，避免單一分頁 section header 解析脆弱的問題。

**訂單 sheet 新增 3 欄**（A~I 現有 9 欄，延伸至 L）：

| 欄 | 欄位 |
|----|------|
| J  | 取貨方式 |
| K  | 運費 |
| L  | 付款方式 |

### 1B. Apps Script 變更

**新 GET action（公開，不需 token）**：
```
doGet?action=getShippingConfig
→ { ok: true, shipping: [{name, fee}], payment: [{name}] }
```
讀取「取貨設定」和「付款設定」兩個分頁，只回傳 C欄=Y 的列。

**writeOrder 變更**：  
appendRow 新增 row[9]=取貨方式, row[10]=運費, row[11]=付款方式

**getOrders 變更**：  
讀取範圍改 A~L（12欄），回傳物件新增 `shipping_method`, `shipping_fee`, `payment_method`

**updateSchema 變更**：  
自動建立「取貨設定」、「付款設定」分頁並填入預設資料（若不存在）。

### 1C. shop.html 變更

- 初始化時並行 fetch `getShippingConfig`（與商品資料同時載入）
- 結帳表單新增：
  - **取貨方式** select（動態建立）→ 選後自動更新運費
  - **付款方式** select（動態建立）
- 合計列：商品小計 + 運費 = **總計**（兩行顯示）
- submitOrder payload 新增 `shipping_method`, `shipping_fee`, `payment_method`

### 1D. admin.html 變更

- 訂單列表頂部加搜尋框（即時 client-side filter，搜尋 id / 姓名 / 電話）
- 訂單展開詳情新增顯示：取貨方式、運費、付款方式

---

## Wave 2：老闆拍圖上架自定義商品

### 2A. 資料結構

**新 Sheets 分頁「自定義商品」**（10欄）：

| A（id） | B（名稱） | C（價格） | D（庫存） | E（單位） | F（圖片URL） | G（啟用） | H（描述） | I（建立時間） |
|---------|---------|---------|---------|---------|------------|---------|---------|------------|

- id 格式：`CUSTOM-001`（Apps Script 自動產生，取現有最大序號 +1）
- 單位（E欄）：預設「件」，老闆可在 Sheets 改（盒/張/套/組）
- 圖片 URL 格式：`https://lh3.googleusercontent.com/d/FILE_ID`（可直接嵌入 img src，比 uc?id= 穩定）

**Google Drive 資料夾**：  
Apps Script 首次執行時以 `DriveApp.createFolder('小賣部商品圖片')` 建立，將 FOLDER_ID 存入 `PropertiesService.getScriptProperties()`，之後重複使用。

### 2B. Apps Script 變更

**`addCustomProduct`（需 token）**：  
單一 action 同時處理圖片上傳 + 商品資料寫入，避免中途失敗產生孤兒圖片。
```
POST action=addCustomProduct
body: { token, name, price, stock, unit, description, imageBase64, imageFilename }
→ { ok, id, imageUrl }
```
流程：先寫商品列（imageUrl 暫存空字串）→ 上傳圖片取得 URL → 回填 imageUrl 欄位。若圖片上傳失敗，整列刪除。

**其他 actions（需 token）**：
```
POST action=updateCustomProduct  → { ok }
POST action=deleteCustomProduct  → { ok }（軟刪除，G欄=N）
GET  action=getCustomProducts（公開）→ { ok, data: [...] }
```

**`initDriveFolder`**（一次性執行）：  
建立 Drive 資料夾，儲存 FOLDER_ID 到 Script Properties。

### 2C. admin.html 變更

新增 tab「🏪 商品上架」：

**上傳流程**：
1. `<input type=file accept="image/*" capture="camera">` → 手機直接開相機
2. canvas 壓縮（最長邊 1200px, JPEG 80%）→ 即時預覽
3. 填寫：名稱（必填）、價格、庫存、單位（預設「件」）、描述（選填）
4. 「上架」按鈕 → POST addCustomProduct → toast 成功/失敗
5. 上架成功後清空表單，重新載入已上架列表

**已上架商品列表**：
- 縮圖 + 名稱 + 價格 + 庫存（inline 可編輯）+ 上下架切換 + 刪除

### 2D. shop.html 變更

- 初始化時並行 fetch `getCustomProducts`
- 自定義商品顯示在「整盒/整彈」tab 最上方，section 標題「✨ 特賣商品」
- 卡片外觀與現有 product-card 一致
- 支援加入購物車（item type=`custom`，unit 欄顯示在購物車）

---

## Wave 3：顧客訂單查詢 + 預購登記

### 3A. 顧客訂單查詢

**新頁面 `order-status.html`**：
- 輸入手機號碼 → 查詢
- 顯示該手機的所有訂單（id、時間、金額、狀態、取貨方式）
- 每筆展開可看品項明細
- 狀態 chip 樣式與 admin.html 相同

**Apps Script 新 action（公開）**：
```
GET action=queryOrderByPhone&phone=XXXX
→ { ok, data: [{id, time, total, status, shipping_method, items:[...]}] }
```
- 只回傳非隱私欄位（不含地址）
- 電話需完整符合，避免部分查詢

**shop.html**：訂單成功頁新增「查詢我的訂單 →」連結至 order-status.html

### 3B. 預購登記

**新 Sheets 分頁「預購名單」**：

| 時間 | 商品ID | 商品名稱 | 姓名 | 電話 | 備註 |
|-----|--------|---------|------|------|------|

**去重邏輯**：同一電話 + 同一商品ID 已存在時，更新時間戳，不重複新增列。

**shop.html 變更**：
- 缺貨商品（stock=0）顯示「📋 預購登記」按鈕
- 點擊開 modal：姓名 + 電話（必填）+ 備註（選填）→ 送出
- 送出後 disable 按鈕（session 內不重複登記），toast 提示

**Apps Script 新 action（公開）**：
```
POST action=submitPreorder
body: { productId, productName, name, phone, note }
→ { ok }
```
寫入前先查重（電話 + productId），有則更新時間，無則新增。

**admin.html 變更**：
- 庫存頁各商品卡片顯示預購人數（從「預購名單」sheet 統計）

---

## 檔案變更清單

| 檔案 | 波次 |
|------|------|
| Apps Script（程式碼.gs） | W1 + W2 + W3 |
| shop.html | W1 + W2 + W3 |
| admin.html | W1 + W2 + W3 |
| order-status.html（新建） | W3 |
| Sheets 新分頁 | W1: 取貨設定、付款設定 / W2: 自定義商品 / W3: 預購名單 |

---

## 實作順序（每波次）

1. Apps Script 新增 actions + updateSchema
2. 執行 updateSchema 更新 Sheets 結構
3. admin.html
4. shop.html（+ order-status.html）
5. 推上 GitHub

---

## 不在範圍內

- 金流串接（LinePay / 信用卡）
- 自動寄信通知
- 多語言
