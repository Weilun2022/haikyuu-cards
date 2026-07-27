const { test } = require('node:test');
const assert = require('node:assert/strict');
const { mergeVideos } = require('./fetch_promo.js');

// 重現回歸情境：頻道最新 15 部裡混入大量非排球少年內容，把舊的相關影片擠出抓取視窗。
// 修法前：每次都整批覆寫，被擠出視窗的影片就從 promo_data.js 永久消失。
// 修法後：merge 用 videoId 去重，只要曾經被判定相關就留著，直到超過 MAX_STORED（300）才淘汰最舊的。
test('曾經抓到的相關影片，即使這次沒有再出現在抓取結果，也不會消失', () => {
  const existing = [
    { videoId: 'old1', title: '舊的排球少年影片1', published: '2026-07-09T09:27:04Z', schools: ['綜合'], school: '綜合', stage: '', channel: '執貳' },
    { videoId: 'old2', title: '舊的排球少年影片2', published: '2026-07-20T12:42:15Z', schools: ['綜合'], school: '綜合', stage: '', channel: '執貳' },
  ];
  // 這次抓到的最新 15 部裡，只剩 1 部相關（其餘都被日常 vlog 擠掉了）
  const fresh = [
    { videoId: 'new1', title: '最新排球少年影片', published: '2026-07-27T16:47:06Z', schools: ['綜合'], school: '綜合', stage: '', channel: '執貳' },
  ];

  const merged = mergeVideos(existing, fresh);

  assert.equal(merged.length, 3);
  assert.deepEqual(merged.map(v => v.videoId), ['new1', 'old2', 'old1']); // 依 published 新到舊排序
});

test('同一支影片重新抓到時，用新資料覆蓋舊分類（例如關鍵字規則更新後重新分類）', () => {
  const existing = [
    { videoId: 'v1', title: '對戰影片', published: '2026-07-20T00:00:00Z', schools: ['綜合'], school: '綜合', stage: '', channel: '執貳' },
  ];
  const fresh = [
    { videoId: 'v1', title: '對戰影片', published: '2026-07-20T00:00:00Z', schools: ['烏野'], school: '烏野', stage: '八強賽', channel: '執貳' },
  ];

  const merged = mergeVideos(existing, fresh);

  assert.equal(merged.length, 1);
  assert.equal(merged[0].school, '烏野');
  assert.equal(merged[0].stage, '八強賽');
});

test('累積數量超過上限（300）時，淘汰最舊的，不是任意丟棄', () => {
  const existing = Array.from({ length: 300 }, (_, i) => ({
    videoId: `old${i}`,
    title: `影片${i}`,
    published: `2026-01-${String((i % 28) + 1).padStart(2, '0')}T00:00:00Z`,
    schools: ['綜合'], school: '綜合', stage: '', channel: '執貳',
  }));
  const fresh = [
    { videoId: 'brandnew', title: '最新影片', published: '2026-07-28T00:00:00Z', schools: ['綜合'], school: '綜合', stage: '', channel: '執貳' },
  ];

  const merged = mergeVideos(existing, fresh);

  assert.equal(merged.length, 300);
  assert.ok(merged.some(v => v.videoId === 'brandnew'));
});
