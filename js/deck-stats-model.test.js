import { test } from 'node:test';
import assert from 'node:assert/strict';
import { STATS_CARDS } from './deck-stats-fixtures.js';
import {
  indexCards, normalizeDeck, selectCohort, similarity, groupVersions,
  describeDeck, aggregate, crossAccountSimilar,
  QUICK_DECK_ID, SIMILARITY_THRESHOLD, MIN_ACCOUNTS_FOR_CONFIDENCE,
} from './deck-stats-model.js';

const INDEX = indexCards(STATS_CARDS);
const NOW = 1_800_000_000_000;

// Firestore 文件形狀（對齊 cloud-sync.js 的 deckDocPayload）
function doc(uid, id, name, cards, extra = {}) {
  return { id, ownerUid: uid, deck: { id, name, cards }, deleted: false, clientUpdatedAt: NOW - 1000, ...extra };
}
const card = (image_file, count, card_no) => ({ image_file, card_no: card_no ?? INDEX.byImage.get(image_file)?.card_no ?? '', count });

// 36 角色 + 4 事件 = 40 張合法牌組
function legalDeck(uid, id, name, extra = {}) {
  return doc(uid, id, name, [
    card('K1-H.webp', 12), card('K2-H.webp', 12), card('K3-H.webp', 12), card('E1-H.webp', 4),
  ], extra);
}
const norm = (d, opts = {}) => normalizeDeck(d, INDEX, { now: NOW, ...opts });

// ── indexCards ─────────────────────────────────────────────────────────
test('indexCards：image_file 與 card_no 兩個索引都建起來，同卡號多版本合成一筆', () => {
  assert.equal(INDEX.byImage.get('K1-I.webp').card_no, 'HV-T01-001');
  assert.equal(INDEX.byCardNo.get('HV-T01-001').name_zh, '甲一');
  assert.equal(INDEX.byImage.size, STATS_CARDS.length);
  assert.equal(INDEX.byCardNo.size, STATS_CARDS.length - 1);
  assert.deepEqual(INDEX.conflicts, []);
});

test('indexCards：同一個 card_no 的資料互相衝突時列進 conflicts，不默默挑一筆', () => {
  const ix = indexCards([
    ...STATS_CARDS,
    { image_file: 'K1-S.webp', card_no: 'HV-T01-001', name: '甲一', name_zh: '甲一', category: 'CHARACTER',
      category_zh: '角色', school: '音駒', school_tags: ['音駒'], srv: 2, blk: 3, rcv: 4, tos: 0, atk: 2 },
  ]);
  assert.deepEqual(ix.conflicts.map(c => c.card_no), ['HV-T01-001']);
  assert.ok(ix.conflicts[0].fields.includes('school_tags'));
});

// ── normalizeDeck ──────────────────────────────────────────────────────
test('normalizeDeck：向量以 card_no 為鍵，同卡號的不同稀有度版本相加', () => {
  const d = norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 2), card('K1-I.webp', 3)]));
  assert.deepEqual([...d.vector], [['HV-T01-001', 5]]);
  assert.equal(d.total, 5);
  assert.equal(d.kinds, 1);
});

test('normalizeDeck：角色／事件／未知卡的張數分開算', () => {
  const d = norm(doc('u1', 'd1', '甲', [
    card('K1-H.webp', 3), card('E1-H.webp', 2), card('ZZZ.webp', 4, 'HV-X'),
  ]));
  assert.equal(d.roleCopies, 3);
  assert.equal(d.eventCopies, 2);
  assert.equal(d.unknownCopies, 4);
  assert.equal(d.total, 9);
  assert.equal(d.vector.has('HV-X'), false);
});

test('normalizeDeck：缺 count 的舊資料視為 1 張，不算問題', () => {
  const d = norm(doc('u1', 'd1', '甲', [{ image_file: 'K1-H.webp', card_no: 'HV-T01-001' }]));
  assert.equal(d.total, 1);
  assert.deepEqual(d.issues, []);
});

test('normalizeDeck：查不到卡片資料的卡列 unknown_card 並記下 image_file', () => {
  const d = norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 1), card('ZZZ.webp', 2, 'HV-X')]));
  assert.deepEqual(d.issues.find(i => i.code === 'unknown_card').items, ['ZZZ.webp']);
});

