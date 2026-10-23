// 牌組分析面板（ana.html）的 A 線統計純函式。
// 規格與理由見 docs/deck-analysis-panel-plan.md；這裡只實作，不重述規格。
// 刻意不碰 DOM／Firebase，才能用 node:test 測（見 ADR 0005）。
//
// 兩個貫穿整份模組的前提：
// 1. 權威鍵是 cards_data.js 的 card_no。牌組文件裡存的是 image_file（同一個 card_no 可能有
//    多個稀有度版本），所以一律先用 image_file 查卡庫、再換成 card_no 併起來，不信文件自帶的
//    card_no（實際資料會不一致，不一致就標記，但以卡庫為準）。
// 2. 這些數字描述的是「網站使用者存了什麼」，不是強度、不是人氣、不是勝率。每個彙總函式都回傳
//    分母與樣本數，讓畫面有東西可標；少於 MIN_ACCOUNTS_FOR_CONFIDENCE 個帳號要標「探索性」。

import { serializeDeck } from './deck-fingerprint.js';
import { QUICK_DECK_ID, LEGAL_DECK_SIZE, deckUpdatedMs } from './deck-constants.js';

export { QUICK_DECK_ID, LEGAL_DECK_SIZE };
export const MAX_EVENT_COPIES = 8;
export const SIMILARITY_THRESHOLD = 0.9;
export const MIN_ACCOUNTS_FOR_CONFIDENCE = 5;
export const MAIN_SCHOOL_MIN_SHARE = 0.6;
export const MAIN_SCHOOL_MIN_LEAD = 0.2;

export const STAT_KEYS = Object.freeze(['srv', 'blk', 'rcv', 'tos', 'atk']);
export const COLOR_KEYS = Object.freeze(['free', 'receive', 'set', 'attack']);

const CONFLICT_FIELDS = ['category', 'school_tags', ...STAT_KEYS];

const isRole = card => card.category !== 'EVENT';
const signature = (card, field) => JSON.stringify(
  field === 'school_tags' ? [...(card.school_tags || [])].sort() : card[field] ?? null,
);

export function indexCards(cards) {
  const byImage = new Map();
  const byCardNo = new Map();
  const conflicts = [];
  for (const card of cards || []) {
    byImage.set(card.image_file, card);
    const first = byCardNo.get(card.card_no);
    if (!first) { byCardNo.set(card.card_no, card); continue; }
    const fields = CONFLICT_FIELDS.filter(f => signature(first, f) !== signature(card, f));
    if (fields.length) conflicts.push({ card_no: card.card_no, fields, images: [first.image_file, card.image_file] });
  }
  return { byImage, byCardNo, conflicts };
}

// 學校標記的「有效」是指「卡庫上真的掛了這個標記」，不是 school-constants.js 的 10 個 key——
// 那份白名單是熱門學校榜單用的（只收 8 支固定校隊 + ユース/疑似ユース），但卡庫實際有 28 種標記
// （角川、条善寺、井闥山、町内会…）。分析面板要照實呈現玩家在組什麼，把這些併成「未知」會失真。
const schoolTagsOf = card => (card.school_tags || []).filter(t => typeof t === 'string' && t !== '');

function addIssue(issues, code, item) {
  let entry = issues.find(i => i.code === code);
  if (!entry) { entry = { code, items: [] }; issues.push(entry); }
  if (item != null && !entry.items.includes(item)) entry.items.push(item);
}

function colorUseOf(doc, entries, index, issues) {
  const use = { free: 0, receive: 0, set: 0, attack: 0, unassigned: 0, event: 0 };
  const colors = doc.color || {};
  for (const { image_file, count } of entries) {
    const card = index.byImage.get(image_file);
    if (card && !isRole(card)) { use.event += count; continue; }
    const map = colors[image_file];
    const assignment = COLOR_KEYS.map(key => (Number.isInteger(map?.[key]) && map[key] > 0 ? map[key] : 0));
    const assigned = assignment.reduce((s, n) => s + n, 0);
    // 顏色張數超過該卡張數時，只丟掉「這張卡的用途色」這一個指標（標記起來），
    // 張數本身照算進未指定——否則堆疊條的總和會對不上牌組張數，整條圖都不能看。
    if (assigned > count) {
      addIssue(issues, 'color_overflow', image_file);
      use.unassigned += count;
      continue;
    }
    COLOR_KEYS.forEach((key, i) => { use[key] += assignment[i]; });
    use.unassigned += count - assigned;
  }
  return use;
}

