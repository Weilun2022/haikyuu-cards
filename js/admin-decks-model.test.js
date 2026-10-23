import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  groupByAccount, filterDecks, summarizeDeck, findDeckHits, isAdminUser,
} from './admin-decks-model.js';

const CARDS = {
  'A-1.webp': { card_no: 'A-1', name: '日向 翔陽', name_zh: '日向翔陽', school: '烏野', category_zh: '角色' },
  'A-2.webp': { card_no: 'A-2', name: '影山 飛雄', name_zh: '影山飛雄', school: '烏野', category_zh: '角色' },
  'B-1.webp': { card_no: 'B-1', name: '黒尾 鉄朗', name_zh: '黑尾鐵朗', school: '音駒', category_zh: '角色' },
  'E-1.webp': { card_no: 'E-1', name: 'がんばれ', name_zh: '加油', school: '烏野', category_zh: '事件' },
};

// 模擬 Firestore 文件：{ id, ownerUid, deck:{name,cards}, deleted, clientUpdatedAt }
function doc(uid, id, name, cards, extra = {}) {
  return { id, ownerUid: uid, deck: { id, name, cards }, deleted: false, clientUpdatedAt: 1000, ...extra };
}
const full40 = [{ image_file: 'A-1.webp', count: 20 }, { image_file: 'B-1.webp', count: 20 }];

test('groupByAccount：依 uid 分組，並計算牌組數與最近更新時間', () => {
  const docs = [
    doc('u1', 'd1', '烏野', full40, { clientUpdatedAt: 5 }),
    doc('u1', 'd2', '音駒', full40, { clientUpdatedAt: 9 }),
    doc('u2', 'd3', '稻荷崎', full40),
  ];
  const accounts = groupByAccount(docs);
  const u1 = accounts.find(a => a.uid === 'u1');
  assert.equal(accounts.length, 2);
  assert.equal(u1.decks.length, 2);
  assert.equal(u1.lastUpdated, 9);
  assert.equal(u1.shortId, 'u1');
});

test('groupByAccount：沒有 ownerUid 時從 id 以外的欄位取不到，退回 unknown，不丟例外', () => {
  const accounts = groupByAccount([{ id: 'x', deck: { name: 'a', cards: [] } }]);
  assert.equal(accounts[0].uid, 'unknown');
});

test('張數：count 缺省視為 1，總張數是各卡 count 加總', () => {
  const [a] = groupByAccount([doc('u1', 'd1', 'x', [{ image_file: 'A-1.webp' }, { image_file: 'A-2.webp', count: 3 }])]);
  assert.equal(a.decks[0].total, 4);
});

test('帳號排序：真正牌組（非快速查詢、非空、未刪除）多的排前面', () => {
  const docs = [
    doc('few', 'd1', '甲', full40),
    doc('many', 'd2', '乙', full40), doc('many', 'd3', '丙', full40),
    doc('quick', 'd4', '快速查詢', full40), doc('quick', 'd5', '快速查詢', full40), doc('quick', 'd6', '快速查詢', full40),
  ];
  const accounts = groupByAccount(docs);
  assert.deepEqual(accounts.map(a => a.uid), ['many', 'few', 'quick']);
  assert.equal(accounts[0].realCount, 2);
  assert.equal(accounts[2].realCount, 0);
});

test('帳號統計：legal40Count 只算剛好 40 張的真正牌組', () => {
  const [a] = groupByAccount([
    doc('u', 'd1', '滿', full40),
    doc('u', 'd2', '缺', [{ image_file: 'A-1.webp', count: 10 }]),
    doc('u', 'd3', '空', []),
  ]);
  assert.equal(a.realCount, 2);
  assert.equal(a.legal40Count, 1);
});

test('filterDecks：預設隱藏快速查詢、空牌組、已刪除', () => {
  const [a] = groupByAccount([
    doc('u', 'd1', '正常', full40),
    doc('u', 'd2', '快速查詢', full40),
    doc('u', 'd3', '空', []),
    doc('u', 'd4', '已刪', full40, { deleted: true }),
  ]);
  assert.deepEqual(filterDecks(a.decks).map(d => d.name), ['正常']);
});

test('filterDecks：各旗標可個別打開', () => {
  const [a] = groupByAccount([
    doc('u', 'd1', '正常', full40),
    doc('u', 'd2', '快速查詢', full40),
    doc('u', 'd3', '空', []),
    doc('u', 'd4', '已刪', full40, { deleted: true }),
  ]);
  const names = opts => filterDecks(a.decks, opts).map(d => d.name).sort();
  assert.deepEqual(names({ showQuick: true }), ['快速查詢', '正常'].sort());
  assert.deepEqual(names({ showEmpty: true }), ['正常', '空'].sort());
  assert.deepEqual(names({ showDeleted: true }), ['已刪', '正常'].sort());
});

