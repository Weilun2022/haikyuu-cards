// 熱門學校標籤本地狀態與 Firestore payload 的欄位形狀定義。
// 純 JSDoc typedef（這個專案沒有 TypeScript 建置流程），供 school-popularity.js
// 直接參照，避免三種形狀互相混用賦值。
//
// - PendingDelta 只會被本地點擊行為遞增、同步成功後清空；
// - LastSyncedSnapshot 只會被「讀回雲端快照」寫入，本地點擊不會直接改到它；
// - IncrementPayload 是要送給 Firestore atomic increment 呼叫的「純差值」，
//   絕不是 LastSyncedSnapshot 的整份覆寫（呼應 ADR 0001 的 last-write-wins
//   是牌組同步專屬決策，本功能刻意改用 atomic increment，不沿用整份覆蓋）。
// 三者 key 皆須是 school-constants.js 的 SCHOOL_KEYS 白名單成員，value 皆為
// 非負整數。

/**
 * @typedef {Object<string, number>} PendingDelta
 * 本次瀏覽期間，尚未同步到雲端的各學校增量計數。
 * 例：{ '烏野': 3, 'ユース': 1 }
 */

/**
 * @typedef {Object<string, number>} LastSyncedSnapshot
 * 頁面載入時從 Firestore 讀回的雲端目前總量快照，用來計算熱門排行。
 * 例：{ '烏野': 128, '音駒': 97 }
 */

/**
 * @typedef {Object<string, number>} IncrementPayload
 * 要送給 Firestore atomic increment 呼叫的差值 payload（只送 +N，不送總量）。
 * 例：{ '烏野': 3, 'ユース': 1 }
 */

export {};
