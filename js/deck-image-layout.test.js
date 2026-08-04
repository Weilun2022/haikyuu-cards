import { test } from 'node:test';
import assert from 'node:assert/strict';
import { computeDeckImageLayout } from './deck-image-layout.js';

const LAYOUT = { cols: 8, cardW: 100, cardH: 140, gap: 10, pad: 20, headH: 118, footH: 34 };

test('0 張卡（空牌組）：畫布仍是完整寬度、0 列、無座標', () => {
  const result = computeDeckImageLayout(0, LAYOUT);
  assert.deepEqual(result, { width: 910, height: 192, rows: 0, positions: [] });
});

test('1~7 張卡：第一列不滿 8 欄，仍固定 8 欄寬度、1 列', () => {
  const result = computeDeckImageLayout(7, LAYOUT);
  assert.equal(result.width, 910);
  assert.equal(result.height, 332);
  assert.equal(result.rows, 1);
  assert.deepEqual(result.positions, [
    { x: 20, y: 138 },
    { x: 130, y: 138 },
    { x: 240, y: 138 },
    { x: 350, y: 138 },
    { x: 460, y: 138 },
    { x: 570, y: 138 },
    { x: 680, y: 138 },
  ]);
});

test('剛好 8 張：整除，1 列無殘列', () => {
  const result = computeDeckImageLayout(8, LAYOUT);
  assert.equal(result.rows, 1);
  assert.equal(result.height, 332);
  assert.equal(result.positions.length, 8);
  assert.deepEqual(result.positions[7], { x: 790, y: 138 });
});

test('剛好 16 張：整除，2 列無殘列', () => {
  const result = computeDeckImageLayout(16, LAYOUT);
  assert.equal(result.rows, 2);
  assert.equal(result.width, 910);
  assert.equal(result.height, 482);
  assert.equal(result.positions.length, 16);
  assert.deepEqual(result.positions[8], { x: 20, y: 288 });
  assert.deepEqual(result.positions[15], { x: 790, y: 288 });
});

test('40 張（滿版牌組上限）：5 列整除', () => {
  const result = computeDeckImageLayout(40, LAYOUT);
  assert.equal(result.rows, 5);
  assert.equal(result.width, 910);
  assert.equal(result.height, 932);
  assert.equal(result.positions.length, 40);
  assert.deepEqual(result.positions[39], { x: 790, y: 738 });
});

test('39 張：非 8 倍數邊界，最後一列缺 1 格', () => {
  const result = computeDeckImageLayout(39, LAYOUT);
  assert.equal(result.rows, 5);
  assert.equal(result.height, 932);
  assert.equal(result.positions.length, 39);
  assert.deepEqual(result.positions[38], { x: 680, y: 738 });
});

test('座標公式與現有 drawDeckCanvas() 手算邏輯一致：PAD + col*(CARD_W+GAP)、HEAD_H + PAD + row*(CARD_H+GAP)', () => {
  const result = computeDeckImageLayout(10, LAYOUT);
  const { cardW, cardH, gap, pad, headH } = LAYOUT;
  result.positions.forEach((pos, i) => {
    const col = i % LAYOUT.cols;
    const row = Math.floor(i / LAYOUT.cols);
    assert.equal(pos.x, pad + col * (cardW + gap));
    assert.equal(pos.y, headH + pad + row * (cardH + gap));
  });
});
