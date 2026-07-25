# 任務 06 輸出：卡片縮圖屬性顯示順序與 Modal 一致

## 【插入位置】
`buildCardEl` 函式內的 `statPairs` 陣列，位於 index.html 第 1736–1739 行

## 【程式碼】

```js
    const statPairs = [
      ['srv', card.srv], ['blk', card.blk], ['rcv', card.rcv],
      ['tos', card.tos], ['atk', card.atk]
    ].filter(([,v]) => v !== null && v !== undefined && v !== '' && v != 0);
```

## 【說明】
將 `statPairs` 陣列的屬性排列順序從 `atk/blk/rcv/tos/srv` 改為 `srv/blk/rcv/tos/atk`，與 Modal 的 `statDefs` 順序一致。

## 【遺留問題】
無
