# 任務 06：卡片縮圖屬性顯示順序與 Modal 一致

## 背景
卡片 grid 縮圖的數值顯示順序（atk/blk/rcv/tos/srv）與點開後 Modal 的順序（srv/blk/rcv/tos/atk）不同。
產品決策：兩者統一，縮圖改成跟 Modal 一樣的順序。

## 目標
1. 卡片縮圖的數值顯示順序改為：srv → blk → rcv → tos → atk

## 技術細節

### 現有 JS（`buildCardEl` 函式，約 line 1734–1744）
```js
let statsHtml = '';
if (card.category === 'CHARACTER') {
  const statPairs = [
    ['atk', card.atk], ['blk', card.blk], ['rcv', card.rcv],
    ['tos', card.tos], ['srv', card.srv]
  ].filter(([,v]) => v !== null && v !== undefined && v !== '' && v != 0);
  if (statPairs.length) {
    statsHtml = `<div class="card-stats">${statPairs.map(([k,v]) =>
      `<div class="stat stat-${k}">${STAT_LABELS[k]}<b>${v}</b></div>`
    ).join('')}</div>`;
  }
}
```

### Modal 的順序（`openModal` 函式，約 line 1865–1869）
```js
const statDefs = [
  ['srv', '發球', '#EAB308'], ['blk', '攔網', '#1C1C1C'],
  ['rcv', '接球', '#2563EB'], ['tos', '舉球', '#16A34A'],
  ['atk', '攻擊', '#DC2626']
];
```

### 修改重點
只需把 `statPairs` 陣列的順序從 `atk/blk/rcv/tos/srv` 改為 `srv/blk/rcv/tos/atk`

## 操作範圍
- 只能讀：index.html（禁止直接修改）
- 只能寫：tasks/output_06.md

## 禁止事項
- 不能修改任何 .html / .js / .py 檔案
- 不能 git commit / push
- 不能自行擴大功能範圍

## 輸出格式（寫入 tasks/output_06.md）

### 【插入位置】
找到 `buildCardEl` 函式內的 `statPairs` 陣列（約 line 1736）

### 【程式碼】
修改後的完整 `statPairs` 陣列（4 行）

### 【說明】
（一句說明改了什麼）

### 【遺留問題】
（無則填「無」）
