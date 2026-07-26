import { test, before, after, mock } from 'node:test';
import assert from 'node:assert/strict';
import { findCandidates } from './cardLookup.js';

// 假卡片資料庫，格式跟真實 cards_data.js 一樣（`const CARDS_DATA = {...};` 這種文字
// 格式，loadCards() 實際在解析的格式）。loadCards() 會把載入結果快取在模組層級變數
// 裡，整個測試檔案理論上只有第一次呼叫 findCandidates() 才會真的用到這份 mock 資料，
// 所以這裡一次準備好涵蓋全部測試案例的假資料，不用每個測試案例各自換一份 mock。
//
// - 田中 究：完全比對
// - 渡辺 親治：模擬 OCR 漏字（跟 cardLookup.js 原本註解舉的「渡 親治」對「渡辺 親治」
//   是同一個例子），測編輯距離退而求其次比對
// - 及川 徹：同一個角色有 3 個版本，測多版本回傳跟 maxCandidates 截斷
const FIXTURE_CARDS = [
  { image_file: 'HV-TEST-001.webp', card_no: 'HV-TEST-001', name: '田中 究' },
  { image_file: 'HV-TEST-002.webp', card_no: 'HV-TEST-002', name: '渡辺 親治' },
  { image_file: 'HV-TEST-003A.webp', card_no: 'HV-TEST-003A', name: '及川 徹' },
  { image_file: 'HV-TEST-003B.webp', card_no: 'HV-TEST-003B', name: '及川 徹' },
  { image_file: 'HV-TEST-003C.webp', card_no: 'HV-TEST-003C', name: '及川 徹' },
];

before(() => {
  mock.method(globalThis, 'fetch', async () => ({
    ok: true,
    status: 200,
    text: async () => `const CARDS_DATA = ${JSON.stringify({ cards: FIXTURE_CARDS })};`,
  }));
});

after(() => {
  mock.restoreAll();
});

test('完全比對：名字完全相符時回傳對應卡片', async () => {
  const result = await findCandidates('田中 究');
  assert.equal(result.length, 1);
  assert.equal(result[0].image_file, 'HV-TEST-001.webp');
});

test('模糊比對：OCR 漏字時靠編輯距離找到最相近的名字', async () => {
  const result = await findCandidates('渡 親治'); // 漏了「辺」字
  assert.equal(result.length, 1);
  assert.equal(result[0].image_file, 'HV-TEST-002.webp');
});

test('完全比對不到：回傳空陣列，不硬猜一個錯的', async () => {
  const result = await findCandidates('完全不相關的亂碼名字ＸＹＺ');
  assert.deepEqual(result, []);
});

test('多版本：同一個角色有多個版本時全部回傳', async () => {
  const result = await findCandidates('及川 徹');
  assert.equal(result.length, 3);
  const files = result.map(c => c.image_file).sort();
  assert.deepEqual(files, ['HV-TEST-003A.webp', 'HV-TEST-003B.webp', 'HV-TEST-003C.webp']);
});

test('maxCandidates 上限：符合的版本數量超過上限時會被截斷', async () => {
  const result = await findCandidates('及川 徹', 2);
  assert.equal(result.length, 2);
});