export function normalizeDeck(doc, index, { now = Date.now() } = {}) {
  const issues = [];
  const vector = new Map();
  const rawEntries = doc.deck?.cards || [];
  const entries = [];
  let roleCopies = 0;
  let eventCopies = 0;
  let unknownCopies = 0;

  for (const entry of rawEntries) {
    const image = entry.image_file;
    const count = entry.count === undefined || entry.count === null ? 1 : entry.count;
    if (!Number.isInteger(count) || count <= 0) { addIssue(issues, 'bad_count', image); continue; }
    entries.push({ image_file: image, count });

    const card = index.byImage.get(image);
    if (!card) { unknownCopies += count; addIssue(issues, 'unknown_card', image); continue; }
    if (entry.card_no && entry.card_no !== card.card_no) addIssue(issues, 'card_no_mismatch', image);

    vector.set(card.card_no, (vector.get(card.card_no) || 0) + count);
    if (isRole(card)) {
      roleCopies += count;
      if (STAT_KEYS.some(k => !Number.isFinite(card[k]))) addIssue(issues, 'missing_stats', image);
    } else {
      eventCopies += count;
    }
  }

  const colorUse = colorUseOf(doc, entries, index, issues);
  const updatedMs = deckUpdatedMs(doc);
  if (!updatedMs || updatedMs > now) addIssue(issues, 'invalid_time', null);

  return {
    uid: doc.ownerUid || 'unknown',
    id: doc.id,
    name: doc.deck?.name ?? '（無名稱）',
    deleted: !!doc.deleted,
    updatedMs,
    vector,
    kinds: vector.size,
    total: roleCopies + eventCopies + unknownCopies,
    roleCopies,
    eventCopies,
    unknownCopies,
    colorUse,
    issues,
  };
}

const hasIssue = (deck, code) => deck.issues.some(i => i.code === code);

// 排除條件的順序就是漏斗的順序；一副牌可能同時踩到多條，reasons 全部留著給品質面板用。
const COHORT_STAGES = [
  { key: 'not_deleted', reason: 'deleted', label: '未刪除', ok: d => !d.deleted },
  { key: 'not_quick', reason: 'quick_deck', label: '非預設牌組', ok: d => d.id !== QUICK_DECK_ID },
  { key: 'identifiable', reason: 'unidentifiable', label: '卡片可辨識、張數為正整數',
    ok: d => !hasIssue(d, 'unknown_card') && !hasIssue(d, 'bad_count') },
  { key: 'size_40', reason: 'not_40', label: `${LEGAL_DECK_SIZE} 張`, ok: d => d.total === LEGAL_DECK_SIZE },
  { key: 'events_8', reason: 'too_many_events', label: `事件 ≤${MAX_EVENT_COPIES}`, ok: d => d.eventCopies <= MAX_EVENT_COPIES },
];

const countAccounts = decks => new Set(decks.map(d => d.uid)).size;

export function selectCohort(decks) {
  const all = decks || [];
  const funnel = [{ key: 'all', label: '全部牌組文件', decks: all.length, accounts: countAccounts(all) }];
  let surviving = all;
  for (const stage of COHORT_STAGES) {
    surviving = surviving.filter(stage.ok);
    funnel.push({ key: stage.key, label: stage.label, decks: surviving.length, accounts: countAccounts(surviving) });
  }
  const included = surviving;
  const excluded = all
    .filter(d => !included.includes(d))
    .map(d => ({ deck: d, reasons: COHORT_STAGES.filter(s => !s.ok(d)).map(s => s.reason) }));
  return { included, excluded, funnel };
}

