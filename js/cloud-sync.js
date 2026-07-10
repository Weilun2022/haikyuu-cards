// 牌組雲端同步：Google 登入 + Firestore 備份/還原
// 專案：haikyuu-cards-cloud（與 game.html 的 BYO Firebase 完全分開，見 firebase-config.js 註解）
//
// 對外介面掛在 window.hvCloudSync，讓 index.html 的傳統 <script> 可以直接呼叫
// （index.html 目前沒有改成 type="module"，用 window 橋接是最小改動的做法）。

import { firebaseConfig } from './firebase-config.js';
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.4/firebase-app.js';
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  setPersistence,
  browserLocalPersistence
} from 'https://www.gstatic.com/firebasejs/10.12.4/firebase-auth.js';
import {
  getFirestore,
  collection,
  doc,
  getDoc,
  getDocs,
  setDoc,
  writeBatch,
  serverTimestamp
} from 'https://www.gstatic.com/firebasejs/10.12.4/firebase-firestore.js';

const SCHEMA_VERSION = 1;
const DECK_META_KEY = 'hv_deck_meta'; // { [deckId]: { updatedAt } } — 只用於本機顯示狀態，不參與安全性判斷

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
await setPersistence(auth, browserLocalPersistence);

// ── 本機 meta（僅供 UI 顯示「本機有未上傳變更」，不影響雲端資料正確性）──
function loadDeckMeta() {
  try { return JSON.parse(localStorage.getItem(DECK_META_KEY) || '{}'); } catch { return {}; }
}
function saveDeckMeta(meta) { localStorage.setItem(DECK_META_KEY, JSON.stringify(meta)); }

// ── 內容雜湊（判斷本機/雲端該副牌組是否真的有變更，避免不必要的寫入）──
function stableStringify(obj) {
  if (obj === null || typeof obj !== 'object') return JSON.stringify(obj);
  if (Array.isArray(obj)) return '[' + obj.map(stableStringify).join(',') + ']';
  return '{' + Object.keys(obj).sort().map(k => JSON.stringify(k) + ':' + stableStringify(obj[k])).join(',') + '}';
}
async function sha256Hex(str) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
}
async function contentHashOf(deck, color) {
  return sha256Hex(stableStringify({ deck, color: color ?? null }));
}

// ── 狀態通知（登入狀態 / 是否有未上傳變更）──
let _hasLocalChanges = false;
const _statusListeners = [];
function getStatus() { return { user: auth.currentUser, hasLocalChanges: _hasLocalChanges }; }
function onStatusChange(cb) { _statusListeners.push(cb); }
function _notifyStatus() { _statusListeners.forEach(cb => cb(getStatus())); }

function markDirty(deckId) {
  const meta = loadDeckMeta();
  meta[deckId] = { updatedAt: Date.now() };
  saveDeckMeta(meta);
  _hasLocalChanges = true;
  _notifyStatus();
}

const _authListeners = [];
function onAuthChange(cb) { _authListeners.push(cb); }
onAuthStateChanged(auth, user => {
  _authListeners.forEach(cb => cb(user));
  _notifyStatus();
});

// ── 登入 / 登出 ──
async function signInWithGoogle() {
  const provider = new GoogleAuthProvider();
  await signInWithPopup(auth, provider);
}
async function signOutUser() {
  await signOut(auth);
}

// ── Firestore 存取 ──
function decksCollection(uid) {
  return collection(db, 'users', uid, 'decks');
}

async function fetchCloudDecks(uid) {
  const snap = await getDocs(decksCollection(uid));
  return snap.docs.map(d => ({ id: d.id, ...d.data() }));
}

async function ensureUserDoc(uid) {
  const ref = doc(db, 'users', uid);
  const snap = await getDoc(ref);
  if (!snap.exists()) {
    await setDoc(ref, {
      ownerUid: uid,
      schemaVersion: SCHEMA_VERSION,
      createdAt: serverTimestamp(),
      updatedAt: serverTimestamp()
    });
  }
}

