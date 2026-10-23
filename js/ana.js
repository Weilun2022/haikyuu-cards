// 管理者牌組檢視頁：一次把所有帳號的牌組載進來，點帳號看牌組、點牌組看卡片。
// 純唯讀——這個檔案不呼叫任何 Firestore 寫入函式。
// 真正的把關是 Firestore Rules（只有管理者 email 能讀別人的 decks）；這裡的 accessDecision
// 只是把沒權限的人彈回卡牌資料庫，不是安全邊界。
//
// 登入狀態跟 index.html 共用（同一個 app／同網域），在卡牌網站登入過這裡就已登入。
// 牌組名稱是其他使用者自訂的不可信字串，一律用 textContent 渲染，不拼 innerHTML。

import { app } from './cloud-sync.js';
import { getAuth, onAuthStateChanged } from 'https://www.gstatic.com/firebasejs/10.12.4/firebase-auth.js';
import { getFirestore, collectionGroup, getDocs, query } from 'https://www.gstatic.com/firebasejs/10.12.4/firebase-firestore.js';
import { groupByAccount, filterDecks, summarizeDeck, findDeckHits, accessDecision, cardCount } from './ana-model.js';
import { indexCards, normalizeDeck, selectCohort, aggregate } from './deck-stats-model.js';
import { renderAnalysis } from './ana-analysis.js';
import { h, fmtDate, fmtTime } from './ana-dom.js';

const ADMIN_EMAIL = 'evilscheme2012@gmail.com';
// 沒權限的人彈回卡牌資料庫。管理者要在這一頁自己登入的話，用 ana.html?login=1。
const HOME_URL = 'index.html';
const wantsLogin = new URLSearchParams(location.search).has('login');
// 標題不寫在 HTML 裡：沒權限的人在跳轉前不該看到「牌組檢視（管理者）」閃過。
const PAGE_TITLE = '牌組檢視（管理者）';

const auth = getAuth(app);
const db = getFirestore(app);
const $ = id => document.getElementById(id);

const cardsByImage = {};
for (const c of (typeof CARDS_DATA !== 'undefined' ? CARDS_DATA.cards : [])) cardsByImage[c.image_file] = c;

let accounts = [];
let selUid = null;
let selDeckId = null;
let rawDocs = [];
let loadedAt = 0;
let tab = 'browse';
// 分析面板的運算結果（全量算一次就夠，切分頁不重算）。重新整理資料時清掉。
let analysis = null;
// 面板內的 UI 選擇（選了哪一校、哪一副牌、品質清單看哪一欄），重畫時沿用。
const analysisState = { schoolWeighted: true };
const cardsIndex = indexCards(typeof CARDS_DATA !== 'undefined' ? CARDS_DATA.cards : []);

function showGate(text, isErr = false) {
  $('app').hidden = true;
  const g = $('gate');
  g.hidden = false;
  g.className = 'msg' + (isErr ? ' err' : '');
  g.textContent = text;
}

function filters() {
  return {
    showQuick: $('f-quick').checked,
    showEmpty: $('f-empty').checked,
    showDeleted: $('f-deleted').checked,
    only40: $('f-40').checked,
  };
}

async function loadAll() {
  $('status').textContent = '讀取中…';
  const snap = await getDocs(query(collectionGroup(db, 'decks')));
  rawDocs = snap.docs.map(d => ({
    ...d.data(),
    id: d.id,
    // 以文件路徑上的 uid 為準，不信文件內可自填的 ownerUid
    ownerUid: d.ref.parent.parent?.id || d.data().ownerUid,
  }));
  accounts = groupByAccount(rawDocs);
  loadedAt = Date.now();
  analysis = null;
  $('status').textContent = `${accounts.length} 個帳號、${rawDocs.length} 份牌組文件`;
  $('loaded-at').textContent = `資料讀取於 ${fmtTime(loadedAt)}`;
  $('data-note').textContent = `資料讀取於 ${fmtTime(loadedAt)}，之後不會自動更新——要看最新狀態請按「重新整理」。`
    + '玩家刪除或清空牌組不會自動同步到雲端（要玩家自己按「🔄 立即同步」），'
    + '所以已經被刪掉的牌組可能還留在這裡。';
  render();
}

function buildAnalysis() {
  const normalized = rawDocs.map(d => normalizeDeck(d, cardsIndex));
  const cohort = selectCohort(normalized);
  return {
    normalized,
    cohort,
    agg: aggregate(cohort.included, cardsIndex),
    index: cardsIndex,
    loadedAt,
    state: analysisState,
  };
}

function render() {
  const onAnalysis = tab === 'analysis';
  $('view-browse').hidden = onAnalysis;
  $('view-analysis').hidden = !onAnalysis;
  $('tab-browse').classList.toggle('active', !onAnalysis);
  $('tab-analysis').classList.toggle('active', onAnalysis);
  if (onAnalysis) {
    if (!analysis) {
      // 全量算幾百毫秒，同步算的話瀏覽器不會先把「計算中」畫出來（整段都在同一個 task 裡），
      // 所以先讓出一次事件迴圈再算。
      $('view-analysis').replaceChildren(h('div', { class: 'msg' }, '計算中…'));
      setTimeout(() => { analysis = buildAnalysis(); render(); }, 0);
      return;
    }
    renderAnalysis($('view-analysis'), analysis);
    return;
  }
  renderAccounts();
  renderDetail();
}

