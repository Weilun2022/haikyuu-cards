// 牌組轉圖片：卡格幾何計算純函式，不碰 DOM，見 issue #94。

/**
 * 給定卡片總數與固定版面常數，算出畫布總寬高、列數、以及每個卡格索引
 * 對應的 x/y 座標。固定欄數（不論卡片總數多寡皆同一寬度版面），供
 * `drawDeckCanvas()` 的卡格版面（issue #96）呼叫。
 *
 * @param {number} cardCount 卡片總數（含展開後的每一份，例如 count>1 的卡只算一格）
 * @param {{cols: number, cardW: number, cardH: number, gap: number, pad: number, headH: number, footH: number}} layout
 * @returns {{width: number, height: number, rows: number, positions: Array<{x: number, y: number}>}}
 */
export function computeDeckImageLayout(cardCount, layout) {
  const { cols, cardW, cardH, gap, pad, headH, footH } = layout;

  const rows = Math.ceil(cardCount / cols);
  const cardAreaW = cols * (cardW + gap) - gap;
  const cardAreaH = rows > 0 ? rows * (cardH + gap) - gap : 0;

  const width = pad * 2 + cardAreaW;
  const height = headH + pad + cardAreaH + pad + footH;

  const positions = [];
  for (let i = 0; i < cardCount; i++) {
    const col = i % cols;
    const row = Math.floor(i / cols);
    positions.push({
      x: pad + col * (cardW + gap),
      y: headH + pad + row * (cardH + gap),
    });
  }

  return { width, height, rows, positions };
}