test('normalizeDeck：非正整數張數列 bad_count，該張不進向量也不進總數', () => {
  const d = norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 3), card('K2-H.webp', 2.5), card('K3-H.webp', -1)]));
  assert.deepEqual(d.issues.find(i => i.code === 'bad_count').items.sort(), ['K2-H.webp', 'K3-H.webp']);
  assert.equal(d.total, 3);
  assert.equal(d.vector.size, 1);
});

test('normalizeDeck：牌組裡寫的 card_no 跟權威卡庫不符時標記，但以卡庫為準', () => {
  const d = norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 3, 'HV-WRONG-999')]));
  assert.deepEqual([...d.vector], [['HV-T01-001', 3]]);
  assert.deepEqual(d.issues.find(i => i.code === 'card_no_mismatch').items, ['K1-H.webp']);
});

test('normalizeDeck：五維是 null 的角色卡列 missing_stats', () => {
  const d = norm(doc('u1', 'd1', '甲', [card('X1-H.webp', 2)]));
  assert.deepEqual(d.issues.find(i => i.code === 'missing_stats').items, ['X1-H.webp']);
});

test('normalizeDeck：用途色張數超過該卡張數時列 color_overflow', () => {
  const d = norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 2)], {
    color: { 'K1-H.webp': { free: 0, receive: 2, set: 1, attack: 0 } },
  }));
  assert.deepEqual(d.issues.find(i => i.code === 'color_overflow').items, ['K1-H.webp']);
});

test('normalizeDeck：顏色張數不符只丟掉那張卡的用途色，張數照算進未指定', () => {
  const d = norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 2), card('K2-H.webp', 3)], {
    color: { 'K1-H.webp': { receive: 2, set: 1 }, 'K2-H.webp': { attack: 3 } },
  }));
  // 壞掉的 K1 兩張進未指定，沒壞的 K2 照常算
  assert.deepEqual(d.colorUse, { free: 0, receive: 0, set: 0, attack: 3, unassigned: 2, event: 0 });
  // 堆疊條的總和必須等於牌組張數，否則整條圖不能看
  assert.equal(Object.values(d.colorUse).reduce((s, n) => s + n, 0), d.total);
});

test('normalizeDeck：用途色統計含未指定與事件兩欄，事件卡不吃用途色', () => {
  const d = norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 4), card('E1-H.webp', 3)], {
    color: { 'K1-H.webp': { receive: 1, attack: 2 } },
  }));
  assert.deepEqual(d.colorUse, { free: 0, receive: 1, set: 0, attack: 2, unassigned: 1, event: 3 });
});

test('normalizeDeck：時間取 clientUpdatedAt，缺的時候退回 updatedAt.toMillis()', () => {
  assert.equal(norm(doc('u1', 'd1', '甲', [], { clientUpdatedAt: 123 })).updatedMs, 123);
  const d = norm({ id: 'd2', ownerUid: 'u1', deck: { name: '乙', cards: [] }, updatedAt: { toMillis: () => 456 } });
  assert.equal(d.updatedMs, 456);
});

test('normalizeDeck：沒有時間或時間在未來列 invalid_time', () => {
  assert.ok(norm(doc('u1', 'd1', '甲', [], { clientUpdatedAt: null })).issues.some(i => i.code === 'invalid_time'));
  assert.ok(norm(doc('u1', 'd1', '甲', [], { clientUpdatedAt: NOW + 86_400_000 })).issues.some(i => i.code === 'invalid_time'));
  assert.deepEqual(norm(legalDeck('u1', 'd1', '甲')).issues, []);
});

