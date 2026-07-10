// 牌組雲端同步 v2：Google 登入 + Firestore 自動同步（安全版）
// 專案：haikyuu-cards-cloud（與 game.html 的 BYO Firebase 完全分開，見 firebase-config.js 註解）
//
// 核心原則（v1 上線後使用者回報「重整頁面一直跳提示」+ 要求刪除保護，v2 重新設計）：
//   1. 自動同步只做新增/更新（upsert），永遠不會用「本機沒有這副牌組」去推斷要刪雲端。
//   2. 真正的刪除只有兩種來源：使用者明確按刪除鈕（本機 pendingDeletes 佇列）、
//      或雲端 tombstone（另一台裝置刪除，且本機沒改過這副牌）。
//   3. 本機資料無故消失（清快取/bug/被清空）且沒有 pendingDeletes 紀錄時，一律視為「本機遺失」，
//      自動從雲端救回，不會把雲端也清空。
//   4. 用 baseline manifest（每副牌組上次成功同步時的 contentHash）判斷「這裡到底變了沒」，
//      兩邊一致就完全安靜跳過，不再每次重整頁面都跳互動提示。
//   5. 真的雙邊同時改到同一副牌組且內容不同（少見）→ 不阻斷、不跳窗，直接比照 v1 的作法把
//      雲端版本另存成「（雲端衝突副本）」，本機原本的版本保留，兩邊都不丟資料，只用 toast 通知。
//
// 對外介面掛在 window.hvCloudSync，讓 index.html 的傳統 <script> 可以直接呼叫。

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
  deleteDoc,
  writeBatch,
  serverTimestamp
} from 'https://www.gstatic.com/firebasejs/10.12.4/firebase-firestore.js';

const SCHEMA_VERSION = 1;
// 軟刪除的 tombstone 存在超過這個天數，代表早就同步擴散到所有裝置了，下次同步時真的清掉
// （tombstone 存在的唯一目的是讓其他裝置知道「這是使用者自己刪的」，不是給使用者反悔用——
// UI 上本來就沒有復原功能，超過這個天數留著也沒意義，只會讓 Firestore 文件數一直往上累積）
const TOMBSTONE_GC_DAYS = 30;

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
await setPersistence(auth, browserLocalPersistence);

// ── 本機同步狀態（每個 uid 一份，記 baseline / 待刪除 / 待上傳）──────────
function syncStateKey(uid) { return `hv_cloud_sync_state:${uid}`; }
function loadSyncState(uid) {
  try {
    const s = JSON.parse(localStorage.getItem(syncStateKey(uid)) || '{}');
    if (!s.baseline) s.baseline = {};
    if (!s.pendingDeletes) s.pendingDeletes = {};
    if (!s.pendingRisky) s.pendingRisky = {};
    if (!s.dirty) s.dirty = {};
    if (!s.favoritesBaseline) s.favoritesBaseline = null; // null = 從沒同步過
    return s;
  } catch {
    return { baseline: {}, pendingDeletes: {}, pendingRisky: {}, dirty: {}, favoritesBaseline: null };
  }
}
function saveSyncState(uid, state) { localStorage.setItem(syncStateKey(uid), JSON.stringify(state)); }

// ── 內容雜湊（判斷某副牌組本機/雲端是否真的不同）─────────────────────────
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

// ── 狀態通知（登入狀態 / 同步中 / 有無待處理變更）─────────────────────────
let _syncing = false;
let _hasPending = false;
let _hasPendingDeletes = false; // 有牌組已在本機刪除，但還沒手動同步推上雲端 tombstone
const _statusListeners = [];
function getStatus() { return { user: auth.currentUser, syncing: _syncing, hasPending: _hasPending, hasPendingDeletes: _hasPendingDeletes }; }
function onStatusChange(cb) { _statusListeners.push(cb); }
function _notifyStatus() { _statusListeners.forEach(cb => cb(getStatus())); }

function _recomputePending(uid) {
  if (!uid) { _hasPending = false; _hasPendingDeletes = false; return; }
  const s = loadSyncState(uid);
  _hasPendingDeletes = Object.keys(s.pendingDeletes).length > 0 || Object.keys(s.pendingRisky).length > 0;
  _hasPending = Object.keys(s.dirty).length > 0 || _hasPendingDeletes;
}

// 本機牌組新增/修改時呼叫：只記錄「這副牌組髒了」，實際上傳交給 autoReconcile
function markDirty(uid, deckId) {
  if (!uid) return;
  const s = loadSyncState(uid);
  s.dirty[deckId] = true;
  saveSyncState(uid, s);
  _hasPending = true;
  _notifyStatus();
}

