// Firestore 安全規則測試：管理者唯讀檢視（admin-decks.html）的 collectionGroup('decks') 規則。
// 重點：管理者能讀所有帳號的牌組，但「一般使用者」「未驗證 email」「別的 email」「未登入」
// 全部讀不到別人的；管理者也沒有寫入權限；原本「只能讀寫自己的」規則沒被放寬。
//
// 跟 school-popularity-rules.js 一樣需要正在跑的 emulator，不能被 `npm test` 掃到。
// 跑法：`firebase emulators:exec --only firestore "npm --prefix functions run test:admin-rules"`
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
const ADMIN_EMAIL = 'evilscheme2012@gmail.com';

const [emulatorHost, emulatorPort] = (
  process.env.FIRESTORE_EMULATOR_HOST || '127.0.0.1:8080'
).split(':');

before(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: 'haikyuu-cards-admin-rules-test',
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
  // 準備兩個帳號各一副牌組（繞過規則直接寫入）
  await testEnv.withSecurityRulesDisabled(async ctx => {
    const db = ctx.firestore();
    await db.doc('users/alice/decks/d1').set({ ownerUid: 'alice', deck: { name: '甲' } });
    await db.doc('users/bob/decks/d2').set({ ownerUid: 'bob', deck: { name: '乙' } });
  });
});

const groupQuery = ctx => ctx.firestore().collectionGroup('decks').get();

test('管理者（已驗證 email）可以用 collectionGroup 讀到所有帳號的牌組', async () => {
  const admin = testEnv.authenticatedContext('admin-uid', { email: ADMIN_EMAIL, email_verified: true });
  const snap = await assertSucceeds(groupQuery(admin));
  assert.equal(snap.size, 2);
});

test('管理者也能直接讀別人的單一牌組文件', async () => {
  const admin = testEnv.authenticatedContext('admin-uid', { email: ADMIN_EMAIL, email_verified: true });
  await assertSucceeds(admin.firestore().doc('users/alice/decks/d1').get());
});

test('管理者 email 未驗證時讀不到', async () => {
  const ctx = testEnv.authenticatedContext('x', { email: ADMIN_EMAIL, email_verified: false });
  await assertFails(groupQuery(ctx));
});

test('別的 email 的已登入使用者用 collectionGroup 讀不到', async () => {
  const ctx = testEnv.authenticatedContext('alice', { email: 'someone@example.com', email_verified: true });
  await assertFails(groupQuery(ctx));
});

test('未登入讀不到', async () => {
  await assertFails(groupQuery(testEnv.unauthenticatedContext()));
});

test('一般使用者仍然讀得到自己的牌組、讀不到別人的（原規則沒被放寬）', async () => {
  const alice = testEnv.authenticatedContext('alice', { email: 'alice@example.com', email_verified: true });
  await assertSucceeds(alice.firestore().doc('users/alice/decks/d1').get());
  await assertFails(alice.firestore().doc('users/bob/decks/d2').get());
});

test('管理者沒有別人牌組的寫入／刪除權限', async () => {
  const admin = testEnv.authenticatedContext('admin-uid', { email: ADMIN_EMAIL, email_verified: true });
  await assertFails(admin.firestore().doc('users/alice/decks/d1').set({ deck: { name: '被改' } }));
  await assertFails(admin.firestore().doc('users/alice/decks/d1').delete());
});
