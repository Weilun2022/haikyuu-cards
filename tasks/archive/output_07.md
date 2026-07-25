# 任務 07 輸出：Mobile Modal 圖片填滿版面優化

## 【插入位置】

`index.html` 第 527 行，`@media (max-width: 600px)` 內的：

```css
.modal-img { width: 100%; height: 240px; }
```

將此行替換為以下兩段規則：

---

## 【程式碼】

```css
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

完整 context（第 525–528 行修改後樣貌）：

```css
@media (max-width: 600px) {
  .modal { flex-direction: column; }
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
  .grid-container { grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); gap: 8px; }
  ...
```

---

## 【說明】

1. **`height: 240px` → `height: 56vw`**：圖片區高度從固定值改為視窗寬度比例，在 375px 寬手機約 210px，在 414px 約 232px，整體比原本略小且隨螢幕自適應。

2. **新增 `.modal-img img` 規則（media query 內）**：覆寫全域的 `width: 100%; object-fit: cover`，加上：
   - `height: 100%`：讓 img 高度撐滿 `.modal-img` 容器，使 `object-fit: cover` 能正確裁切填滿，消除下方空白。
   - `object-position: top center`：裁切時優先保留圖片上方（角色臉部/頭部區域），避免被截掉。

3. **全域 `.modal-img img` 不動**：Desktop 行為維持不變，僅 mobile（≤600px）套用覆寫規則。

4. **Lightbox 功能不受影響**：`cursor: pointer` 與點擊事件綁定在 `#modal-img`，本次修改未觸及任何 JS 邏輯。

---

## 【遺留問題】

無