const vectorOf = deck => (deck instanceof Map ? deck : deck.vector);

export function similarity(a, b) {
  const va = vectorOf(a);
  const vb = vectorOf(b);
  let min = 0;
  let max = 0;
  for (const key of new Set([...va.keys(), ...vb.keys()])) {
    const x = va.get(key) || 0;
    const y = vb.get(key) || 0;
    min += Math.min(x, y);
    max += Math.max(x, y);
  }
  return max === 0 ? 0 : min / max;
}

// 門檻一律「含等於」，但 0.6 / 0.2 這種十進位門檻在浮點下算出來常常差個 1e-17
// （例如 24/40 - 16/40 會得到 0.19999999999999998），所以比較時給一個比資料精度小得多的容差。
const EPS = 1e-9;
const atLeast = (value, threshold) => value + EPS >= threshold;

const hasInvalidTime = deck => deck.issues.some(i => i.code === 'invalid_time');

// 每群保留「最新有效時間」者：時間無效（缺時間／未來時間）的那副不當代表，
// 除非整群都無效。時間相同時用 id 決定，避免輸入順序改變結果。
function pickRepresentative(decks) {
  const valid = decks.filter(d => !hasInvalidTime(d));
  const pool = valid.length ? valid : decks;
  return pool.reduce((best, d) =>
    (d.updatedMs > best.updatedMs || (d.updatedMs === best.updatedMs && d.id < best.id)) ? d : best);
}

// 完全連結（complete linkage）：兩群要合併，必須「所有」跨群配對都達到門檻。
// 刻意不用單一連結——A~B 0.95、B~C 0.95、A~C 0.80 這種相似鏈會被串成一個大群。
export function groupVersions(decks, { threshold = SIMILARITY_THRESHOLD } = {}) {
  const items = decks || [];
  if (items.length <= 1) {
    return items.map(d => ({ decks: [d], representative: d, weight: 1 }));
  }
  // 群間相似度 = 所有跨群配對的最小值。合併後直接用 min 更新那一列就夠，不必每輪重新掃所有
  // 成員配對——重新掃是 O(n⁴)，一校幾百副牌時瀏覽器會卡住。
  const n = items.length;
  const sim = items.map((a, i) => items.map((b, j) => (i === j ? 1 : similarity(a, b))));
  const members = items.map((_, i) => [i]);
  const alive = items.map(() => true);
  let count = n;

  while (count > 1) {
    let best = null;
    for (let i = 0; i < n; i++) {
      if (!alive[i]) continue;
      for (let j = i + 1; j < n; j++) {
        if (alive[j] && (!best || sim[i][j] > best.s)) best = { i, j, s: sim[i][j] };
      }
    }
    if (!best || !atLeast(best.s, threshold)) break;
    members[best.i].push(...members[best.j]);
    alive[best.j] = false;
    count--;
    for (let x = 0; x < n; x++) {
      if (!alive[x] || x === best.i) continue;
      const v = Math.min(sim[best.i][x], sim[best.j][x]);
      sim[best.i][x] = v;
      sim[x][best.i] = v;
    }
  }

  const clusters = members.filter((_, i) => alive[i]);
  const weight = 1 / clusters.length;
  return clusters.map(idx => {
    const group = idx.map(i => items[i]).sort((a, b) => b.updatedMs - a.updatedMs || (a.id < b.id ? -1 : 1));
    return { decks: group, representative: pickRepresentative(group), weight };
  });
}

function schoolDistribution(deck, index) {
  const copies = new Map();
  let roleCopies = 0;
  let unknownAttributionCopies = 0;
  for (const [cardNo, n] of deck.vector) {
    const card = index.byCardNo.get(cardNo);
    if (!card || !isRole(card)) continue;
    roleCopies += n;
    const tags = schoolTagsOf(card);
    if (!tags.length) { unknownAttributionCopies += n; continue; }
    for (const tag of tags) copies.set(tag, (copies.get(tag) || 0) + n / tags.length);
  }
  const dist = [...copies]
    .map(([school, c]) => ({ school, copies: c, share: roleCopies ? c / roleCopies : 0 }))
    .sort((a, b) => b.copies - a.copies || (a.school < b.school ? -1 : 1));
  return {
    dist,
    roleCopies,
    unknownAttributionCopies,
    // ユース 與 疑似ユース 語意不同，畫面要分欄，所以在這裡就分開帶出來，不讓呼叫端去比字串
    youth: { 'ユース': copies.get('ユース') || 0, '疑似ユース': copies.get('疑似ユース') || 0 },
  };
}

