// Firestore emulator 範例測試：證明「emulator 啟動 → 寫入一筆資料 → 讀回驗證」
// 這條路徑是通的，作為之後撰寫規則測試/同步整合測試的範本。
//
// 這個檔案刻意不叫 *.test.js——它需要一個正在跑的本地 Firestore emulator
// （見根目錄 README 的「Firestore emulator 本地測試」段落），跟 `npm test`
// 預設會自動掃描、不需要任何額外環境就能跑的其他測試不是同一類，避免污染
// 預設 `npm test`。跑法：`npm run test:emulator`（需要在 emulator 環境內執行，
// 例如透過 `firebase emulators:exec` 包起來）。
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { initializeTestEnvironment, assertSucceeds } from '@firebase/rules-unit-testing';

let testEnv;

before(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: 'haikyuu-cards-emulator-smoke',
    firestore: {
      rules: readFileSync(new URL('../firestore.rules', import.meta.url), 'utf8'),
      host: '127.0.0.1',
      port: 8080,
    },
  });
});

after(async () => {
  await testEnv.cleanup();
});

test('emulator 寫入一筆資料後可以讀回同樣的內容', async () => {
  const db = testEnv.unauthenticatedContext().firestore();
  const ref = db.collection('smoke-test').doc('ping');

  await assertSucceeds(ref.set({ hello: 'world' }));

  const snap = await ref.get();
  assert.equal(snap.data().hello, 'world');
});
