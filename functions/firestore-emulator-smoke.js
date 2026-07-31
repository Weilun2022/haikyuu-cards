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

// `firebase emulators:exec` 會注入 FIRESTORE_EMULATOR_HOST（例如
// "127.0.0.1:8080"），優先吃這個環境變數而不是寫死 port，避免跟
// firebase.json 的 emulators.firestore.port 設定值不同步時連錯。
const [emulatorHost, emulatorPort] = (
  process.env.FIRESTORE_EMULATOR_HOST || '127.0.0.1:8080'
).split(':');

before(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: 'haikyuu-cards-emulator-smoke',
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

test('emulator 寫入一筆資料後可以讀回同樣的內容', async () => {
  // 寫入路徑要落在 firestore.rules 實際允許的範圍內，才能反映真實環境的
  // 讀寫行為；學校熱門度計數不需要登入即可寫入，是最簡單的驗證路徑。
  const db = testEnv.unauthenticatedContext().firestore();
  const ref = db.collection('school-popularity').doc('counts');

  await assertSucceeds(ref.set({ '烏野': 1 }, { merge: true }));

  const snap = await ref.get();
  assert.equal(snap.data()['烏野'], 1);
});
