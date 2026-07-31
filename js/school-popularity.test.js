import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  computeTopSchools,
  addView,
  buildIncrementPayload,
  onFlushSuccess,
  onFlushFailure,
  applySnapshot,
} from './school-popularity.js';
import { SCHOOL_KEYS } from './school-constants.js';
import { CARD_FIXTURES } from './card-fixtures.js';

test('空快照（冷啟動）時回傳固定預設排序截到上限筆數', () => {
  const result = computeTopSchools({}, SCHOOL_KEYS, 8);
  assert.deepEqual(result, SCHOOL_KEYS.slice(0, 8));
});

test('有真實計數時依數值由高到低排序回傳前N筆', () => {
  const snapshot = { '烏野': 10, '音駒': 30, 'ユース': 20 };
  const result = computeTopSchools(snapshot, SCHOOL_KEYS, 8);
  assert.deepEqual(result, ['音駒', 'ユース', '烏野']);
});

test('計數筆數少於上限時全部回傳，不會出現缺漏', () => {
  const snapshot = { '梟谷': 4, '鴎台': 9 };
  const result = computeTopSchools(snapshot, SCHOOL_KEYS, 8);
  assert.deepEqual(result, ['鴎台', '梟谷']);
});

test('計數筆數剛好等於上限時全部回傳，不會出現重複', () => {
  const snapshot = {};
  SCHOOL_KEYS.forEach((school, index) => {
    snapshot[school] = index + 1;
  });
  const result = computeTopSchools(snapshot, SCHOOL_KEYS, SCHOOL_KEYS.length);
  assert.equal(result.length, SCHOOL_KEYS.length);
  assert.equal(new Set(result).size, SCHOOL_KEYS.length);
});

test('上限小於資料筆數時只截取前N筆', () => {
  const snapshot = { '烏野': 1, '音駒': 2, '稲荷崎': 3 };
  const result = computeTopSchools(snapshot, SCHOOL_KEYS, 2);
  assert.deepEqual(result, ['稲荷崎', '音駒']);
});

test('涵蓋 ユース/疑似ユース 計數情境，兩者各自獨立排序', () => {
  const snapshot = { 'ユース': 5, '疑似ユース': 3, '烏野': 1 };
  const result = computeTopSchools(snapshot, SCHOOL_KEYS, 8);
  assert.deepEqual(result, ['ユース', '疑似ユース', '烏野']);
});

// ── addView / buildIncrementPayload / onFlushSuccess / onFlushFailure / applySnapshot ──

function initialState() {
  return { pendingDelta: {}, lastSyncedSnapshot: {} };
}

test('addView：單一學校標籤卡片對應學校 +1', () => {
  const singleSchoolCard = CARD_FIXTURES.find(c => c.card_no === 'HV-FIX-001'); // 烏野
  const next = addView(initialState(), singleSchoolCard);
  assert.deepEqual(next.pendingDelta, { '烏野': 1 });
});

test('addView：雙掛學校標籤卡片兩校各自 +1', () => {
  const dualSchoolCard = CARD_FIXTURES.find(c => c.card_no === 'HV-FIX-002'); // 烏野+音駒
  const next = addView(initialState(), dualSchoolCard);
  assert.deepEqual(next.pendingDelta, { '烏野': 1, '音駒': 1 });
});

test('addView：忽略白名單外的學校 key，不寫入 pendingDelta', () => {
  const bogusCard = { school_tags: ['不存在的學校'] };
  const next = addView(initialState(), bogusCard);
  assert.deepEqual(next.pendingDelta, {});
});

test('addView：同一張卡連續呼叫多次，pendingDelta 持續累加（不是防重複）', () => {
  const card = CARD_FIXTURES.find(c => c.card_no === 'HV-FIX-001'); // 烏野
  let state = initialState();
  state = addView(state, card);
  state = addView(state, card);
  state = addView(state, card);
  assert.deepEqual(state.pendingDelta, { '烏野': 3 });
});

test('addView：不會修改傳入的 state（回傳新物件）', () => {
  const card = CARD_FIXTURES.find(c => c.card_no === 'HV-FIX-001'); // 烏野
  const before = initialState();
  const next = addView(before, card);
  assert.deepEqual(before.pendingDelta, {});
  assert.notEqual(next, before);
});

test('buildIncrementPayload：pendingDelta 為空時回傳 null（不需要同步）', () => {
  assert.equal(buildIncrementPayload(initialState()), null);
});

test('buildIncrementPayload：有累積值時回傳正確格式的 increment payload', () => {
  const state = addView(initialState(), { school_tags: ['烏野', '音駒'] });
  assert.deepEqual(buildIncrementPayload(state), { '烏野': 1, '音駒': 1 });
});

test('onFlushSuccess：執行後 pendingDelta 被清空', () => {
  const state = addView(initialState(), { school_tags: ['烏野'] });
  const next = onFlushSuccess(state);
  assert.deepEqual(next.pendingDelta, {});
});

test('onFlushFailure：執行後 pendingDelta 維持不變', () => {
  const state = addView(initialState(), { school_tags: ['烏野'] });
  const next = onFlushFailure(state);
  assert.deepEqual(next.pendingDelta, state.pendingDelta);
});

test('applySnapshot：正確把遠端快照併入 lastSyncedSnapshot，且不影響既有 pendingDelta', () => {
  let state = addView(initialState(), { school_tags: ['烏野'] });
  state = applySnapshot(state, { '音駒': 50 });
  assert.deepEqual(state.lastSyncedSnapshot, { '音駒': 50 });
  assert.deepEqual(state.pendingDelta, { '烏野': 1 }); // 不受影響

  // 再次套用快照時是「併入」，不是整份覆蓋，既有的 lastSyncedSnapshot 保留
  state = applySnapshot(state, { '烏野': 10 });
  assert.deepEqual(state.lastSyncedSnapshot, { '音駒': 50, '烏野': 10 });
});

test('模擬多個獨立 state 各自累積、互不污染彼此的本地 state（多分頁情境）', () => {
  const card = CARD_FIXTURES.find(c => c.card_no === 'HV-FIX-001'); // 烏野
  const tabA = addView(initialState(), card);
  const tabB = addView(initialState(), card);
  const tabBAfterSync = onFlushSuccess(tabB);

  assert.deepEqual(tabA.pendingDelta, { '烏野': 1 }); // tabB 同步清空不影響 tabA
  assert.deepEqual(tabBAfterSync.pendingDelta, {});
});