// ── selectCohort ───────────────────────────────────────────────────────
test('selectCohort：合法牌組進主樣本，排除原因逐筆保留', () => {
  const decks = [
    legalDeck('u1', 'd1', '正常'),
    legalDeck('u1', QUICK_DECK_ID, '快速查詢'),
    legalDeck('u1', 'd3', '已刪', { deleted: true }),
    doc('u2', 'd4', '只有 39 張', [card('K1-H.webp', 35), card('E1-H.webp', 4)]),
    doc('u2', 'd5', '事件 9 張', [card('K1-H.webp', 31), card('E1-H.webp', 5), card('E2-H.webp', 4)]),
    doc('u2', 'd6', '有未知卡', [card('K1-H.webp', 36), card('ZZZ.webp', 4, 'HV-X')]),
  ].map(d => norm(d));
  const { included, excluded } = selectCohort(decks);
  assert.deepEqual(included.map(d => d.id), ['d1']);
  const reasons = Object.fromEntries(excluded.map(e => [e.deck.id, e.reasons]));
  assert.deepEqual(reasons[QUICK_DECK_ID], ['quick_deck']);
  assert.deepEqual(reasons.d3, ['deleted']);
  assert.deepEqual(reasons.d4, ['not_40']);
  assert.deepEqual(reasons.d5, ['too_many_events']);
  // 未知卡仍算進 40 張（牌組宣稱的張數就是 40），所以 d6 只踩「卡片可辨識」這一條
  assert.deepEqual(reasons.d6, ['unidentifiable']);
});

test('selectCohort：漏斗逐階段給牌組數與帳號數，供圖表標分母', () => {
  const decks = [
    legalDeck('u1', 'd1', '正常'), legalDeck('u1', QUICK_DECK_ID, '快速查詢'),
    legalDeck('u2', QUICK_DECK_ID, '快速查詢'), legalDeck('u3', 'd3', '已刪', { deleted: true }),
  ].map(d => norm(d));
  const { funnel } = selectCohort(decks);
  assert.deepEqual(funnel.map(s => [s.key, s.decks, s.accounts]), [
    ['all', 4, 3],
    ['not_deleted', 3, 2],
    ['not_quick', 1, 1],
    ['identifiable', 1, 1],
    ['size_40', 1, 1],
    ['events_8', 1, 1],
  ]);
});

// ── similarity ─────────────────────────────────────────────────────────
test('similarity：加權 Jaccard，相同牌表是 1', () => {
  assert.equal(similarity(norm(legalDeck('u1', 'd1', '甲')), norm(legalDeck('u2', 'd2', '乙'))), 1);
});

test('similarity：40 張換 2 張 ≈ 0.905、換 3 張 ≈ 0.860（計畫 §1.5 的參考點）', () => {
  const base = norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 20), card('K2-H.webp', 20)]));
  const swap2 = norm(doc('u1', 'd2', '乙', [card('K1-H.webp', 18), card('K2-H.webp', 20), card('K3-H.webp', 2)]));
  const swap3 = norm(doc('u1', 'd3', '丙', [card('K1-H.webp', 17), card('K2-H.webp', 20), card('K3-H.webp', 3)]));
  assert.equal(similarity(base, swap2).toFixed(3), '0.905');
  assert.equal(similarity(base, swap3).toFixed(3), '0.860');
});

test('similarity：完全不重疊是 0；空牌組不除以零', () => {
  const a = norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 4)]));
  const b = norm(doc('u1', 'd2', '乙', [card('K2-H.webp', 4)]));
  const empty = norm(doc('u1', 'd3', '空', []));
  assert.equal(similarity(a, b), 0);
  assert.equal(similarity(empty, a), 0);
  assert.equal(similarity(empty, empty), 0);
});

test('similarity：Map 直接傳也可以（研究端牌表沒有 Firestore 文件外殼）', () => {
  const a = new Map([['HV-T01-001', 20], ['HV-T01-002', 20]]);
  const b = new Map([['HV-T01-001', 20], ['HV-T01-002', 18], ['HV-T01-003', 2]]);
  assert.equal(similarity(a, b).toFixed(3), '0.905');
});

test('similarity：對稱', () => {
  const a = norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 3), card('K2-H.webp', 1)]));
  const b = norm(doc('u1', 'd2', '乙', [card('K1-H.webp', 1), card('K3-H.webp', 2)]));
  assert.equal(similarity(a, b), similarity(b, a));
  assert.equal(SIMILARITY_THRESHOLD, 0.9);
  assert.equal(MIN_ACCOUNTS_FOR_CONFIDENCE, 5);
});