function classifyMainSchool({ dist, roleCopies }) {
  if (!roleCopies || !dist.length) return { type: 'unknown', school: null, schools: [], share: 0, lead: 0 };
  const [top, second] = dist;
  const share = top.share;
  // lead 用張數差再除以分母，不用兩個 share 相減——相減會累積浮點誤差
  const lead = (top.copies - (second?.copies || 0)) / roleCopies;
  if (atLeast(share, MAIN_SCHOOL_MIN_SHARE) && atLeast(lead, MAIN_SCHOOL_MIN_LEAD)) {
    return { type: 'single', school: top.school, schools: [top.school], share, lead };
  }
  return { type: 'mixed', school: null, schools: dist.slice(0, 2).map(x => x.school), share, lead };
}

// 最近秩（nearest-rank）分位數：把每一張卡當一個觀測值展開後取第 ceil(p*N) 名。
function quantilesOf(histogram, total) {
  if (!total) return { p25: null, p50: null, p75: null };
  const at = p => {
    const rank = Math.max(1, Math.ceil(p * total));
    let seen = 0;
    for (const { value, copies } of histogram) {
      seen += copies;
      if (seen >= rank) return value;
    }
    return histogram[histogram.length - 1].value;
  };
  return { p25: at(0.25), p50: at(0.5), p75: at(0.75) };
}

// 五維各自一軸。刻意不提供「強度」「攻擊力」之類的合成分數——卡片數值加總不能代表強弱，
// 攻擊與攔網更不能相加（計畫 §1.7、§2.5）。
function statProfile(deck, index) {
  const out = {};
  for (const key of STAT_KEYS) {
    const hist = new Map();
    let sum = 0;
    let knownCopies = 0;
    let unknownCopies = 0;
    for (const [cardNo, n] of deck.vector) {
      const card = index.byCardNo.get(cardNo);
      if (!card || !isRole(card)) continue;
      const value = card[key];
      if (!Number.isFinite(value)) { unknownCopies += n; continue; }
      sum += value * n;
      knownCopies += n;
      hist.set(value, (hist.get(value) || 0) + n);
    }
    const histogram = [...hist].map(([value, copies]) => ({ value, copies })).sort((a, b) => a.value - b.value);
    out[key] = {
      sum,
      mean: knownCopies ? sum / knownCopies : null,
      knownCopies,
      unknownCopies,
      quantiles: quantilesOf(histogram, knownCopies),
      histogram,
    };
  }
  return out;
}

export function describeDeck(deck, index) {
  const schools = schoolDistribution(deck, index);
  const [top, second] = schools.dist;
  return {
    schools,
    mainSchool: classifyMainSchool(schools),
    concentration: {
      top1: top?.share || 0,
      top2: second?.share || 0,
      lead: ((top?.copies || 0) - (second?.copies || 0)) / (schools.roleCopies || 1),
    },
    stats5: statProfile(deck, index),
    colorUse: deck.colorUse,
    unknown: {
      copies: deck.unknownCopies,
      kinds: deck.issues.find(i => i.code === 'unknown_card')?.items.length || 0,
    },
  };
}

