// 熱門學校標籤：不碰 DOM／Firestore 的純函式，見 docs/adr/0005。

import { isValidSchoolKey } from './school-constants.js';

/**
 * 算出要顯示在「熱門學校標籤」下拉清單裡的學校 key 排行。
 * 冷啟動（快照為空，尚無任何真實計數）時直接回傳固定預設排序，不做排序運算。
 *
 * @param {import('./school-popularity-types.js').LastSyncedSnapshot} lastSyncedSnapshot
 * @param {readonly string[]} fallbackOrder 冷啟動時使用的固定預設排序（沿用 index.html 的 schoolOrder）
 * @param {number} [limit=8]
 * @returns {string[]}
 */
export function computeTopSchools(lastSyncedSnapshot, fallbackOrder, limit = 8) {
  const hasAnyCount = Object.keys(lastSyncedSnapshot).length > 0;
  if (!hasAnyCount) {
    return fallbackOrder.slice(0, limit);
  }

  return Object.entries(lastSyncedSnapshot)
    .sort(([, countA], [, countB]) => countB - countA)
    .slice(0, limit)
    .map(([school]) => school);
}

/**
 * @typedef {{
 *   pendingDelta: import('./school-popularity-types.js').PendingDelta,
 *   lastSyncedSnapshot: import('./school-popularity-types.js').LastSyncedSnapshot,
 * }} ViewCountState
 */

/**
 * 卡片被點開時呼叫：把 card.school_tags（或 fallback [card.school]）裡每個
 * 白名單內的學校標籤各自在 pendingDelta +1。不做防重複/節流——同一張卡
 * 反覆點開，每次都要讓對應學校再 +1。白名單外的 key 直接忽略，不寫入
 * pendingDelta。回傳新的 state，不修改傳入的 state。
 *
 * @param {ViewCountState} state
 * @param {{school?: string, school_tags?: string[]}} card
 * @returns {ViewCountState}
 */
export function addView(state, card) {
  const schools = card.school_tags || (card.school ? [card.school] : []);
  const nextPendingDelta = { ...state.pendingDelta };
  for (const school of schools) {
    if (!isValidSchoolKey(school)) continue;
    nextPendingDelta[school] = (nextPendingDelta[school] || 0) + 1;
  }
  return { ...state, pendingDelta: nextPendingDelta };
}

/**
 * 把目前 pendingDelta 轉換成要送給 Firestore atomic increment 呼叫的
 * payload（只送增量，不送整份總量）。pendingDelta 為空時回傳 null，
 * 代表「不需要同步」。
 *
 * @param {ViewCountState} state
 * @returns {import('./school-popularity-types.js').IncrementPayload | null}
 */
export function buildIncrementPayload(state) {
  if (Object.keys(state.pendingDelta).length === 0) return null;
  return { ...state.pendingDelta };
}

/**
 * 同步成功後呼叫，清空已送出的 pendingDelta。
 *
 * @param {ViewCountState} state
 * @returns {ViewCountState}
 */
export function onFlushSuccess(state) {
  return { ...state, pendingDelta: {} };
}

/**
 * 同步失敗後呼叫，保留 pendingDelta 供下次重試，state 原封不動。
 *
 * @param {ViewCountState} state
 * @returns {ViewCountState}
 */
export function onFlushFailure(state) {
  return state;
}

/**
 * 頁面載入時，把從 Firestore 讀到的快照併入 lastSyncedSnapshot，不影響
 * 既有的 pendingDelta。
 *
 * @param {ViewCountState} state
 * @param {import('./school-popularity-types.js').LastSyncedSnapshot} remoteSnapshot
 * @returns {ViewCountState}
 */
export function applySnapshot(state, remoteSnapshot) {
  return { ...state, lastSyncedSnapshot: { ...state.lastSyncedSnapshot, ...remoteSnapshot } };
}