// ── groupVersions ──────────────────────────────────────────────────────
// base~v2 = 0.905、v2~v3 = 0.905、base~v3 = 0.818：單一連結會把三副串成一群，
// 完全連結只會併 base 與 v2（計畫 §1.5 刻意選完全連結就是為了避免相似鏈）。
const versionSet = () => [
  norm(doc('u1', 'base', '基礎', [card('K1-H.webp', 20), card('K2-H.webp', 20)], { clientUpdatedAt: 100 })),
  norm(doc('u1', 'v2', '換兩張', [card('K1-H.webp', 18), card('K2-H.webp', 20), card('K3-H.webp', 2)], { clientUpdatedAt: 300 })),
  norm(doc('u1', 'v3', '換四張', [card('K1-H.webp', 16), card('K2-H.webp', 20), card('K3-H.webp', 4)], { clientUpdatedAt: 200 })),
];

test('groupVersions：完全連結聚群，不讓相似鏈串成一大群', () => {
  const groups = groupVersions(versionSet());
  assert.equal(groups.length, 2);
  assert.deepEqual(groups.map(g => g.decks.map(d => d.id).sort()).sort(), [['base', 'v2'], ['v3']]);
});

test('groupVersions：每群留最新更新時間者當代表，權重是 1/群數', () => {
  const groups = groupVersions(versionSet());
  const pair = groups.find(g => g.decks.length === 2);
  assert.equal(pair.representative.id, 'v2');
  assert.equal(pair.weight, 0.5);
  assert.equal(groups.reduce((s, g) => s + g.weight, 0), 1);
});

test('groupVersions：完全相同的牌表一定併在同一群', () => {
  const groups = groupVersions([
    norm(legalDeck('u1', 'a', '甲', { clientUpdatedAt: 100 })),
    norm(legalDeck('u1', 'b', '乙', { clientUpdatedAt: 200 })),
  ]);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].weight, 1);
  assert.equal(groups[0].representative.id, 'b');
});

test('groupVersions：代表優先挑時間有效的那副，時間無效的不當代表', () => {
  const groups = groupVersions([
    norm(legalDeck('u1', 'good', '時間正常', { clientUpdatedAt: 100 })),
    norm(legalDeck('u1', 'future', '時間在未來', { clientUpdatedAt: NOW + 86_400_000 })),
  ]);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].representative.id, 'good');
});

test('groupVersions：單副牌是一群、空輸入回空陣列', () => {
  const [only] = groupVersions([norm(legalDeck('u1', 'a', '甲'))]);
  assert.equal(only.weight, 1);
  assert.deepEqual(groupVersions([]), []);
});

// ── describeDeck ───────────────────────────────────────────────────────
test('describeDeck：學校分數 n/k，只算角色卡，事件卡不計', () => {
  // M1 雙掛烏野＋音駒 ×12 → 兩校各 6；K1 烏野 ×24 → 烏野 24；事件 4 張不計
  const d = describeDeck(norm(doc('u1', 'd1', '甲', [
    card('K1-H.webp', 24), card('M1-H.webp', 12), card('E1-H.webp', 4),
  ])), INDEX);
  assert.equal(d.schools.roleCopies, 36);
  assert.deepEqual(d.schools.dist, [
    { school: '烏野', copies: 30, share: 30 / 36 },
    { school: '音駒', copies: 6, share: 6 / 36 },
  ]);
});

test('describeDeck：最高 ≥60% 且領先第二名 ≥20 個百分點才判主校', () => {
  const main = v => describeDeck(norm(doc('u1', 'd', '甲', v)), INDEX).mainSchool;
  // 24/36 = 66.7%，領先 33.3 個百分點 → 主校
  assert.deepEqual(main([card('K1-H.webp', 24), card('N1-H.webp', 12)]),
    { type: 'single', school: '烏野', schools: ['烏野'], share: 24 / 36, lead: 12 / 36 });
  // 21/36 = 58.3% < 60% → 混合，並列前兩校
  assert.deepEqual(main([card('K1-H.webp', 21), card('N1-H.webp', 15)]),
    { type: 'mixed', school: null, schools: ['烏野', '音駒'], share: 21 / 36, lead: 6 / 36 });
});

test('describeDeck：剛好 60%／領先剛好 20 個百分點算主校（門檻含等於）', () => {
  // 24 烏野 ＋ 16 音駒 = 40 角色：60% vs 40%，領先 20 個百分點
  const r = describeDeck(norm(doc('u1', 'd', '甲', [card('K1-H.webp', 24), card('N1-H.webp', 16)])), INDEX);
  assert.equal(r.mainSchool.type, 'single');
  assert.equal(r.mainSchool.school, '烏野');
});