// 「跨帳號相似牌表」——命名刻意不用「抄襲」：相似只代表牌表接近，供查核用，不是指控（計畫 §2.4）。
// 先用精確指紋（serializeDeck 的同一套序列化規則）分組去重，再只比各組代表一次，
// 比完展開回實際配對：牌表完全相同的那幾副只算一次相似度（§6）。
export function crossAccountSimilar(decks, { threshold = SIMILARITY_THRESHOLD } = {}) {
  const exact = new Map();
  for (const deck of decks || []) {
    const key = serializeDeck(deck.vector);
    if (!exact.has(key)) exact.set(key, []);
    exact.get(key).push(deck);
  }
  const groups = [...exact.values()];
  const pairs = [];
  const expand = (ga, gb, s, identical) => {
    for (const a of ga) for (const b of gb) {
      if (a.uid !== b.uid) pairs.push({ a, b, similarity: s, identical });
    }
  };
  for (let i = 0; i < groups.length; i++) {
    for (let x = 0; x < groups[i].length; x++) {
      expand([groups[i][x]], groups[i].slice(x + 1), 1, true);
    }
    for (let j = i + 1; j < groups.length; j++) {
      const s = similarity(groups[i][0], groups[j][0]);
      if (atLeast(s, threshold)) expand(groups[i], groups[j], s, s === 1);
    }
  }
  return pairs.sort((x, y) => y.similarity - x.similarity
    || (x.a.id < y.a.id ? -1 : x.a.id > y.a.id ? 1 : 0));
}

const MIXED_BUCKET = '混合';
const UNKNOWN_BUCKET = '未知';
const bucketOf = mainSchool =>
  mainSchool.type === 'single' ? mainSchool.school : mainSchool.type === 'mixed' ? MIXED_BUCKET : UNKNOWN_BUCKET;

function groupBy(items, key) {
  const map = new Map();
  for (const item of items) {
    const k = key(item);
    if (!map.has(k)) map.set(k, []);
    map.get(k).push(item);
  }
  return map;
}

// 帳號加權：每個帳號的總權重固定是 1，帳號內各群等權。用「該桶群數 / 該帳號群數」一次算完，
// 不是把 1/m 逐群相加——後者在 m=3 時會得到 0.9999999999999999。
function weightedBuckets(clusters) {
  const sums = new Map();
  for (const [uid, list] of groupBy(clusters, c => c.uid)) {
    for (const [school, members] of groupBy(list, c => c.school)) {
      const entry = sums.get(school) || { weight: 0, accounts: new Set() };
      entry.weight += members.length / list.length;
      entry.accounts.add(uid);
      sums.set(school, entry);
    }
  }
  return sums;
}

function rankBuckets(sums, accountCount) {
  return [...sums]
    .map(([school, { weight, accounts }]) => ({
      school, weight, share: accountCount ? weight / accountCount : 0, accounts: accounts.size,
    }))
    .sort((a, b) => b.weight - a.weight || (a.school < b.school ? -1 : 1));
}

// §2.3「檢查移除單一帳號後結論是否翻轉」：列出移掉之後第一名就不再是第一名（含變成並列）的帳號。
function topSchoolRobustness(clusters) {
  const accounts = [...new Set(clusters.map(c => c.uid))];
  const overall = rankBuckets(weightedBuckets(clusters), accounts.length);
  const topSchool = overall[0]?.school ?? null;
  if (!topSchool) return { topSchool: null, flipAccounts: [] };
  const flipAccounts = accounts.filter(uid => {
    const rest = clusters.filter(c => c.uid !== uid);
    const ranked = rankBuckets(weightedBuckets(rest), new Set(rest.map(c => c.uid)).size);
    if (!ranked.length || ranked[0].school !== topSchool) return true;
    return !(ranked[0].weight > (ranked[1]?.weight || 0) + EPS);
  });
  return { topSchool, flipAccounts };
}