test('filterDecks：only40 只留剛好 40 張', () => {
  const [a] = groupByAccount([
    doc('u', 'd1', '滿', full40),
    doc('u', 'd2', '缺', [{ image_file: 'A-1.webp', count: 10 }]),
  ]);
  assert.deepEqual(filterDecks(a.decks, { only40: true }).map(d => d.name), ['滿']);
});

test('filterDecks：牌組依最近更新由新到舊排序', () => {
  const [a] = groupByAccount([
    doc('u', 'old', '舊', full40, { clientUpdatedAt: 1 }),
    doc('u', 'new', '新', full40, { clientUpdatedAt: 9 }),
  ]);
  assert.deepEqual(filterDecks(a.decks).map(d => d.name), ['新', '舊']);
});

test('summarizeDeck：依學校與類別統計張數，查無資料的卡另計', () => {
  const s = summarizeDeck({
    cards: [
      { image_file: 'A-1.webp', count: 3 },
      { image_file: 'B-1.webp', count: 2 },
      { image_file: 'E-1.webp', count: 1 },
      { image_file: 'ZZZ.webp', count: 4 },
    ],
  }, CARDS);
  assert.deepEqual(s.bySchool, [{ label: '烏野', count: 4 }, { label: '音駒', count: 2 }]);
  assert.deepEqual(s.byCategory, [{ label: '角色', count: 5 }, { label: '事件', count: 1 }]);
  assert.equal(s.unknown, 4);
});

test('findDeckHits：用中文名找到用了該卡的牌組，並帶出張數與帳號', () => {
  const accounts = groupByAccount([
    doc('u1', 'd1', '甲', [{ image_file: 'A-1.webp', count: 3 }]),
    doc('u2', 'd2', '乙', [{ image_file: 'B-1.webp', count: 2 }]),
  ]);
  const hits = findDeckHits(accounts, '日向', CARDS);
  assert.equal(hits.length, 1);
  assert.deepEqual([hits[0].uid, hits[0].deckId, hits[0].count], ['u1', 'd1', 3]);
});

test('findDeckHits：卡號、日文名都能搜，且忽略空白差異；已刪除與快速查詢不計入', () => {
  const accounts = groupByAccount([
    doc('u1', 'd1', '甲', [{ image_file: 'A-1.webp', count: 1 }]),
    doc('u1', 'd2', '快速查詢', [{ image_file: 'A-1.webp', count: 1 }]),
    doc('u1', 'd3', '已刪', [{ image_file: 'A-1.webp', count: 1 }], { deleted: true }),
  ]);
  assert.equal(findDeckHits(accounts, 'a-1', CARDS).length, 1);
  assert.equal(findDeckHits(accounts, '日向 翔陽', CARDS).length, 1);
  assert.equal(findDeckHits(accounts, '日向　翔陽', CARDS).length, 1);
});

test('findDeckHits：兎／兔 異體字視為同一個字（資料裡是「兎」，使用者常打「兔」）', () => {
  const cards = { 'K-1.webp': { card_no: 'K-1', name: '木兎 光太郎', name_zh: '木兎光太郎', school: '梟谷', category_zh: '角色' } };
  const accounts = groupByAccount([doc('u1', 'd1', '梟谷', [{ image_file: 'K-1.webp', count: 2 }])]);
  assert.equal(findDeckHits(accounts, '木兔', cards).length, 1);
  assert.equal(findDeckHits(accounts, '木兎', cards).length, 1);
});

test('findDeckHits：空字串不回傳任何東西；結果依張數由多到少', () => {
  const accounts = groupByAccount([
    doc('u1', 'd1', '少', [{ image_file: 'A-1.webp', count: 1 }]),
    doc('u2', 'd2', '多', [{ image_file: 'A-1.webp', count: 3 }]),
  ]);
  assert.deepEqual(findDeckHits(accounts, '', CARDS), []);
  assert.deepEqual(findDeckHits(accounts, '日向', CARDS).map(h => h.deckName), ['多', '少']);
});

test('isAdminUser：email 相符且已驗證才算管理者', () => {
  const ADMIN = 'me@example.com';
  assert.equal(isAdminUser({ email: ADMIN, emailVerified: true }, ADMIN), true);
  assert.equal(isAdminUser({ email: ADMIN, emailVerified: false }, ADMIN), false);
  assert.equal(isAdminUser({ email: 'other@example.com', emailVerified: true }, ADMIN), false);
  assert.equal(isAdminUser(null, ADMIN), false);
});
