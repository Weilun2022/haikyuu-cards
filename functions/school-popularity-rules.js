// Firestore 安全規則測試：學校瀏覽計數的白名單/increment上限防護，以及
// 確認牌組同步既有的 /users/{uid}/... 規則沒有被這次修改影響。
//
// 這個檔案刻意不叫 *.test.js——原因跟 firestore-emulator-smoke.js 一樣，
// 需要一個正在跑的本地 Firestore emulator，不能被 `npm test` 預設掃描到。
// 跑法：`npm run test:rules`（需要在 emulator 環境內執行，例如透過
// `firebase emulators:exec` 包起來）。
import { test, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  initializeTestEnvironment,
  assertSucceeds,
  assertFails,
} from '@firebase/rules-unit-testing';
import firebase from 'firebase/compat/app';
import 'firebase/compat/firestore';

let testEnv;

const [emulatorHost, emulatorPort] = (
  process.env.FIRESTORE_EMULATOR_HOST || '127.0.0.1:8080'
).split(':');

before(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: 'haikyuu-cards-rules-test',
    firestore: {
      rules: readFileSync(new URL('../firestore.rules', import.meta.url), 'utf8'),
      host: emulatorHost,
      port: Number(emulatorPort),
    },
  });
});

after(async () => {
  await testEnv?.cleanup();
});

beforeEach(async () => {
  await testEnv.clearFirestore();
});

// ── 學校瀏覽計數：白名單 + increment 上限 ────────────────────────────

test('合法寫入：白名單學校 key、上限內的 increment 成功', async () => {
  const db = testEnv.unauthenticatedContext().firestore();
  const ref = db.collection('school-popularity').doc('counts');
  await assertSucceeds(ref.set({ '烏野': 5 }, { merge: true }));
});

test('合法寫入：對已存在的文件做上限內的累加也成功', async () => {
  await testEnv.withSecurityRulesDisabled(async context => {
    await context.firestore().collection('school-popularity').doc('counts').set({ '烏野': 3 });
  });
  const db = testEnv.unauthenticatedContext().firestore();
  const ref = db.collection('school-popularity').doc('counts');
  await assertSucceeds(ref.set({ '烏野': 3 + 6 }, { merge: true })); // +6，未超過上限9
});

test('白名單外的學校 key 一律拒絕', async () => {
  const db = testEnv.unauthenticatedContext().firestore();
  const ref = db.collection('school-popularity').doc('counts');
  await assertFails(ref.set({ '不存在的學校': 1 }, { merge: true }));
});

test('單次 increment 超過上限時拒絕（新文件）', async () => {
  const db = testEnv.unauthenticatedContext().firestore();
  const ref = db.collection('school-popularity').doc('counts');
  await assertFails(ref.set({ '烏野': 20 }, { merge: true })); // 上限是個位數(9)
});

test('單次 increment 超過上限時拒絕（累加到既有值上）', async () => {
  await testEnv.withSecurityRulesDisabled(async context => {
    await context.firestore().collection('school-popularity').doc('counts').set({ '烏野': 3 });
  });
  const db = testEnv.unauthenticatedContext().firestore();
  const ref = db.collection('school-popularity').doc('counts');
  await assertFails(ref.set({ '烏野': 3 + 10 }, { merge: true })); // +10 超過上限
});

test('同一次寫入混合合法與非法 key 時，整筆拒絕', async () => {
  const db = testEnv.unauthenticatedContext().firestore();
  const ref = db.collection('school-popularity').doc('counts');
  await assertFails(ref.set({ '烏野': 1, '不存在的學校': 1 }, { merge: true }));
});

test('合法寫入：實際 client 用的 FieldValue.increment() transform 也成功（不只是普通 set）', async () => {
  await testEnv.withSecurityRulesDisabled(async context => {
    await context.firestore().collection('school-popularity').doc('counts').set({ '烏野': 3 });
  });
  const db = testEnv.unauthenticatedContext().firestore();
  const ref = db.collection('school-popularity').doc('counts');
  // js/school-popularity-firestore.js 實際送出的就是這種 FieldValue.increment
  // sentinel，不是算好結果的普通數字，這裡驗證規則對兩種寫法一視同仁。
  await assertSucceeds(ref.set({ '烏野': firebase.firestore.FieldValue.increment(5) }, { merge: true }));
  const snap = await ref.get();
  assert.equal(snap.data()['烏野'], 8);
});

test('超過上限：FieldValue.increment() transform 送出的超額增量一樣被拒絕', async () => {
  await testEnv.withSecurityRulesDisabled(async context => {
    await context.firestore().collection('school-popularity').doc('counts').set({ '烏野': 3 });
  });
  const db = testEnv.unauthenticatedContext().firestore();
  const ref = db.collection('school-popularity').doc('counts');
  await assertFails(ref.set({ '烏野': firebase.firestore.FieldValue.increment(10) }, { merge: true }));
});

test('不需要登入也能讀取熱門度快照', async () => {
  await testEnv.withSecurityRulesDisabled(async context => {
    await context.firestore().collection('school-popularity').doc('counts').set({ '烏野': 3 });
  });
  const db = testEnv.unauthenticatedContext().firestore();
  await assertSucceeds(db.collection('school-popularity').doc('counts').get());
});

// ── 既有牌組同步規則（/users/{uid}/...）不受本次修改影響 ──────────────

test('牌組同步：未登入寫入自己的路徑仍被拒絕', async () => {
  const db = testEnv.unauthenticatedContext().firestore();
  await assertFails(db.collection('users').doc('alice').collection('decks').doc('d1').set({ name: '測試牌組' }));
});

test('牌組同步：登入後寫入自己的路徑仍然成功', async () => {
  const db = testEnv.authenticatedContext('alice').firestore();
  await assertSucceeds(db.collection('users').doc('alice').collection('decks').doc('d1').set({ name: '測試牌組' }));
});

test('牌組同步：登入後寫入別人的路徑仍被拒絕', async () => {
  const db = testEnv.authenticatedContext('alice').firestore();
  await assertFails(db.collection('users').doc('bob').collection('decks').doc('d1').set({ name: '測試牌組' }));
});