function renderAccounts() {
  const list = $('accounts');
  list.replaceChildren(...accounts.map((a, i) => h('button', {
    class: 'row' + (a.uid === selUid ? ' active' : ''),
    on: { click: () => { selUid = a.uid; selDeckId = null; render(); } },
  },
    `#${String(i + 1).padStart(2, '0')} ${a.shortId}…　${a.realCount} 副`,
    h('span', { class: 'sub' }, `40 張 ${a.legal40Count}　有效 ${a.activeCount}　更新 ${fmtDate(a.lastUpdated)}`),
  )));
  $('acc-title').textContent = `帳號（${accounts.length}）`;
}

function renderDetail() {
  const box = $('detail');
  const q = $('q').value.trim();
  if (q) return renderSearch(box, q);

  const acc = accounts.find(a => a.uid === selUid);
  if (!acc) return box.replaceChildren(h('div', { class: 'msg' }, '從左邊選一個帳號'));

  const decks = filterDecks(acc.decks, filters());
  if (!decks.length) return box.replaceChildren(h('div', { class: 'msg' }, '這個帳號在目前篩選下沒有牌組（可試著勾選「顯示空牌組」）'));
  if (!decks.some(d => d.id === selDeckId)) selDeckId = decks[0].id;

  const chips = h('div', { class: 'decks' }, decks.map(d => h('button', {
    class: 'chip' + (d.id === selDeckId ? ' active' : ''),
    title: d.name,
    on: { click: () => { selDeckId = d.id; renderDetail(); } },
  }, `${d.name}${d.deleted ? '（已刪）' : ''}　${d.total}`)));

  box.replaceChildren(chips, deckView(decks.find(d => d.id === selDeckId)));
}

function deckView(deck) {
  const s = summarizeDeck(deck, cardsByImage);
  const sorted = [...deck.cards].sort((a, b) => String(a.card_no || a.image_file).localeCompare(String(b.card_no || b.image_file)));
  return h('div', {},
    h('div', { class: 'deck-head' },
      h('b', {}, deck.name),
      h('span', {}, `${deck.total} 張`),
      h('span', {}, `更新 ${fmtDate(deck.updatedMs)}`),
      deck.deleted ? h('span', {}, '已刪除') : null),
    h('div', { class: 'tags' },
      s.bySchool.map(x => h('span', { class: 'tag' }, `${x.label} ${x.count}`)),
      s.byCategory.map(x => h('span', { class: 'tag' }, `${x.label} ${x.count}`)),
      s.unknown ? h('span', { class: 'tag' }, `查無卡片資料 ${s.unknown}`) : null),
    h('div', { class: 'grid' }, sorted.map(c => {
      const card = cardsByImage[c.image_file];
      const label = card ? (card.name_zh || card.name) : c.image_file;
      return h('a', { class: 'c', href: `images/${c.image_file}`, target: '_blank', rel: 'noopener', title: `${c.card_no || ''} ${label}` },
        h('img', { src: `images/${c.image_file}`, alt: label, loading: 'lazy' }),
        h('span', { class: 'n' }, `×${cardCount(c)}`),
        h('div', { class: 't' }, label));
    })));
}

function renderSearch(box, q) {
  const hits = findDeckHits(accounts, q, cardsByImage);
  if (!hits.length) return box.replaceChildren(h('div', { class: 'msg' }, `沒有牌組放了「${q}」`));
  box.replaceChildren(
    h('div', { class: 'hint' }, `${hits.length} 副牌組放了「${q}」（依張數排序，不含已刪除與快速查詢）`),
    h('div', { class: 'list' }, hits.map(x => h('button', {
      class: 'row',
      // 跳過去之前先取消「只看 40 張」，否則被濾掉的牌組會悄悄換成別副顯示
      on: { click: () => { selUid = x.uid; selDeckId = x.deckId; $('q').value = ''; $('f-40').checked = false; render(); } },
    }, `${x.deckName}　×${x.count}`, h('span', { class: 'sub' }, `帳號 ${x.shortId}…`)))));
}

function bindUi() {
  $('tab-browse').addEventListener('click', () => { tab = 'browse'; render(); });
  $('tab-analysis').addEventListener('click', () => { tab = 'analysis'; render(); });
  for (const id of ['f-quick', 'f-empty', 'f-deleted', 'f-40']) $(id).addEventListener('change', renderDetail);
  $('q').addEventListener('input', renderDetail);
  $('btn-refresh').addEventListener('click', () => start(auth.currentUser));
  $('btn-login').addEventListener('click', () => window.hvCloudSync.signInWithGoogle().catch(e => showGate(`登入失敗：${e.message}`, true)));
  $('btn-logout').addEventListener('click', () => window.hvCloudSync.signOutUser());
}

async function start(user) {
  const decision = accessDecision(user, ADMIN_EMAIL, { wantsLogin });
  // replace 而不是 assign：免得使用者按上一頁又被彈回來，在兩頁之間彈跳
  if (decision === 'redirect') return void location.replace(HOME_URL);

  // 到這裡才讓畫面出現；'login' 只露出登入按鈕，標題仍然留白
  $('page-head').hidden = false;
  if (decision === 'allow') {
    document.title = PAGE_TITLE;
    $('page-title').textContent = PAGE_TITLE;
  }
  $('btn-login').hidden = !!user;
  $('btn-logout').hidden = !user;
  $('btn-refresh').hidden = true;
  if (decision === 'login') { $('status').textContent = '未登入'; return showGate('請先用管理者的 Google 帳號登入'); }
  $('gate').textContent = '載入中…';
  try {
    await loadAll();
    $('gate').hidden = true;
    $('app').hidden = false;
    $('btn-refresh').hidden = false;
  } catch (e) {
    $('status').textContent = '';
    showGate(e.code === 'permission-denied'
      ? '讀取被拒絕：Firestore 規則尚未允許管理者讀取（請先發布規則）'
      : `讀取失敗：${e.message}`, true);
  }
}

bindUi();
onAuthStateChanged(auth, user => { start(user); });
