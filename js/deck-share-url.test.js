import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildDeckSharePayload, encodeDeckShare, deckShareUrl } from './deck-share-url.js';

// 不裝 lz-string：編碼本身不是這裡要測的事，只要確認有把 payload JSON 交給它
const fakeLz = { compressToEncodedURIComponent: s => `LZ(${s})` };

test('buildDeckSharePayload：名稱走 n、卡片走 c 的 [image_file, count] 陣列', () => {
  const payload = buildDeckSharePayload({
    name: '烏野主力',
    cards: [{ image_file: 'A-1.webp', count: 4 }, { image_file: 'B-1.webp', count: 2 }],
  });
  assert.deepEqual(payload, { n: '烏野主力', c: [['A-1.webp', 4], ['B-1.webp', 2]] });
});

test('buildDeckSharePayload：沒有 count 的舊卡片算 1 張', () => {
  const payload = buildDeckSharePayload({ name: 'x', cards: [{ image_file: 'A-1.webp' }] });
  assert.deepEqual(payload.c, [['A-1.webp', 1]]);
});

test('buildDeckSharePayload：沒有顏色或顏色是空物件時不放 k', () => {
  assert.equal('k' in buildDeckSharePayload({ name: 'x', cards: [] }), false);
  assert.equal('k' in buildDeckSharePayload({ name: 'x', cards: [], colors: {} }), false);
  assert.equal('k' in buildDeckSharePayload({ name: 'x', cards: [], colors: null }), false);
});

test('buildDeckSharePayload：有顏色時原樣放進 k', () => {
  const colors = { 'A-1.webp': { free: 1, receive: 0, set: 0, attack: 2 } };
  assert.deepEqual(buildDeckSharePayload({ name: 'x', cards: [], colors }).k, { ...colors });
});

test('buildDeckSharePayload：cards 缺欄位時回傳空陣列，不丟例外', () => {
  assert.deepEqual(buildDeckSharePayload({ name: 'x' }).c, []);
});

test('encodeDeckShare：把 payload 的 JSON 交給 LZString 壓縮', () => {
  const encoded = encodeDeckShare({ name: 'x', cards: [] }, fakeLz);
  assert.equal(encoded, 'LZ({"n":"x","c":[]})');
});

test('deckShareUrl：相對於呼叫端網址指向 index.html，編碼放在 deck 參數', () => {
  const url = deckShareUrl({ name: 'x', cards: [] }, {
    base: 'https://weilun2022.github.io/haikyuu-cards/ana.html?login=1',
    lz: { compressToEncodedURIComponent: () => 'ENC' },
  });
  assert.equal(url, 'https://weilun2022.github.io/haikyuu-cards/index.html?deck=ENC');
});
