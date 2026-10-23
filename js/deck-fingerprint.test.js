import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { serializeDeck, deckFingerprint, sha1Hex } from './deck-fingerprint.js';

// 這些牌表直接內嵌，不從 deck_health/ 讀檔——指紋規格的測試向量不該依賴另一條分支的檔案路徑
// （計畫 §1.3）。四副都是研究端 deck_health/ 的實際牌表，雜湊值由 Python 端與 JS 端各自獨立驗算吻合。
const VECTORS = [
  {
    name: '規格範例（兩種卡）',
    deck: { 'HV-P01-001': 3, 'HV-P01-002': 2 },
    serialized: '[["HV-P01-001",3],["HV-P01-002",2]]',
    sha1: '75deb4dd22372e7b32fac38eef145c9e305ea344',
  },
  {
    name: 'ina_v4b 40張/12種',
    deck: {
      'HV-P02-022': 4, 'HV-P02-024': 3, 'HV-P02-034': 3, 'HV-P03-046': 3,
      'HV-D03-004': 4, 'HV-P02-077': 5, 'HV-P03-021': 3, 'HV-D03-002': 3,
      'HV-P02-020': 3, 'HV-P02-084': 2, 'HV-P02-087': 6, 'HV-P02-016': 1,
    },
    sha1: 'b2ab9432cf20d535ff3a383e7b58913cc17721db',
  },
  {
    name: 'deck.json 40張/20種',
    deck: {
      'HV-P02-001': 3, 'HV-P01-013': 2, 'HV-D01-005': 2, 'HV-P01-004': 2,
      'HV-P01-011': 2, 'HV-P03-046': 3, 'HV-PR-022': 2, 'HV-D01-009': 1,
      'HV-P01-006': 5, 'HV-P02-060': 3, 'HV-P03-047': 1, 'HV-P01-002': 3,
      'HV-P02-057': 1, 'HV-PR-027': 1, 'HVBP-001': 1, 'HV-D01-012': 2,
      'HV-P01-074': 1, 'HV-P01-078': 2, 'HV-P02-083': 1, 'HV-P03-086': 2,
    },
    sha1: '8426025b5d97b70838d4b628494b2c4d2ac16b27',
  },
  {
    name: 'fuku_op8_v2 40張/12種',
    deck: {
      'HV-P01-051': 3, 'HV-P01-050': 3, 'HV-PR-047': 3, 'HV-P03-062': 4,
      'HV-P01-045': 4, 'HV-P01-049': 4, 'HV-P01-043': 4, 'HV-P01-091': 5,
      'HV-PR-031': 2, 'HV-P01-046': 3, 'HV-P01-044': 4, 'HV-P02-067': 1,
    },
    sha1: '9d754d3cea932806efc2a7ebf87caf5e83ba20a7',
  },
  {
    name: 'shira_final 40張/15種',
    deck: {
      'HV-P03-068': 2, 'HV-P02-049': 2, 'HV-P02-047': 5, 'HV-P02-053': 5,
      'HV-P03-071': 2, 'HV-P02-050': 5, 'HV-P02-055': 3, 'HV-P03-072': 2,
      'HV-P02-046': 4, 'HV-P02-094': 2, 'HV-P02-096': 1, 'HV-P02-097': 3,
      'HV-P03-090': 1, 'HV-P03-099': 1, 'HV-P03-067': 2,
    },
    sha1: '7705ed174e05eb0d123184d31df55799f5b386d1',
  },
];

for (const v of VECTORS) {
  test(`指紋測試向量：${v.name}`, async () => {
    const ser = serializeDeck(v.deck);
    if (v.serialized) assert.equal(ser, v.serialized);
    // node:crypto 當獨立比對實作：serializeDeck 的輸出餵進去要得到規格記錄的雜湊
    assert.equal(createHash('sha1').update(ser, 'utf8').digest('hex'), v.sha1);
    // 實際對外的 API（WebCrypto，瀏覽器與 Node 同一條路徑）要給出同一個值
    assert.equal(await deckFingerprint(v.deck), v.sha1);
  });
}

