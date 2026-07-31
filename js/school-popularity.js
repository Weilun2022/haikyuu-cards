// 熱門學校標籤：不碰 DOM／Firestore 的純函式，見 docs/adr/0005。

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
