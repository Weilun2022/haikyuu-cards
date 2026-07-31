import { test } from 'node:test';
import assert from 'node:assert/strict';
import { computeTopSchools } from './school-popularity.js';
import { SCHOOL_KEYS } from './school-constants.js';

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