test('serializeDeck：卡號用固定字元升冪排序，不依賴輸入順序或物件鍵順序', () => {
  const a = serializeDeck({ 'HV-P02-001': 1, 'HV-P01-002': 2, 'HV-D01-005': 3 });
  const b = serializeDeck({ 'HV-D01-005': 3, 'HV-P01-002': 2, 'HV-P02-001': 1 });
  assert.equal(a, b);
  assert.equal(a, '[["HV-D01-005",3],["HV-P01-002",2],["HV-P02-001",1]]');
});

test('serializeDeck：排序用預設字元序，不是 localeCompare', () => {
  // localeCompare 在部分 locale 會把 '-' 當可忽略字元，讓 'HV-P1' 排到 'HV-PR' 之後；
  // 預設字元序比的是 code unit，'1'(0x31) < 'R'(0x52)。
  const ser = serializeDeck({ 'HV-PR-001': 1, 'HV-P1-001': 1 });
  assert.equal(ser, '[["HV-P1-001",1],["HV-PR-001",1]]');
});

test('serializeDeck：同卡號的複本先合併相加（陣列輸入）', () => {
  const ser = serializeDeck([
    { card_no: 'HV-P01-002', count: 2 },
    { card_no: 'HV-P01-001', count: 1 },
    { card_no: 'HV-P01-002', count: 1 },
  ]);
  assert.equal(ser, '[["HV-P01-001",1],["HV-P01-002",3]]');
});

test('serializeDeck：Map 也接受（牌組向量就是 Map）', () => {
  assert.equal(serializeDeck(new Map([['HV-P01-002', 2], ['HV-P01-001', 3]])),
    '[["HV-P01-001",3],["HV-P01-002",2]]');
});

test('serializeDeck：卡號不改大小寫、不移除前綴', () => {
  assert.equal(serializeDeck({ 'hv-p01-001': 1 }), '[["hv-p01-001",1]]');
});

test('serializeDeck：零張移除，整副零張得到空陣列', () => {
  assert.equal(serializeDeck({ 'HV-P01-001': 0, 'HV-P01-002': 2 }), '[["HV-P01-002",2]]');
  assert.equal(serializeDeck({ 'HV-P01-001': 0 }), '[]');
});

test('serializeDeck：負數與小數報錯，不默默四捨五入', () => {
  assert.throws(() => serializeDeck({ 'HV-P01-001': -1 }), /張數/);
  assert.throws(() => serializeDeck({ 'HV-P01-001': 2.5 }), /張數/);
  assert.throws(() => serializeDeck({ 'HV-P01-001': NaN }), /張數/);
  assert.throws(() => serializeDeck({ 'HV-P01-001': '3' }), /張數/);
});

test('serializeDeck：負數不會被同卡號的正數抵銷掉，照樣報錯', () => {
  assert.throws(() => serializeDeck([
    { card_no: 'HV-P01-001', count: 2 },
    { card_no: 'HV-P01-001', count: -2 },
  ]), /張數/);
});

test('serializeDeck：卡號必須是非空字串——查不到權威卡號的牌組不給指紋', () => {
  assert.throws(() => serializeDeck({ '': 3 }), /卡號/);
  assert.throws(() => serializeDeck([{ card_no: null, count: 3 }]), /卡號/);
});

test('serializeDeck：張數差一張就是不同的序列化字串（指紋對張數敏感）', () => {
  assert.notEqual(serializeDeck({ 'HV-P01-001': 3 }), serializeDeck({ 'HV-P01-001': 4 }));
});

test('sha1Hex：輸出小寫十六進位 40 字元，且與 node:crypto 一致', async () => {
  const hex = await sha1Hex('[]');
  assert.match(hex, /^[0-9a-f]{40}$/);
  assert.equal(hex, createHash('sha1').update('[]', 'utf8').digest('hex'));
});

test('sha1Hex：對 UTF-8 位元組計算（非 ASCII 也要跟 node:crypto 吻合）', async () => {
  const text = '烏野';
  assert.equal(await sha1Hex(text), createHash('sha1').update(text, 'utf8').digest('hex'));
});