test('describeDeck：未知歸屬另報、不重分配——各校比例合計會小於 1', () => {
  const d = describeDeck(norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 30), card('U1-H.webp', 6)])), INDEX);
  assert.equal(d.schools.unknownAttributionCopies, 6);
  assert.equal(d.schools.dist.reduce((s, x) => s + x.share, 0), 30 / 36);
  assert.equal(d.mainSchool.school, '烏野');
});

test('describeDeck：整副都沒有學校標記時主校是 unknown，不硬挑一個', () => {
  const d = describeDeck(norm(doc('u1', 'd1', '甲', [card('U1-H.webp', 36)])), INDEX);
  assert.deepEqual(d.schools.dist, []);
  assert.equal(d.mainSchool.type, 'unknown');
  assert.equal(d.mainSchool.school, null);
});

test('describeDeck：ユース 與 疑似ユース 分欄，不合併成同一個標記', () => {
  const d = describeDeck(norm(doc('u1', 'd1', '甲', [card('Y1-H.webp', 20), card('Y2-H.webp', 16)])), INDEX);
  assert.deepEqual(d.schools.youth, { 'ユース': 20, '疑似ユース': 16 });
  assert.deepEqual(d.schools.dist.map(x => x.school), ['ユース', '疑似ユース']);
  assert.equal(d.mainSchool.type, 'mixed');
});

test('describeDeck：網站側才有的 町内会 標記照實呈現，不併進未知', () => {
  const d = describeDeck(norm(doc('u1', 'd1', '甲', [card('C1-H.webp', 36)])), INDEX);
  assert.deepEqual(d.schools.dist, [{ school: '町内会', copies: 36, share: 1 }]);
  assert.equal(d.schools.unknownAttributionCopies, 0);
});

test('describeDeck：五維逐張統計總和／平均／分位數／逐值張數', () => {
  // K1 srv=2 ×2、K2 srv=1 ×1、K3 srv=3 ×1 → 觀測值 [1,2,2,3]
  const d = describeDeck(norm(doc('u1', 'd1', '甲', [
    card('K1-H.webp', 2), card('K2-H.webp', 1), card('K3-H.webp', 1),
  ])), INDEX);
  assert.equal(d.stats5.srv.sum, 8);
  assert.equal(d.stats5.srv.mean, 2);
  assert.equal(d.stats5.srv.knownCopies, 4);
  assert.deepEqual(d.stats5.srv.quantiles, { p25: 1, p50: 2, p75: 2 });
  assert.deepEqual(d.stats5.srv.histogram, [
    { value: 1, copies: 1 }, { value: 2, copies: 2 }, { value: 3, copies: 1 },
  ]);
});

test('describeDeck：五維缺值不當 0，另計 unknownCopies', () => {
  const d = describeDeck(norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 2), card('X1-H.webp', 2)])), INDEX);
  assert.equal(d.stats5.atk.knownCopies, 2);
  assert.equal(d.stats5.atk.unknownCopies, 2);
  assert.equal(d.stats5.atk.sum, 4);
  assert.equal(d.stats5.atk.mean, 2);
});

test('describeDeck：事件卡不進五維統計', () => {
  const d = describeDeck(norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 2), card('E1-H.webp', 10)])), INDEX);
  assert.equal(d.stats5.blk.knownCopies, 2);
  assert.equal(d.stats5.blk.unknownCopies, 0);
});

test('describeDeck：攻擊與攔網各自一軸，沒有合併成強度分數的欄位', () => {
  const d = describeDeck(norm(legalDeck('u1', 'd1', '甲')), INDEX);
  assert.deepEqual(Object.keys(d.stats5).sort(), ['atk', 'blk', 'rcv', 'srv', 'tos']);
  assert.equal('strength' in d, false);
  assert.equal('power' in d.stats5, false);
});

test('describeDeck：帶出用途色與未知卡張數，供畫面標註', () => {
  const d = describeDeck(norm(doc('u1', 'd1', '甲', [card('K1-H.webp', 4), card('ZZZ.webp', 2, 'HV-X')], {
    color: { 'K1-H.webp': { attack: 4 } },
  })), INDEX);
  assert.equal(d.colorUse.attack, 4);
  assert.deepEqual(d.unknown, { copies: 2, kinds: 1 });
});

