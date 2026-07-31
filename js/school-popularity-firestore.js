// 熱門學校標籤的 Firestore 讀寫，沿用 js/cloud-sync.js 已經初始化好的
// Firebase app 實例（不重新 initializeApp，避免建立第二個 app）。
// 寫入路徑跟牌組同步的 /users/{uid}/... 完全分開、不需要登入——這份計數
// 涵蓋所有訪客的瀏覽行為，不受雲端同步開關影響。
import { app } from './cloud-sync.js';
import {
  getFirestore,
  connectFirestoreEmulator,
  doc,
  getDoc,
  setDoc,
  increment,
} from 'https://www.gstatic.com/firebasejs/10.12.4/firebase-firestore.js';

const db = getFirestore(app);
// 手動測試用開關：網址帶 ?use-emulator 才會接本地 Firestore emulator
// （見 firebase.json / firestore.rules），預設一律連正式環境，不會誤連。
if (new URLSearchParams(location.search).has('use-emulator')) {
  connectFirestoreEmulator(db, '127.0.0.1', 8080);
}
const POPULARITY_DOC = doc(db, 'school-popularity', 'counts');

/** @returns {Promise<import('./school-popularity-types.js').LastSyncedSnapshot>} */
export async function fetchSchoolPopularitySnapshot() {
  const snap = await getDoc(POPULARITY_DOC);
  return snap.exists() ? snap.data() : {};
}

/** @param {import('./school-popularity-types.js').IncrementPayload} payload */
export async function flushSchoolPopularityIncrement(payload) {
  const incrementFields = {};
  for (const [school, delta] of Object.entries(payload)) {
    incrementFields[school] = increment(delta);
  }
  // setDoc + merge（而非 updateDoc）：文件第一次寫入前還不存在時，
  // updateDoc 的 increment 會因為找不到文件直接失敗，setDoc+merge 則會
  // 把 increment 當成「從 0 開始累加」正確建立文件。
  await setDoc(POPULARITY_DOC, incrementFields, { merge: true });
}