// 上傳本機到雲端：雲端變成本機目前狀態（只寫真的變更過的 deck，刪除本機已不存在的）
async function uploadLocalToCloud(uid, localDecks, localColors) {
  await ensureUserDoc(uid);
  const cloudDecks = await fetchCloudDecks(uid);
  const cloudMap = new Map(cloudDecks.map(d => [d.id, d]));
  const batch = writeBatch(db);
  let hasOps = false;

  for (const deck of localDecks) {
    const color = localColors[deck.id] ?? null;
    const hash = await contentHashOf(deck, color);
    const existing = cloudMap.get(deck.id);
    cloudMap.delete(deck.id);
    if (existing && existing.contentHash === hash) continue; // 沒變，略過

    const ref = doc(db, 'users', uid, 'decks', deck.id);
    batch.set(ref, {
      ownerUid: uid,
      schemaVersion: SCHEMA_VERSION,
      deck,
      color,
      clientUpdatedAt: Date.now(),
      contentHash: hash,
      createdAt: existing ? existing.createdAt : serverTimestamp(),
      updatedAt: serverTimestamp()
    });
    hasOps = true;
  }

  // 雲端有但本機已刪除的 deck，一併刪除
  for (const leftoverId of cloudMap.keys()) {
    batch.delete(doc(db, 'users', uid, 'decks', leftoverId));
    hasOps = true;
  }

  if (hasOps) await batch.commit();

  _hasLocalChanges = false;
  saveDeckMeta({});
  _notifyStatus();
}

// 從雲端下載到本機：回傳 { decks, colors }，由呼叫端負責寫入 localStorage
async function downloadCloudToLocal(uid) {
  const cloudDecks = await fetchCloudDecks(uid);
  const decks = cloudDecks.map(d => d.deck);
  const colors = {};
  cloudDecks.forEach(d => { if (d.color != null) colors[d.id] = d.color; });
  _hasLocalChanges = false;
  saveDeckMeta({});
  _notifyStatus();
  return { decks, colors };
}

// 合併本機與雲端：deck 級別比對，內容不同時本機保留原 id、雲端版本另存衝突副本
// （不做時間戳「誰比較新」判斷——本機目前沒有可靠的跨裝置時鐘可比，寧可多一份副本也不要默默蓋掉資料）
// 合併結果會寫回本機（由呼叫端存 localStorage）並同步上傳回雲端
async function mergeLocalAndCloud(uid, localDecks, localColors) {
  const cloudDecks = await fetchCloudDecks(uid);
  const cloudMap = new Map(cloudDecks.map(d => [d.id, d]));
  const localMap = new Map(localDecks.map(d => [d.id, d]));
  const allIds = new Set([...localMap.keys(), ...cloudMap.keys()]);

  const resultDecks = [];
  const resultColors = {};

  for (const id of allIds) {
    const l = localMap.get(id);
    const c = cloudMap.get(id);

    if (l && !c) {
      resultDecks.push(l);
      if (localColors[id] != null) resultColors[id] = localColors[id];
      continue;
    }
    if (!l && c) {
      resultDecks.push(c.deck);
      if (c.color != null) resultColors[id] = c.color;
      continue;
    }

    const lColor = localColors[id] ?? null;
    const lHash = await contentHashOf(l, lColor);
    if (lHash === c.contentHash) {
      resultDecks.push(l);
      if (lColor != null) resultColors[id] = lColor;
      continue;
    }

    // 內容衝突：本機保留原 id，雲端版本另存為衝突副本，兩邊都不丟
    resultDecks.push(l);
    if (lColor != null) resultColors[id] = lColor;

    const conflictId = `${id}_cloud_${Date.now()}_${Math.floor(Math.random() * 10000)}`;
    const conflictDeck = JSON.parse(JSON.stringify(c.deck));
    conflictDeck.id = conflictId;
    conflictDeck.name = `${conflictDeck.name || '未命名牌組'}（雲端衝突副本）`;
    resultDecks.push(conflictDeck);
    if (c.color != null) resultColors[conflictId] = c.color;
  }

  await uploadLocalToCloud(uid, resultDecks, resultColors);
  return { decks: resultDecks, colors: resultColors };
}

window.hvCloudSync = {
  signInWithGoogle,
  signOutUser,
  onAuthChange,
  onStatusChange,
  getStatus,
  markDirty,
  fetchCloudDecks,
  uploadLocalToCloud,
  downloadCloudToLocal,
  mergeLocalAndCloud,
  get currentUser() { return auth.currentUser; }
};
window.dispatchEvent(new CustomEvent('hv-cloud-sync-ready'));
