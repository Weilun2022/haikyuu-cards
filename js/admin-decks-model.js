// 管理者牌組檢視頁（admin-decks.html）的純函式：把 collectionGroup('decks') 抓回來的
// 文件分組、篩選、統計。刻意不碰 DOM / Firebase，才能用 node:test 測（見 ADR 0005）。
//
// 輸入的「文件」形狀（對應 cloud-sync.js 的 deckDocPayload）：
//   { id, ownerUid, deck: { name, cards: [{ image_file, card_no, count }] },
//     deleted, clientUpdatedAt, updatedAt? }

export const QUICK_DECK_NAME = '快速查詢';
const LEGAL_DECK_SIZE = 40;

// 舊資料的卡片可能沒有 count 欄位，視為 1 張
export function cardCount(c) {
  return Number.isFinite(c.count) ? c.count : 1;
}

function deckTotal(cards) {
  return (cards || []).reduce((s, c) => s + cardCount(c), 0);
}

const isQuickDeck = d => d.name === QUICK_DECK_NAME;

function updatedMs(d) {
  if (Number.isFinite(d.clientUpdatedAt)) return d.clientUpdatedAt;
  const t = d.updatedAt?.toMillis?.();
  return Number.isFinite(t) ? t : 0;
}

function normalizeDeck(d) {
  const cards = d.deck?.cards || [];
  return {
    id: d.id,
    name: d.deck?.name ?? '（無名稱）',
    cards,
    total: deckTotal(cards),
    deleted: !!d.deleted,
    updatedMs: updatedMs(d),
  };
}

// 「真正的牌組」：不是預設的快速查詢、不是空的、沒被刪除
function isRealDeck(d) {
  return !d.deleted && !isQuickDeck(d) && d.total > 0;
}

export function groupByAccount(docs) {
  const byUid = new Map();
  for (const doc of docs) {
    const uid = doc.ownerUid || 'unknown';
    if (!byUid.has(uid)) byUid.set(uid, []);
    byUid.get(uid).push(normalizeDeck(doc));
  }
  const accounts = [...byUid].map(([uid, decks]) => {
    const live = decks.filter(d => !d.deleted);
    const real = decks.filter(isRealDeck);
    return {
      uid,
      shortId: uid.slice(0, 6),
      decks,
      activeCount: live.length,
      realCount: real.length,
      legal40Count: real.filter(d => d.total === LEGAL_DECK_SIZE).length,
      lastUpdated: Math.max(0, ...live.map(d => d.updatedMs)),
    };
  });
  return accounts.sort((a, b) => b.realCount - a.realCount || b.lastUpdated - a.lastUpdated);
}

export function filterDecks(decks, { showQuick = false, showEmpty = false, showDeleted = false, only40 = false } = {}) {
  return decks
    .filter(d => (showDeleted || !d.deleted)
      && (showQuick || !isQuickDeck(d))
      && (showEmpty || d.total > 0)
      && (!only40 || d.total === LEGAL_DECK_SIZE))
    .sort((a, b) => b.updatedMs - a.updatedMs);
}

function tally(cards, cardsByImage, pick) {
  const counts = new Map();
  let unknown = 0;
  for (const c of cards || []) {
    const n = cardCount(c);
    const card = cardsByImage[c.image_file];
    if (!card) { unknown += n; continue; }
    const label = pick(card) || '其他';
    counts.set(label, (counts.get(label) || 0) + n);
  }
  const list = [...counts].map(([label, count]) => ({ label, count })).sort((a, b) => b.count - a.count);
  return { list, unknown };
}

export function summarizeDeck(deck, cardsByImage) {
  const school = tally(deck.cards, cardsByImage, c => c.school);
  const category = tally(deck.cards, cardsByImage, c => c.category_zh);
  return { bySchool: school.list, byCategory: category.list, unknown: school.unknown };
}

// 卡名資料保留日文字形「兎」（木兎光太郎），但使用者多半打「兔」，兩邊都轉成同一個字再比
const normalizeQuery = s => String(s ?? '').toLowerCase().replace(/[\s　]+/g, '').replace(/兔/g, '兎');

// 找「哪些牌組用了符合這個字串的卡」：卡號、日文名、中文名都比對。
// 已刪除與預設的快速查詢不算（那不是使用者真的組出來的牌）。
export function findDeckHits(accounts, query, cardsByImage) {
  const q = normalizeQuery(query);
  if (!q) return [];
  const matches = image => {
    const c = cardsByImage[image];
    return !!c && [c.card_no, c.name, c.name_zh].some(f => normalizeQuery(f).includes(q));
  };
  const hits = [];
  for (const acc of accounts) {
    for (const d of acc.decks) {
      if (d.deleted || isQuickDeck(d)) continue;
      const count = d.cards.filter(c => matches(c.image_file))
        .reduce((s, c) => s + cardCount(c), 0);
      if (count > 0) hits.push({ uid: acc.uid, shortId: acc.shortId, deckId: d.id, deckName: d.name, count });
    }
  }
  return hits.sort((a, b) => b.count - a.count);
}

// 網頁端的閘門（只是讓非管理者看到明確訊息，真正的把關是 Firestore Rules）
export function isAdminUser(user, adminEmail) {
  return !!user && user.emailVerified === true && user.email === adminEmail;
}