// ── crossAccountSimilar ────────────────────────────────────────────────
test('crossAccountSimilar：只比跨帳號的配對，同帳號的版本不列入', () => {
  const decks = [
    norm(legalDeck('u1', 'a', '甲')), norm(legalDeck('u1', 'b', '乙')), norm(legalDeck('u2', 'c', '丙')),
  ];
  const pairs = crossAccountSimilar(decks);
  assert.equal(pairs.length, 2);
  assert.ok(pairs.every(p => p.a.uid !== p.b.uid));
  assert.ok(pairs.every(p => p.identical === true && p.similarity === 1));
});

test('crossAccountSimilar：牌表完全相同的多個帳號，配對會全部展開（先去重只影響算幾次相似度）', () => {
  const decks = ['u1', 'u2', 'u3'].map((uid, i) => norm(legalDeck(uid, `d${i}`, '同一副')));
  const pairs = crossAccountSimilar(decks);
  assert.equal(pairs.length, 3);
  assert.ok(pairs.every(p => p.identical && p.similarity === 1));
  assert.deepEqual([...new Set(pairs.flatMap(p => [p.a.uid, p.b.uid]))].sort(), ['u1', 'u2', 'u3']);
});

test('crossAccountSimilar：低於門檻的配對不列，依相似度由高到低排序', () => {
  const decks = [
    norm(doc('u1', 'a', '甲', [card('K1-H.webp', 20), card('K2-H.webp', 20)])),
    norm(doc('u2', 'b', '乙', [card('K1-H.webp', 18), card('K2-H.webp', 20), card('K3-H.webp', 2)])),
    norm(doc('u3', 'c', '丙', [card('K3-H.webp', 40)])),
  ];
  const pairs = crossAccountSimilar(decks);
  assert.deepEqual(pairs.map(p => [p.a.id, p.b.id].sort()), [['a', 'b']]);
  assert.equal(pairs[0].identical, false);
  assert.equal(pairs[0].similarity.toFixed(3), '0.905');
});

// ── aggregate ──────────────────────────────────────────────────────────
// 烏野 24 + 音駒 12 + 事件 4 → 主校烏野；把其中幾張換成 K2 做出不同版本
const karasuno = (uid, id, { k1 = 24, k2 = 0, n1 = 12 } = {}) => norm(doc(uid, id, '烏野-' + id, [
  card('K1-H.webp', k1), card('K2-H.webp', k2), card('N1-H.webp', n1), card('E1-H.webp', 4),
]));
const nekoma = (uid, id) => norm(doc(uid, id, '音駒-' + id, [
  card('N1-H.webp', 24), card('K1-H.webp', 12), card('E2-H.webp', 4),
]));

test('aggregate：學校分布同時給原始副數與帳號加權，存很多副不會變成人氣', () => {
  // u1 存了 3 副互不相似的烏野牌（權重各 1/3），u2 只有 1 副音駒
  const decks = [
    karasuno('u1', 'a'), karasuno('u1', 'b', { k1: 12, k2: 12 }), karasuno('u1', 'c', { k1: 0, k2: 24 }),
    nekoma('u2', 'd'),
  ];
  const r = aggregate(decks, INDEX);
  assert.equal(r.sample.accounts, 2);
  assert.equal(r.sample.decks, 4);
  assert.equal(r.sample.clusters, 4);
  assert.deepEqual(r.schools.raw, [
    { school: '烏野', decks: 3, share: 0.75 },
    { school: '音駒', decks: 1, share: 0.25 },
  ]);
  assert.deepEqual(r.schools.weighted, [
    { school: '烏野', weight: 1, share: 0.5, accounts: 1 },
    { school: '音駒', weight: 1, share: 0.5, accounts: 1 },
  ]);
  assert.deepEqual(r.schools.denominator, { decks: 4, accounts: 2, weight: 2 });
});

test('aggregate：少於 5 個帳號標成探索性', () => {
  const few = aggregate([karasuno('u1', 'a'), nekoma('u2', 'b')], INDEX);
  assert.equal(few.sample.exploratory, true);
  const many = aggregate(
    [...Array(MIN_ACCOUNTS_FOR_CONFIDENCE)].map((_, i) => karasuno('u' + i, 'd' + i)), INDEX);
  assert.equal(many.sample.exploratory, false);
});

