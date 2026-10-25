'use strict';
// 測試用的 Firebase 模擬本身的行為測試：E2E 測試的結論只在這個模擬忠實時才有意義，
// 所以把 game.html 的同步邏輯依賴到的那幾個真實行為單獨釘住。
const test = require('node:test');
const assert = require('node:assert/strict');
const { createHub, connectDirect } = require('./helpers/mock-rtdb-hub.js');

const tick = (ms = 20) => new Promise(r => setTimeout(r, ms));

test('本機寫入先發預先回呼；伺服器駁回後回滾並再發一次事件', async () => {
  const hub = createHub();
  const a = connectDirect(hub, 'a');
  const seen = [];
  a.ref('x').on('value', s => seen.push(s.val()));
  await tick();
  hub.reject('a', /^x$/);
  const p = a.ref('x').set(1);
  assert.deepEqual(seen, [null, 1], '預先回呼');
  await assert.rejects(p, /PERMISSION_DENIED/);
  assert.deepEqual(seen, [null, 1, null], '駁回後回滾');
  assert.equal(hub.get('x'), null);
});

test('伺服器確認：先更新資料樹（事件），後完成回呼', async () => {
  const hub = createHub();
  const a = connectDirect(hub, 'a');
  const order = [];
  a.ref('x').on('value', s => order.push(['event', s.val()]));
  await tick();
  await a.ref('x').set(2).then(() => order.push(['done']));
  assert.deepEqual(order, [['event', null], ['event', 2], ['done']]);
});

test('預先回呼裡再發的寫入，排在觸發它的那一筆之後送出', async () => {
  const hub = createHub();
  const a = connectDirect(hub, 'a');
  a.ref('first').on('value', s => { if (s.val() === 1) a.ref('second').set(2); });
  await tick();
  await a.ref('first').set(1);
  await tick();
  assert.deepEqual(hub.log.map(e => e.path), ['first', 'second']);
});

test('transaction：被伺服器駁回就用真實值重跑；第一次可強制用 null（冷快取）', async () => {
  const hub = createHub();
  const a = connectDirect(hub, 'a');
  hub.seed('n', 5);
  await tick();
  const inputs = [];
  a.controls.coldNextTransaction();
  const r = await a.ref('n').transaction(cur => { inputs.push(cur); return (cur || 0) + 1; }, undefined, false);
  assert.deepEqual(inputs, [null, 5], '第一次拿到 null，被駁回後拿到真實值 5');
  assert.equal(r.committed, true);
  assert.equal(hub.get('n'), 6);
});

test('transaction：更新函式回傳 undefined 就中止，不寫入', async () => {
  const hub = createHub();
  const a = connectDirect(hub, 'a');
  hub.seed('n', 1);
  await tick();
  const r = await a.ref('n').transaction(() => undefined, undefined, false);
  assert.equal(r.committed, false);
  assert.equal(hub.get('n'), 1);
});

test('transaction：applyLocally=false 不發本機預先事件', async () => {
  const hub = createHub();
  const a = connectDirect(hub, 'a');
  const seen = [];
  a.ref('t').on('value', s => seen.push(s.val()));
  await tick();
  const p = a.ref('t').transaction(() => 9, undefined, false);
  assert.deepEqual(seen, [null], '提交前本機看不到');
  await p;
  await tick();
  assert.deepEqual(seen, [null, 9]);
});

test('兩個客戶端同時 transaction：只有一個贏，另一個在新值上中止', async () => {
  const hub = createHub();
  const a = connectDirect(hub, 'a');
  const b = connectDirect(hub, 'b');
  await tick();
  const claim = who => cur => (cur ? undefined : who);
  const [ra, rb] = await Promise.all([
    a.ref('lock').transaction(claim('a'), undefined, false),
    b.ref('lock').transaction(claim('b'), undefined, false),
  ]);
  assert.equal([ra, rb].filter(r => r.committed).length, 1);
  assert.ok(['a', 'b'].includes(hub.get('lock')));
});

test('離線：寫入留在佇列、重連時照順序重放；onDisconnect 由伺服器代為執行', async () => {
  const hub = createHub();
  const a = connectDirect(hub, 'a');
  const b = connectDirect(hub, 'b');
  const seenB = [];
  b.ref('presence').on('value', s => seenB.push(s.val()));
  await tick();
  await a.ref('presence/a').set(true);
  await a.ref('presence/a').onDisconnect().remove();
  a.controls.setOnline(false);
  await tick();
  assert.equal(hub.get('presence'), null, 'onDisconnect 執行了');
  const w1 = a.ref('q/1').set('one');
  const w2 = a.ref('q/2').set('two');
  await tick();
  assert.equal(hub.get('q'), null, '離線期間沒有送出');
  assert.deepEqual(a.controls.pendingWrites().map(w => w.path), ['q/1', 'q/2'], '本機視圖已經有，等待重放');
  a.controls.setOnline(true);
  await Promise.all([w1, w2]);
  assert.deepEqual(hub.log.filter(e => e.path.startsWith('q/')).map(e => e.path), ['q/1', 'q/2']);
});

test('hold：寫入被扣住直到 release，之後的寫入也排在後面', async () => {
  const hub = createHub();
  const a = connectDirect(hub, 'a');
  await tick();
  a.controls.hold(true);
  const p1 = a.ref('a').set(1);
  const p2 = a.ref('b').set(2);
  await tick();
  assert.equal(hub.log.length, 0);
  a.controls.release();
  await Promise.all([p1, p2]);
  assert.deepEqual(hub.log.map(e => e.path), ['a', 'b']);
});

test('最壞順序：delay 讓舊寫入晚到，後發的寫入先落地', async () => {
  const hub = createHub();
  const a = connectDirect(hub, 'a');
  await tick();
  hub.delay('a', /^old\//);
  const late = a.ref('old/x').set(1);
  await a.ref('new/y').set(2);
  assert.equal(hub.get('new/y'), 2);
  assert.equal(hub.get('old/x'), null);
  assert.equal(hub.delayedCount('a'), 1);
  hub.flushDelayed('a');
  await late;
  assert.equal(hub.get('old/x'), 1);
});

test('陣列讀回時有 null 空洞；空容器與 null 不存在', async () => {
  const hub = createHub();
  const a = connectDirect(hub, 'a');
  await tick();
  await a.ref('z').set({ block: [null, { img: 'x' }, null], empty: [], drop: [], n: null });
  assert.deepEqual(hub.get('z'), { block: [null, { img: 'x' }] });
});

test('multi-path update 與 ServerValue.TIMESTAMP', async () => {
  const hub = createHub({ now: () => 777 });
  const a = connectDirect(hub, 'a');
  await tick();
  await a.ref('r').update({ 'p/q': 1, 's': { '.sv': 'timestamp' } });
  assert.deepEqual(hub.get('r'), { p: { q: 1 }, s: 777 });
});