// 使用者明確按下刪除牌組時呼叫（要在從本機陣列移除之前呼叫）
function queuePendingDelete(uid, deckId) {
  if (!uid) return;
  const s = loadSyncState(uid);
  s.pendingDeletes[deckId] = true;
  delete s.dirty[deckId];
  delete s.baseline[deckId];
  saveSyncState(uid, s);
  _hasPending = true;
  _hasPendingDeletes = true;
  _notifyStatus();
}

// 使用者做了「清空牌組」這類把內容整個歸零、但牌組本身還在的高風險編輯時呼叫。
// 效果比照 pendingDelete：自動同步不會把這個變更推上雲端，只有手動同步才會確認。
function markRisky(uid, deckId) {
  if (!uid) return;
  const s = loadSyncState(uid);
  s.pendingRisky[deckId] = true;
  saveSyncState(uid, s);
  _hasPending = true;
  _hasPendingDeletes = true;
  _notifyStatus();
}

const _authListeners = [];
function onAuthChange(cb) { _authListeners.push(cb); }
onAuthStateChanged(auth, user => {
  _recomputePending(user?.uid);
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

// 回傳 { active: {id: hash}, docs: {id: 完整文件（含 deleted 版本）} }
async function fetchCloudState(uid) {
  const snap = await getDocs(decksCollection(uid));
  const active = {};
  const docs = {};
  snap.docs.forEach(d => {
    const data = d.data();
    docs[d.id] = { id: d.id, ...data };
    if (!data.deleted) active[d.id] = data.contentHash;
  });
  return { active, docs };
}

async function ensureUserDoc(uid) {
  const ref = doc(db, 'users', uid);
  await setDoc(ref, {
    ownerUid: uid,
    schemaVersion: SCHEMA_VERSION,
    updatedAt: serverTimestamp()
  }, { merge: true });
}

function deckDocPayload(uid, deck, color, hash, existing) {
  return {
    ownerUid: uid,
    schemaVersion: SCHEMA_VERSION,
    deck,
    color: color ?? null,
    contentHash: hash,
    clientUpdatedAt: Date.now(),
    deleted: false,
    deletedAt: null,
    createdAt: existing ? existing.createdAt : serverTimestamp(),
    updatedAt: serverTimestamp()
  };
}

// ══════════════════════════════════════════════════════
// 自動同步核心：只做安全的 upsert / 下載 / 明確刪除，永遠不會用
// 「本機少了這個 id」去推斷要刪雲端。
// ══════════════════════════════════════════════════════
//
// 回傳結果讓呼叫端（index.html）決定怎麼套用到本機 localStorage：
// {
//   applyDownload: [{ id, deck, color }],   // 要寫回本機的 deck（新增或覆蓋）
//   applyRemoveLocal: [id, ...],            // 要從本機移除的 deck id（雲端刪除且本機沒改過）
//   restoredFromLoss: boolean,              // 是否偵測到本機資料異常遺失並自動救回
//   conflictCount: number                   // 有幾副牌組發生雙邊衝突（已自動建副本，不阻斷）
// }
// pushDeletes=false（預設）：自動觸發的同步（登入、切回分頁、編輯 debounce）一律不會把待刪除
// 的牌組真的從雲端移除，只是先擱置——雲端那份原封不動，「用雲端覆蓋本機」隨時都能找回來。
// 只有使用者手動按「立即同步」（pushDeletes=true）才會真的把待刪除的牌組推上雲端 tombstone。
async function autoReconcile(uid, localDecks, localColors, { pushDeletes = false } = {}) {
  if (_syncing) return null;
  _syncing = true;
  _notifyStatus();

  try {
    const state = loadSyncState(uid);
    const cloud = await fetchCloudState(uid);
    const localMap = new Map(localDecks.map(d => [d.id, d]));

    const localHashes = {};
    for (const d of localDecks) localHashes[d.id] = await contentHashOf(d, localColors[d.id] ?? null);

    const allIds = new Set([
      ...localMap.keys(),
      ...Object.keys(cloud.active),
      ...Object.keys(cloud.docs).filter(id => cloud.docs[id].deleted)
    ]);

    const toUploadIds = [];
    const applyDownload = [];
    const applyRemoveLocal = [];
    const toSoftDelete = [];
    const toHardDelete = [];
    let restoredFromLoss = false;
    let conflictCount = 0;

    const isTombstoneOld = cloudDoc => {
      const deletedAtMs = cloudDoc?.deletedAt?.toMillis?.();
      return !!deletedAtMs && (Date.now() - deletedAtMs) > TOMBSTONE_GC_DAYS * 24 * 60 * 60 * 1000;
    };

    for (const id of allIds) {
      const hasLocal = localMap.has(id);
      const localHash = localHashes[id];
      const baseHash = state.baseline[id];
      const cloudDoc = cloud.docs[id];
      const cloudDeleted = cloudDoc?.deleted === true;
      const cloudHash = cloudDeleted ? null : cloud.active[id];
      const pendingDelete = !!state.pendingDeletes[id];
      // 使用者做過「清空牌組」這類把內容整個歸零、但牌組本身還在的高風險編輯：
      // 跟 pendingDelete 一樣，自動同步不會把這個變更推上雲端，只有手動同步才確認
      const pendingRisky = !!state.pendingRisky[id];

      // 1. 使用者明確刪除過（本機已經沒有這副牌）
      if (pendingDelete) {
        if (cloudDeleted) { delete state.pendingDeletes[id]; continue; }
        if (pushDeletes) {
          // 使用者手動按了「立即同步」，這時候才真的推上雲端 tombstone
          toSoftDelete.push(id);
        }
        // pushDeletes=false：先擱置，雲端這份完全不動，也不要被其他規則誤判成
        // 「本機遺失」而自動救回本機（那樣等於默默撤銷使用者剛做的刪除）
        continue;
      }

      // 2. 雲端是 tombstone（可能是別台裝置刪的）
      if (cloudDeleted) {
        if (!hasLocal) {
          delete state.baseline[id];
          // tombstone 存在夠久了（早就同步擴散開了），順便真的清掉這份文件，不要一直累積
          if (isTombstoneOld(cloudDoc)) toHardDelete.push(id);
          continue;
        }
        if (localHash === baseHash) {
          // 本機沒改過這副牌，套用雲端的刪除
          applyRemoveLocal.push(id);
          if (isTombstoneOld(cloudDoc)) toHardDelete.push(id);
        } else {
          // 本機改過、雲端卻刪了 → 不要默默丟掉本機的修改，保留本機，
          // 清掉 baseline 讓它在下一輪被當成「新牌組」自動重新上傳（等於復活這副牌）
          // 注意：這種情況不能順便 GC，因為等等會把它當新牌組重新寫回去
          delete state.baseline[id];
          toUploadIds.push(id);
        }
        continue;
      }

      // 3. 本機沒有、雲端有 active 資料、也沒有 pendingDelete
      //    → 本機遺失保護：一律視為意外遺失（清快取/bug），自動從雲端救回，絕不刪雲端
      if (!hasLocal && cloudDoc) {
        applyDownload.push({ id, deck: cloudDoc.deck, color: cloudDoc.color ?? null });
        restoredFromLoss = true;
        continue;
      }

      // 4. 雲端從沒同步過這副牌 → 上傳
      if (hasLocal && !cloudDoc) {
        toUploadIds.push(id);
        continue;
      }

      // 5. 兩邊都有資料
      if (localHash === cloudHash) {
        state.baseline[id] = localHash;
        delete state.dirty[id];
        continue;
      }

      const localChanged = localHash !== baseHash;
      const cloudChanged  = cloudHash !== baseHash;

      if (localChanged && !cloudChanged) {
        if (pendingRisky && !pushDeletes) continue; // 清空過還沒手動確認，先擱置，雲端不動
        if (pendingRisky) delete state.pendingRisky[id]; // pushDeletes=true：這就是使用者的確認動作
        toUploadIds.push(id);
        continue;
      }
      if (!localChanged && cloudChanged) {
        applyDownload.push({ id, deck: cloudDoc.deck, color: cloudDoc.color ?? null });
        continue;
      }

      // 兩邊都改了，且內容不同 → 真衝突。不阻斷：本機保留原樣（重新確認上傳），
      // 雲端版本另存成衝突副本，兩邊資料都不丟。
      if (pendingRisky && !pushDeletes) continue; // 清空過還沒手動確認，先擱置，連衝突副本都先不建立
      if (pendingRisky) delete state.pendingRisky[id];
      conflictCount++;
      const conflictId = `${id}_cloud_${Date.now()}_${Math.floor(Math.random() * 10000)}`;
      const conflictDeck = JSON.parse(JSON.stringify(cloudDoc.deck));
      conflictDeck.id = conflictId;
      conflictDeck.name = `${conflictDeck.name || '未命名牌組'}（雲端衝突副本）`;
      applyDownload.push({ id: conflictId, deck: conflictDeck, color: cloudDoc.color ?? null });
      toUploadIds.push(id);
    }

    // ── 寫入雲端：新增/更新 ──
    if (toUploadIds.length > 0) {
      await ensureUserDoc(uid);
      const batch = writeBatch(db);
      for (const id of toUploadIds) {
        const deck = localMap.get(id);
        if (!deck) continue; // 理論上不會發生（toUploadIds 只會放本機有的 id）
        const color = localColors[id] ?? null;
        const hash = localHashes[id];
        const existing = cloud.docs[id];
        batch.set(doc(db, 'users', uid, 'decks', id), deckDocPayload(uid, deck, color, hash, existing));
        state.baseline[id] = hash;
        delete state.dirty[id];
      }
      await batch.commit();
    }

    // ── 寫入雲端：明確刪除（tombstone）──
    if (toSoftDelete.length > 0) {
      const batch = writeBatch(db);
      for (const id of toSoftDelete) {
        const existing = cloud.docs[id];
        batch.set(doc(db, 'users', uid, 'decks', id), {
          ownerUid: uid,
          schemaVersion: SCHEMA_VERSION,
          deck: existing?.deck ?? { id, name: '', cards: [] },
          color: existing?.color ?? null,
          contentHash: existing?.contentHash ?? '',
          clientUpdatedAt: Date.now(),
          deleted: true,
          deletedAt: serverTimestamp(),
          createdAt: existing ? existing.createdAt : serverTimestamp(),
          updatedAt: serverTimestamp()
        }, { merge: true });
        delete state.pendingDeletes[id];
      }
      await batch.commit();
    }

    // ── 清掉早就標記刪除超過 TOMBSTONE_GC_DAYS 天的 tombstone，避免文件數一直累積 ──
    // （這時候擴散給其他裝置的任務早就完成了，留著沒有意義）
    if (toHardDelete.length > 0) {
      const batch = writeBatch(db);
      for (const id of toHardDelete) batch.delete(doc(db, 'users', uid, 'decks', id));
      await batch.commit();
    }

    saveSyncState(uid, state);
    _recomputePending(uid);
    return {
      applyDownload, applyRemoveLocal, restoredFromLoss, conflictCount,
      deletesPushed: toSoftDelete.length,
      pendingDeleteCount: Object.keys(state.pendingDeletes).length,
      tombstonesPurged: toHardDelete.length
    };
  } finally {
    _syncing = false;
    _notifyStatus();
  }
}

// 同步完下載/移除本機牌組後，呼叫這個讓 baseline 對齊新狀態（避免下一輪又被當成本機變更上傳）
function commitLocalBaseline(uid, decks, colors) {
  return (async () => {
    const state = loadSyncState(uid);
    for (const d of decks) {
      state.baseline[d.id] = await contentHashOf(d, colors[d.id] ?? null);
    }
    saveSyncState(uid, state);
  })();
}

// ══════════════════════════════════════════════════════
// 我的最愛（單卡收藏，跟牌組系統完全獨立）
// Firestore 路徑：/users/{uid}/favorites/main（跟 /decks 分開，schema 不共用，
// 避免收藏清單被硬塞進牌組驗證規則）。用三方合併（baseline/本機/雲端）同步：
// 任一邊新增就保留、baseline 有但任一邊移除了才視為刪除。
// ══════════════════════════════════════════════════════

function favoritesDocRef(uid) {
  return doc(db, 'users', uid, 'favorites', 'main');
}
async function favoritesHashOf(items) {
  return sha256Hex('favorites:v1\n' + items.join('\n'));
}
function mergeFavoriteSets(baseItems, localItems, remoteItems) {
  const base = new Set(baseItems || []);
  const local = new Set(localItems || []);
  const remote = new Set(remoteItems || []);
  const all = new Set([...base, ...local, ...remote]);
  const out = new Set();
  for (const id of all) {
    const inBase = base.has(id), inLocal = local.has(id), inRemote = remote.has(id);
    if (!inBase) { if (inLocal || inRemote) out.add(id); }
    else { if (inLocal && inRemote) out.add(id); }
  }
  return Array.from(out).sort();
}

// 回傳 { items, changed }。items 是合併後應套用到本機的最終清單；
// changed=true 代表跟傳入的 localItems 不同，呼叫端要把它寫回本機。
async function reconcileFavorites(uid, localItems) {
  const state = loadSyncState(uid);
  const local = Array.from(new Set(localItems || [])).sort();
  const ref = favoritesDocRef(uid);
  const snap = await getDoc(ref);

  if (!snap.exists()) {
    if (local.length === 0) return { items: local, changed: false };
    const hash = await favoritesHashOf(local);
    await setDoc(ref, {
      ownerUid: uid, schemaVersion: SCHEMA_VERSION,
      items: local, itemCount: local.length, contentHash: hash,
      clientUpdatedAt: Date.now(), createdAt: serverTimestamp(), updatedAt: serverTimestamp()
    });
    state.favoritesBaseline = local;
    saveSyncState(uid, state);
    return { items: local, changed: false };
  }

  const remoteData = snap.data();
  const remote = Array.from(new Set(remoteData.items || [])).sort();

  // 沒有 baseline（例如換新裝置）：用聯集，不要讓任一邊默默蓋掉另一邊
  const merged = state.favoritesBaseline === null
    ? Array.from(new Set([...local, ...remote])).sort()
    : mergeFavoriteSets(state.favoritesBaseline, local, remote);

  const mergedHash = await favoritesHashOf(merged);
  if (mergedHash !== remoteData.contentHash) {
    await setDoc(ref, {
      ownerUid: uid, schemaVersion: SCHEMA_VERSION,
      items: merged, itemCount: merged.length, contentHash: mergedHash,
      clientUpdatedAt: Date.now(), createdAt: remoteData.createdAt, updatedAt: serverTimestamp()
    });
  }

  state.favoritesBaseline = merged;
  saveSyncState(uid, state);

  const changed = JSON.stringify(merged) !== JSON.stringify(local);
  return { items: merged, changed };
}

// ══════════════════════════════════════════════════════
// 手動破壞性操作（保留給進階使用者，永遠不會被自動同步呼叫）
// ══════════════════════════════════════════════════════

// 用本機覆蓋雲端：雲端多出的 deck 一律標成 tombstone（不 hard delete）
async function replaceCloudWithLocalDestructive(uid, localDecks, localColors) {
  await ensureUserDoc(uid);
  const cloud = await fetchCloudState(uid);
  const localIds = new Set(localDecks.map(d => d.id));
  const batch = writeBatch(db);
  const state = loadSyncState(uid);

  for (const deck of localDecks) {
    const color = localColors[deck.id] ?? null;
    const hash = await contentHashOf(deck, color);
    const existing = cloud.docs[deck.id];
    batch.set(doc(db, 'users', uid, 'decks', deck.id), deckDocPayload(uid, deck, color, hash, existing));
    state.baseline[deck.id] = hash;
    delete state.dirty[deck.id];
  }
  for (const id of Object.keys(cloud.active)) {
    if (localIds.has(id)) continue;
    const existing = cloud.docs[id];
    batch.set(doc(db, 'users', uid, 'decks', id), {
      ownerUid: uid, schemaVersion: SCHEMA_VERSION,
      deck: existing.deck, color: existing.color ?? null, contentHash: existing.contentHash,
      clientUpdatedAt: Date.now(), deleted: true, deletedAt: serverTimestamp(),
      createdAt: existing.createdAt, updatedAt: serverTimestamp()
    }, { merge: true });
    delete state.baseline[id];
  }
  await batch.commit();
  state.pendingDeletes = {};
  saveSyncState(uid, state);
  _recomputePending(uid);
}

// 用雲端覆蓋本機：回傳 { decks, colors } 給呼叫端寫入 localStorage
async function downloadCloudToLocalDestructive(uid) {
  const cloud = await fetchCloudState(uid);
  const decks = [];
  const colors = {};
  const state = loadSyncState(uid);
  state.baseline = {};
  Object.values(cloud.docs).forEach(d => {
    if (d.deleted) return;
    decks.push(d.deck);
    if (d.color != null) colors[d.id] = d.color;
    state.baseline[d.id] = d.contentHash;
  });
  state.dirty = {};
  state.pendingDeletes = {};
  saveSyncState(uid, state);
  _recomputePending(uid);
  return { decks, colors };
}

window.hvCloudSync = {
  signInWithGoogle,
  signOutUser,
  onAuthChange,
  onStatusChange,
  getStatus,
  markDirty,
  queuePendingDelete,
  markRisky,
  autoReconcile,
  commitLocalBaseline,
  reconcileFavorites,
  replaceCloudWithLocalDestructive,
  downloadCloudToLocalDestructive,
  get currentUser() { return auth.currentUser; }
};
window.dispatchEvent(new CustomEvent('hv-cloud-sync-ready'));