test('aggregate：核心卡採用率先在帳號內等權、再平均各帳號', () => {
  // u1 有 2 個烏野群，只有 1 個放 K2 → 帳號內採用率 0.5
  // u2 有 1 個烏野群，放了 K2 → 帳號內採用率 1
  // 平均各帳號 → 0.75（若改成直接數牌組會是 2/3）
  const decks = [
    karasuno('u1', 'a'), karasuno('u1', 'b', { k1: 12, k2: 12 }), karasuno('u2', 'c', { k1: 12, k2: 12 }),
  ];
  const core = aggregate(decks, INDEX).coreCards.find(s => s.school === '烏野');
  const k2 = core.cards.find(c => c.card_no === 'HV-T01-002');
  assert.equal(k2.adoptionRate, 0.75);
  assert.equal(core.accounts, 2);
  assert.equal(core.clusters, 3);
});

test('aggregate：核心卡的平均張數只算採用者', () => {
  const decks = [
    karasuno('u1', 'a'), karasuno('u1', 'b', { k1: 12, k2: 12 }), karasuno('u2', 'c', { k1: 20, k2: 4 }),
  ];
  const cards = aggregate(decks, INDEX).coreCards.find(s => s.school === '烏野').cards;
  const k2 = cards.find(c => c.card_no === 'HV-T01-002');
  // 採用者是 u1 的 b（12 張）與 u2 的 c（4 張）→ 帳號內平均 12 與 4，再平均 = 8
  assert.equal(k2.meanCopiesAmongAdopters, 8);
  assert.equal(k2.accounts, 2);
  // 沒採用的群不會把平均拉低成 (12+4)/3
  assert.notEqual(k2.meanCopiesAmongAdopters, 16 / 3);
});

test('aggregate：代表牌組是實際存在的那一副（medoid），並帶支持帳號數', () => {
  const decks = [karasuno('u1', 'a'), karasuno('u2', 'b'), karasuno('u3', 'c', { k1: 20, k2: 4 })];
  const rep = aggregate(decks, INDEX).representatives.find(s => s.school === '烏野');
  const top = rep.groups[0];
  assert.ok(decks.some(d => d.id === top.deck.id));
  assert.equal(top.accounts, 2);
  assert.deepEqual(top.members.map(m => m.uid).sort(), ['u1', 'u2']);
});

test('aggregate：混合與未知歸屬各自一欄，不塞進某一校', () => {
  const decks = [
    karasuno('u1', 'a'),
    norm(doc('u2', 'mix', '混合', [card('K1-H.webp', 18), card('N1-H.webp', 18), card('E1-H.webp', 4)])),
    norm(doc('u3', 'unk', '未知', [card('U1-H.webp', 36), card('E1-H.webp', 4)])),
  ];
  const r = aggregate(decks, INDEX);
  assert.deepEqual(r.schools.raw.map(x => x.school).sort(), ['未知', '混合', '烏野']);
});

test('aggregate：標出「移除哪個帳號會讓第一名翻轉」', () => {
  // 加權後烏野 2、音駒 1：移掉任一個烏野帳號就不再是第一名
  const decks = [karasuno('u1', 'a'), karasuno('u2', 'b'), nekoma('u3', 'c')];
  const r = aggregate(decks, INDEX);
  assert.equal(r.schools.robustness.topSchool, '烏野');
  assert.deepEqual(r.schools.robustness.flipAccounts.sort(), ['u1', 'u2']);
});

test('aggregate：空輸入不炸，分母都是 0', () => {
  const r = aggregate([], INDEX);
  assert.deepEqual(r.sample, { accounts: 0, decks: 0, clusters: 0, exploratory: true });
  assert.deepEqual(r.schools.raw, []);
  assert.deepEqual(r.schools.weighted, []);
  assert.deepEqual(r.coreCards, []);
  assert.deepEqual(r.representatives, []);
  assert.equal(r.schools.robustness.topSchool, null);
});

test('aggregate：跨帳號不合併也不刪除——每個帳號的總權重都是 1', () => {
  const decks = [karasuno('u1', 'a'), karasuno('u1', 'b', { k1: 0, k2: 24 }), nekoma('u2', 'c')];
  const r = aggregate(decks, INDEX);
  assert.equal(r.schools.weighted.reduce((s, x) => s + x.weight, 0), 2);
  assert.equal(r.schools.denominator.accounts, 2);
});
