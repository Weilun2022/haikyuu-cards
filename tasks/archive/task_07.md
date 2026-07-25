# 任務 07：Mobile Modal 圖片填滿版面優化

## 背景
Mobile 點開卡片時，Modal 圖片區（`.modal-img`）目前設定 `height: 240px; width: 100%`，
但 img 標籤只有 `width: 100%` 沒有明確 height，導致 `object-fit: cover` 無法正確作用，
圖片沒有填滿容器、留有空白，同時 240px 高度又佔了相當版面。

## 目標
1. Mobile 圖片區完整填滿容器，無空白邊
2. 圖片高度改為 `56vw`（比例感，適配不同螢幕寬度），小於現有 240px 固定值
3. 使用 `object-fit: cover; object-position: top center` 顯示卡片上方（角色臉部區域）
4. 保留既有 lightbox 點擊放大功能不動

## 技術細節

### 現有 Mobile CSS（約 line 525–528）
```css
@media (max-width: 600px) {
  .modal { flex-direction: column; }
  .modal-img { width: 100%; height: 240px; }
  ...
}
```

### 現有全域 CSS（約 line 343、370）
```css
.modal-img img { width: 100%; object-fit: cover; }
.modal-img img { width: 100%; object-fit: cover; cursor: pointer; }
```
（同一個選擇器寫了兩次，以下方為準）

### 修改方式
**只改 mobile media query 內** `.modal-img` 的規則，加上子選擇器覆寫 img 樣式：

```css
/* mobile media query 內 */
.modal-img {
  width: 100%;
  height: 56vw;
}
.modal-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top center;
}
```

全域的 `.modal-img img` 不需要動，mobile 的規則會覆寫。

## 操作範圍
- 只能讀：index.html（禁止直接修改）
- 只能寫：tasks/output_07.md

## 禁止事項
- 不能修改任何 .html / .js / .py 檔案
- 不能 git commit / push
- 不能自行擴大功能範圍

## 輸出格式（寫入 tasks/output_07.md）

### 【插入位置】
找到 `@media (max-width: 600px)` 內的 `.modal-img { width: 100%; height: 240px; }` 這行

### 【程式碼】
修改後的 `.modal-img` 與新增的 `.modal-img img` 規則（在 media query 內）

### 【說明】
（簡述修改內容與效果）

### 【遺留問題】
（無則填「無」）