// §1.6：各校先在帳號內等權算採用率，再平均各帳號；平均張數只算採用者。
function coreCardsOf(clusters) {
  return [...groupBy(clusters, c => c.school)]
    .map(([school, list]) => {
      const byAccount = [...groupBy(list, c => c.uid).values()];
      const cardNos = new Set(list.flatMap(c => [...c.deck.vector.keys()]));
      const cards = [...cardNos].map(cardNo => {
        const perAccount = byAccount.map(accountClusters => {
          const adopting = accountClusters.filter(c => c.deck.vector.has(cardNo));
          return {
            adoption: adopting.length / accountClusters.length,
            meanCopies: adopting.length
              ? adopting.reduce((s, c) => s + c.deck.vector.get(cardNo), 0) / adopting.length
              : null,
          };
        });
        const adopters = perAccount.filter(a => a.meanCopies !== null);
        return {
          card_no: cardNo,
          adoptionRate: perAccount.reduce((s, a) => s + a.adoption, 0) / perAccount.length,
          meanCopiesAmongAdopters: adopters.length
            ? adopters.reduce((s, a) => s + a.meanCopies, 0) / adopters.length
            : null,
          accounts: adopters.length,
        };
      }).sort((a, b) => b.adoptionRate - a.adoptionRate || (a.card_no < b.card_no ? -1 : 1));
      return {
        school,
        accounts: byAccount.length,
        clusters: list.length,
        exploratory: byAccount.length < MIN_ACCOUNTS_FOR_CONFIDENCE,
        cards,
      };
    })
    .sort((a, b) => b.accounts - a.accounts || (a.school < b.school ? -1 : 1));
}

// 代表牌組是「群內帳號加權距離最小的實際牌組」（medoid），不是平均出來的虛構牌表。
// 一校可以有多群——同一校不同流派不該被硬壓成一副。
function representativesOf(clusters, threshold) {
  return [...groupBy(clusters, c => c.school)]
    .map(([school, list]) => {
      const groups = groupVersions(list.map(c => c.deck), { threshold }).map(group => {
        const members = group.decks.map(d => list.find(c => c.deck === d));
        const costs = members.map(m =>
          members.reduce((s, o) => s + o.weight * (1 - similarity(m.deck, o.deck)), 0));
        const medoid = members.reduce((best, cand, i) =>
          costs[i] < costs[members.indexOf(best)]
            || (costs[i] === costs[members.indexOf(best)] && cand.deck.id < best.deck.id) ? cand : best);
        return {
          deck: medoid.deck,
          weight: members.reduce((s, m) => s + m.weight, 0),
          accounts: new Set(members.map(m => m.uid)).size,
          members: members.map(m => ({ uid: m.uid, deck: m.deck, weight: m.weight })),
        };
      }).sort((a, b) => b.weight - a.weight || b.accounts - a.accounts || (a.deck.id < b.deck.id ? -1 : 1));
      return { school, groups };
    })
    .sort((a, b) => b.groups.length - a.groups.length || (a.school < b.school ? -1 : 1));
}

export function aggregate(decks, index, { threshold = SIMILARITY_THRESHOLD } = {}) {
  const included = decks || [];
  const clusters = [];
  for (const [uid, list] of groupBy(included, d => d.uid)) {
    for (const group of groupVersions(list, { threshold })) {
      const profile = describeDeck(group.representative, index);
      clusters.push({
        uid,
        weight: group.weight,
        deck: group.representative,
        members: group.decks,
        profile,
        school: bucketOf(profile.mainSchool),
      });
    }
  }

  const accountCount = new Set(included.map(d => d.uid)).size;
  const rawTotal = included.length;
  const raw = [...groupBy(clusters, c => c.school)]
    .map(([school, list]) => {
      const deckCount = list.reduce((s, c) => s + c.members.length, 0);
      return { school, decks: deckCount, share: rawTotal ? deckCount / rawTotal : 0 };
    })
    .sort((a, b) => b.decks - a.decks || (a.school < b.school ? -1 : 1));

  return {
    sample: {
      accounts: accountCount,
      decks: rawTotal,
      clusters: clusters.length,
      exploratory: accountCount < MIN_ACCOUNTS_FOR_CONFIDENCE,
    },
    clusters,
    schools: {
      raw,
      weighted: rankBuckets(weightedBuckets(clusters), accountCount),
      denominator: { decks: rawTotal, accounts: accountCount, weight: accountCount },
      robustness: topSchoolRobustness(clusters),
    },
    coreCards: coreCardsOf(clusters),
    representatives: representativesOf(clusters, threshold),
  };
}
