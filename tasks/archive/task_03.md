# 任務 03：移除 QR Code 和牌組轉圖片按鈕的紫色背景

## 背景
底部牌組面板有兩顆按鈕（QR Code 快速分享、牌組轉圖片）目前套用了 `tray-btn primary` class，
導致出現紫色背景色，視覺上與其他按鈕不一致。使用者希望這兩顆按鈕外觀與一般按鈕相同（無填色背景）。

## 目標
1. 移除 `deck-share-btn` 和 `deck-export-img-btn` 的 `primary` class
2. 兩顆按鈕外觀與其他 `tray-btn`（無 primary）一致：透明背景 + 邊框樣式

## 技術細節

**要修改的兩行（index.html）：**

第 1083 行（原始）：
```html
<button class="tray-btn primary" id="deck-share-btn" style="width:100%">📲 QR Code 快速分享</button>
```
改為：
```html
<button class="tray-btn" id="deck-share-btn" style="width:100%">📲 QR Code 快速分享</button>
```

第 1085 行（原始）：
```html
<button class="tray-btn primary" id="deck-export-img-btn" style="flex:1">🖼️ 牌組轉圖片</button>
```
改為：
```html
<button class="tray-btn" id="deck-export-img-btn" style="flex:1">🖼️ 牌組轉圖片</button>
```

**CSS 參考（index.html 第 605〜619 行）：**
- `.tray-btn`：透明背景、白色邊框、白色文字
- `.tray-btn.primary`：紫色填滿背景（`var(--accent)`）← 要移除

## 操作範圍
- 可直接修改：`index.html`
- 不需建立其他檔案

## 禁止事項
- 不能修改 CSS 定義本身（`.tray-btn` 或 `.tray-btn.primary` 的 class 定義不動）
- 只改這兩顆按鈕的 class attribute，不改其他按鈕
- 不能 git commit / push
- 不能自行擴大功能範圍

## 回報格式（完成後回報給中樞）

```
【完成項目】移除 deck-share-btn 和 deck-export-img-btn 的 primary class
【結果】成功 / 失敗 / 部分完成
【遺留問題】無 / 有（說明）
【待中樞決策】無 / 有（說明）
```
