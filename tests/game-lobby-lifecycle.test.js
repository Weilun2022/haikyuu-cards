'use strict';
// 大廳房間生命週期（issue #114）：真實瀏覽器頁面跑 game.html，Firebase 全部接到 Node 端 mock hub，沒有任何真實寫入。
// 涵蓋：雙方關頁後立即隱藏但保留資料、單方在線、重連重新顯示、觀戰者不算在線、
// 沒有 rooms 事件也由計時器清過期、未過期不清、過期判斷與續租的交易競爭、
// 清理中的墓碑擋住加入／續租／房號重用、晚到的清理回覆不能刪掉同房號的新房、清理中斷可由他人接手、
// 監聽重掛不殘留、手機背景暫離可恢復。
// 環境找不到 Playwright／Chromium 時整個檔案 skip（不算失敗）。
const test = require('node:test');
const assert = require('node:assert/strict');
const { createHarness } = require('./helpers/game-harness.js');

const T = { timeout: 120000 };
const MIN = 60 * 1000;
let h = null;
let hubReceive = null;

test.before(async () => { h = await createHarness(); if (h) hubReceive = h.hub.receive; });
test.after(async () => { if (h) await h.close(); });
test.beforeEach(() => { if (h) h.consoleErrors.length = 0; });
test.afterEach(async () => { if (h) { h.hub.receive = hubReceive; await h.closePlayers(); } });

function it(name, fn) {
  test(name, T, async t => {
    if (!h) { t.skip('找不到 Playwright／Chromium'); return; }
    await fn(t);
    assert.deepEqual(h.consoleErrors, [], '頁面不應出現未處理的錯誤');
  });
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, ms = 5000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { if (await fn()) return true; await sleep(40); }
  return false;
}
const listed = (p, room) => p.page.evaluate(id =>
  [...document.querySelectorAll('#room-list .room-code-tag')].filter(e => e.textContent.trim() === id).length, room);
const shiftClock = (p, ms) => p.run(`(() => { const n = window.__realNow = window.__realNow || Date.now.bind(Date); Date.now = () => n() + ${ms}; })()`);
const restoreClock = p => p.run('Date.now = window.__realNow || Date.now');
const listeners = (p, prefix) => p.rtdb((r, a) => r.listenerPaths().filter(x => x === a || x.startsWith(a + '/')), prefix);

// 把某個客戶端符合條件的訊息扣在傳輸層，之後 release() 才送達（模擬延遲的回覆／交易）
function intercept(pred) {
  const held = [];
  let on = true;
  h.hub.receive = (client, message) => {
    if (on && pred(client, message)) { held.push([client, message]); return; }
    return hubReceive.call(h.hub, client, message);
  };
  return {
    held,
    release() { on = false; held.splice(0).forEach(([c, m]) => hubReceive.call(h.hub, c, m)); },
    discard() { on = false; held.splice(0); },
  };
}

// createRoom 用 Math.random 產生 4 碼房號：依序指定想要的房號，用完恢復原本的亂數
const forceRoomIds = (p, ids) => p.page.evaluate(list => {
  const orig = Math.random;
  const queue = list.map(id => (Number(id) - 1000 + 0.5) / 9000);
  Math.random = () => (queue.length ? queue.shift() : orig());
}, ids);

async function createAs(p, deckId = 'dk_a') {
  await p.page.fill('#player-name', p.name);
  await p.page.selectOption('#deck-select', deckId);
  await p.page.click('button[onclick="createRoom()"]');
  await p.page.waitForFunction(() => document.getElementById('screen-waiting').classList.contains('active'));
  return (await p.page.textContent('#w-code')).trim();
}

async function closeTabs(...ps) {
  for (const p of ps) { h.hub.dropClient(p.clientId); await p.context.close(); }
}

// ── 1. 使用者回報的情境 ─────────────────────────────────────
it('雙方直接關閉分頁：資料保留但大廳立即隱藏；31 分鐘後沒有任何 rooms 事件也由計時器清除', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙'), lobby = await h.newPlayer('大廳');
  const room = await h.startMatch(host, guest);
  assert.ok(await until(async () => (await listed(lobby, room)) === 1), '雙方在線的對局照常列出');
  await closeTabs(host, guest);
  assert.ok(await until(async () => (await listed(lobby, room)) === 0), '雙方都關閉分頁後，大廳立即隱藏舊對戰');
  assert.ok(h.hub.get(`rooms/${room}`), '房間紀錄仍保留在 30 分鐘租約內供重連');
  assert.ok(h.hub.get(`games/${room}/ctl`));
  assert.equal(h.hub.get(`games/${room}/presence`), null);

  const n0 = h.hub.log.length;
  await shiftClock(lobby, 31 * MIN);
  await lobby.run('LOBBY_SWEEP_MS = 100; startLobbySweep(_lobby)');
  assert.ok(await until(() => !h.hub.get(`rooms/${room}`) && !h.hub.get(`games/${room}`)), '過期後由大廳計時器清除');
  const roomWriters = new Set(h.hub.log.slice(n0).filter(e => e.path.startsWith('rooms')).map(e => e.clientId));
  assert.deepEqual([...roomWriters], [lobby.clientId], '期間沒有其他房間事件，清理完全由計時器發起');
  assert.equal(await listed(lobby, room), 0);
});

it('只有一方離線仍列出；雙方離線隱藏；任一方重連後重新顯示，對局不受影響', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙'), lobby = await h.newPlayer('大廳');
  const room = await h.startMatch(host, guest);
  await guest.rtdb(r => r.setOnline(false));
  await until(() => !h.hub.get(`games/${room}/presence/guest`));
  await sleep(300);
  assert.equal(await listed(lobby, room), 1, '房主還在線就要列出');
  await host.rtdb(r => r.setOnline(false));
  assert.ok(await until(async () => (await listed(lobby, room)) === 0), '雙方都離線才隱藏');
  await guest.rtdb(r => r.setOnline(true));
  assert.ok(await until(async () => (await listed(lobby, room)) === 1), '對手重連後立即重新顯示（沒有任何 rooms 更新）');
  await host.rtdb(r => r.setOnline(true));
  await h.settle(host, guest, lobby);
  for (const p of [host, guest]) {
    assert.equal(await p.get('roomId'), room);
    assert.equal(await p.get('actionLocked()'), false);
  }
  assert.equal(await listed(lobby, room), 1, '沒有重複列');
});

it('觀戰者不算在線；未過期的雙離線房間定時掃描也不會被清', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙'), lobby = await h.newPlayer('大廳');
  const room = await h.startMatch(host, guest);
  const watcher = await h.newPlayer('觀戰');
  await watcher.run(`spectateRoom(${JSON.stringify(room)})`);
  await watcher.page.waitForFunction(() => document.getElementById('screen-game').classList.contains('active'));
  await closeTabs(host, guest);
  assert.ok(await until(async () => (await listed(lobby, room)) === 0), '只有觀戰者在看時仍視為雙方離線');
  assert.equal(h.hub.get(`games/${room}/presence`), null, '觀戰者不寫 presence');
  await shiftClock(lobby, 29 * MIN);
  await lobby.run('ROOM_ABANDON_MS = 1e12');   // 雙離線寬限另有 game-lobby-abandon.test.js；這裡只驗 30 分鐘租約
  await lobby.run('LOBBY_SWEEP_MS = 50; startLobbySweep(_lobby)');
  await sleep(700);
  assert.equal(h.hub.get(`rooms/${room}/status`), 'playing2', '租約未過期不能清');
  assert.ok(h.hub.get(`games/${room}/ctl`));
  assert.equal(await watcher.get('roomId'), room);
});

// ── 2. 清理與續租、房號重用的競態 ─────────────────────────────
it('大廳判定過期後、交易送達前房主剛好續租：伺服器重新驗證租約，房間不被刪除', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙'), lobby = await h.newPlayer('大廳');
  const room = await h.startMatch(host, guest);
  const ic = intercept((c, m) => c === lobby.clientId && m.t === 'tx' && m.path === `rooms/${room}`);
  h.hub.seed(`rooms/${room}/createdAt`, Date.now() - 31 * MIN);   // 大廳看到的快照已過期
  assert.ok(await until(() => ic.held.length > 0), '大廳依舊快照發出清理交易');
  await host.run('renewRoomLease()');
  assert.ok(await until(() => h.hub.get(`rooms/${room}/createdAt`) > Date.now() - MIN), '房主續租先落地');
  ic.release();
  await h.settle(host, guest, lobby);
  await sleep(300);
  assert.equal(h.hub.get(`rooms/${room}/status`), 'playing2', '清理交易必須以最新租約重新判斷而中止');
  assert.ok(h.hub.get(`games/${room}/ctl`));
  for (const p of [host, guest]) assert.equal(await p.get('roomId'), room);
  assert.equal(await listed(lobby, room), 1);
});

it('清理中的房號：不能加入、不能被新房重用；晚到的清理回覆也不能刪掉之後同房號的新房', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙');
  const reaperA = await h.newPlayer('大廳A'), reaperB = await h.newPlayer('大廳B'), newcomer = await h.newPlayer('新人');
  const room = await h.startMatch(host, guest);
  await closeTabs(host, guest);
  const oldInst = h.hub.get(`games/${room}/inst`);
  assert.ok(oldInst, '新建房間帶有房間實例 id');

  const ic = intercept((c, m) => c === reaperA.clientId && m.t === 'tx' && m.path === `games/${room}`);
  await shiftClock(reaperA, 31 * MIN);
  await reaperA.run('lobbySweep(_lobby)');
  assert.ok(await until(() => ic.held.length > 0), 'A 已寫下墓碑，刪除 games 的交易卡在路上');
  assert.equal(h.hub.get(`rooms/${room}/status`), 'reaping');
  assert.ok(h.hub.get(`games/${room}/ctl`));
  await restoreClock(reaperA);   // 只讓 A 判定這一間過期；之後同房號的新房不能因為 A 的時鐘被誤判

  await newcomer.page.fill('#player-name', newcomer.name);
  await newcomer.page.selectOption('#deck-select', 'dk_a');
  await newcomer.run(`joinRoom(${JSON.stringify(room)})`);
  assert.equal(await newcomer.get('roomId'), null, '清理中的房間不能加入');
  assert.equal(h.hub.get(`rooms/${room}/status`), 'reaping');

  const other = room === '9999' ? '9998' : '9999';
  await forceRoomIds(newcomer, [room, other]);
  const got = await createAs(newcomer);
  assert.equal(got, other, '建立房間時跳過清理中的房號');
  assert.equal(h.hub.get(`rooms/${room}/status`), 'reaping');
  await newcomer.run('leaveRoom()');
  await newcomer.waitFor('roomId === null');

  // B 接手完成清理（A 的回覆仍卡著），之後新人剛好拿到同一個房號
  await reaperB.run('ROOM_REAP_TAKEOVER_MS = 0; lobbySweep(_lobby)');
  assert.ok(await until(() => !h.hub.get(`rooms/${room}`) && !h.hub.get(`games/${room}`)), 'B 接手清除墓碑與資料');
  await forceRoomIds(newcomer, [room]);
  assert.equal(await createAs(newcomer), room);
  const newInst = h.hub.get(`games/${room}/inst`);
  assert.ok(newInst && newInst !== oldInst);

  ic.release();
  await h.settle(newcomer, reaperA);
  await sleep(300);
  assert.equal(h.hub.get(`rooms/${room}/status`), 'waiting2', '晚到的清理不能刪掉新房紀錄');
  assert.equal(h.hub.get(`games/${room}/inst`), newInst, '晚到的清理不能刪掉新房資料');
  assert.ok(h.hub.get(`games/${room}/ctl`));
  assert.equal(await newcomer.get('roomId'), room);
  assert.ok(await newcomer.page.evaluate(() => document.getElementById('screen-waiting').classList.contains('active')));
});

it('清理到一半的大廳關閉：墓碑由其他大廳接手完成；墓碑期間的續租不能讓房間復活', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙');
  const reaperA = await h.newPlayer('大廳A'), reaperB = await h.newPlayer('大廳B');
  const room = await h.startMatch(host, guest);
  await guest.rtdb(r => r.setOnline(false));
  await host.rtdb(r => r.setOnline(false));
  const ic = intercept((c, m) => c === reaperA.clientId && m.t === 'tx' && m.path === `games/${room}`);
  await shiftClock(reaperA, 31 * MIN);
  await reaperA.run('lobbySweep(_lobby)');
  assert.ok(await until(() => ic.held.length > 0));
  ic.discard();
  await closeTabs(reaperA);

  // 房主回來：續租遇到墓碑要中止，不能把 status 改回可加入／可續租的狀態
  await host.rtdb(r => r.setOnline(true));
  await host.run('renewRoomLease()');
  await sleep(300);
  assert.equal(h.hub.get(`rooms/${room}/status`), 'reaping', '墓碑期間不能續租');

  await reaperB.run('ROOM_REAP_TAKEOVER_MS = 0; lobbySweep(_lobby)');
  assert.ok(await until(() => !h.hub.get(`rooms/${room}`) && !h.hub.get(`games/${room}`)), '其他大廳接手完成清理');
  await host.page.waitForFunction(() => document.getElementById('screen-lobby').classList.contains('active'));
  assert.equal(await host.get('roomId'), null);
  assert.equal(await host.get('_leaseTimer'), null);
});

// ── 2b. 沒有 inst 的房間（修正前或舊版客戶端建立）──────────────────
it('沒有 inst 的舊版 proto 2 房：晚到的清理不能刪掉舊版客戶端用同房號新建（同樣沒有 inst）的新房', async () => {
  const a = await h.newPlayer('大廳A'), b = await h.newPlayer('大廳B');
  const id = '4114';
  h.hub.seed(`rooms/${id}`, { id, status: 'playing2', createdAt: Date.now(), proto: 2, hostName: '舊房' });
  h.hub.seed(`games/${id}`, { ctl: { proto: 2, activeMatch: 'old', started: true }, m: { old: { old: true } } });
  await h.settle(a, b);
  for (const p of [a, b]) await p.run('stopLobby(); _serverTimeOffset += 31 * 60000');
  const ic = intercept((c, m) => c === a.clientId && m.t === 'tx' && m.path === `games/${id}`);
  await a.run(`void reapRoom('${id}')`);
  assert.ok(await until(() => ic.held.length > 0), 'A 的 games 交易卡在路上');
  assert.equal(h.hub.get(`rooms/${id}/status`), 'reaping');
  assert.equal(h.hub.get(`rooms/${id}/witness`), 'old', '墓碑記下讀到的見證場');
  await b.run(`reapRoom('${id}')`);
  assert.equal(h.hub.get(`rooms/${id}`), null, 'B 沿用墓碑身分接手清完');
  assert.equal(h.hub.get(`games/${id}`), null);
  h.hub.seed(`rooms/${id}`, { id, status: 'waiting2', createdAt: Date.now(), proto: 2, hostName: '舊版新房' });
  h.hub.seed(`games/${id}`, { ctl: { proto: 2, activeMatch: 'new', started: false }, m: { new: { newRoom: true } } });
  ic.release();
  await h.settle(a, b);
  await sleep(300);
  assert.equal(h.hub.get(`games/${id}/m/new/newRoom`), true, '缺 inst 不能當成同一間：新房資料要保留');
  assert.equal(h.hub.get(`rooms/${id}/status`), 'waiting2');
});

it('讀見證的回覆晚到、讀到的已是同房號的新房：認領時房間紀錄與先前快照不同，不能把新房標成墓碑', async () => {
  const a = await h.newPlayer('大廳A'), b = await h.newPlayer('大廳B');
  const id = '4116';
  h.hub.seed(`rooms/${id}`, { id, status: 'playing2', createdAt: Date.now(), proto: 2, hostName: '舊房' });
  h.hub.seed(`games/${id}`, { ctl: { proto: 2, activeMatch: 'old', started: true }, m: { old: { old: true } } });
  await h.settle(a, b);
  for (const p of [a, b]) await p.run('stopLobby(); _serverTimeOffset += 31 * 60000');
  const ic = intercept((c, m) => c === a.clientId && m.t === 'get' && m.path === `games/${id}/ctl`);
  await a.run(`void reapRoom('${id}')`);
  assert.ok(await until(() => ic.held.length > 0), 'A 讀見證的請求卡在路上');
  await b.run(`reapRoom('${id}')`);
  assert.equal(h.hub.get(`games/${id}`), null);
  // 極端情況：A 卡得比 30 分鐘還久，新房在 A 眼中也已過期——仍然不能拿新房的見證認領
  h.hub.seed(`rooms/${id}`, { id, status: 'waiting2', createdAt: Date.now() - 1000, proto: 2, hostName: '舊版新房' });
  h.hub.seed(`games/${id}`, { ctl: { proto: 2, activeMatch: 'new', started: false }, m: { new: { newRoom: true } } });
  ic.release();
  await h.settle(a, b);
  await sleep(300);
  assert.equal(h.hub.get(`rooms/${id}/status`), 'waiting2', '認領必須比對讀見證前的房間紀錄');
  assert.equal(h.hub.get(`games/${id}/m/new/newRoom`), true);
});

it('冷快取接手墓碑：games 交易第一次拿 null 執行也會向伺服器確認，身分相符才刪、不符保留', async () => {
  const a = await h.newPlayer('大廳A');
  await a.run('stopLobby()');
  const tomb = id => ({ id, status: 'reaping', createdAt: Date.now() - 31 * MIN, witness: 'w-' + id });
  h.hub.seed('rooms/4117', tomb('4117'));
  h.hub.seed('games/4117', { ctl: { proto: 2, activeMatch: 'x' }, m: { 'w-4117': { a: 1 }, x: { b: 1 } } });
  h.hub.seed('rooms/4118', tomb('4118'));
  h.hub.seed('games/4118', { ctl: { proto: 2, activeMatch: 'other' }, m: { other: { c: 1 } } });
  await h.settle(a);
  for (const id of ['4117', '4118']) await a.run(`window.__rtdb.coldNextTransaction(); reapRoom('${id}')`);
  assert.equal(h.hub.get('games/4117'), null, '身分相符：冷快取下仍刪除');
  assert.equal(h.hub.get('rooms/4117'), null);
  assert.equal(h.hub.get('games/4118/m/other/c'), 1, '身分不符：保留別人的資料');
  assert.equal(h.hub.get('rooms/4118'), null, '墓碑本身照樣收尾');
});

it('舊根佈局房間沒有唯一見證：只移除過期的房間紀錄，不刪身分不明的 games', async () => {
  const a = await h.newPlayer('大廳A');
  const id = '4115';
  const n0 = h.hub.log.length;
  h.hub.seed(`games/${id}`, { started: false, players: { host: { name: '舊房主', ready: true } } });
  h.hub.seed(`rooms/${id}`, { id, status: 'waiting', createdAt: Date.now() - 31 * MIN, hostName: '舊房主' });
  assert.ok(await until(() => !h.hub.get(`rooms/${id}`)), '過期的舊版房間紀錄照樣清掉');
  await sleep(300);
  assert.equal(h.hub.get(`games/${id}/players/host/name`), '舊房主', '身分不明的 games 保守保留');
  const gamesWrites = h.hub.log.slice(n0).filter(e => e.clientId === a.clientId && e.path.startsWith(`games/${id}`));
  assert.deepEqual(gamesWrites, [], '沒有對 games 送出任何刪除');
});

it('沒有 inst 的舊版 proto 2 房跨重開：墓碑記下的見證在重開後仍在，晚到的刪除照樣清掉同一間', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙'), lobby = await h.newPlayer('大廳');
  const room = await h.startMatch(host, guest);
  h.hub.seed(`rooms/${room}/inst`, null);                       // 模擬修正前建立的房間
  h.hub.seed(`games/${room}/inst`, null);
  const m1 = h.hub.get(`games/${room}/ctl/activeMatch`);
  const ic = intercept((c, m) => c === lobby.clientId && m.t === 'tx' && m.path === `games/${room}`);
  h.hub.seed(`rooms/${room}/createdAt`, Date.now() - 31 * MIN);
  assert.ok(await until(() => ic.held.length > 0));
  assert.equal(h.hub.get(`rooms/${room}/witness`), m1);

  await host.run('openRematch()');
  await host.page.click('#rematch-main-btn');
  await guest.waitFor('_ctl && _ctl.phase === "inviting"');
  await guest.page.click('#rematch-main-btn');
  await host.waitFor(`_ctl.activeMatch !== ${JSON.stringify(m1)}`, 15000);
  for (const p of [host, guest]) await p.waitFor('!actionLocked()', 15000);
  assert.notEqual(h.hub.get(`games/${room}/ctl/activeMatch`), m1, '已換到新的一場');
  assert.ok(h.hub.get(`games/${room}/m/${m1}`), '見證的舊場節點重開後仍在');
  assert.equal(h.hub.get(`rooms/${room}/status`), 'reaping', '重開時的續租不能改掉墓碑');

  ic.release();
  assert.ok(await until(() => !h.hub.get(`rooms/${room}`) && !h.hub.get(`games/${room}`)), '同一間房照樣清除');
  for (const p of [host, guest]) await p.page.waitForFunction(() => document.getElementById('screen-lobby').classList.contains('active'));
});

// ── 3. 監聽生命週期 ─────────────────────────────────────────
it('重掛大廳監聽與頻繁切換畫面不累積監聽或計時器；房間消失時釋放 presence 監聽', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙'), lobby = await h.newPlayer('大廳');
  const room = await h.startMatch(host, guest);
  await until(async () => (await listed(lobby, room)) === 1);
  assert.deepEqual(await listeners(lobby, 'rooms'), ['rooms']);
  assert.equal((await listeners(lobby, `games/${room}/presence`)).length, 2);

  await lobby.run(`(() => {
    window.__iv = new Set();
    const si = window.setInterval, ci = window.clearInterval;
    window.setInterval = (...a) => { const id = si(...a); window.__iv.add(id); return id; };
    window.clearInterval = id => { window.__iv.delete(id); return ci(id); };
    window.__oldLobby = _lobby;
  })()`);
  for (let i = 0; i < 3; i++) await lobby.run('listenRooms()');
  for (let i = 0; i < 20; i++) await lobby.run(`showScreen(${i % 2 ? "'lobby'" : "'config'"})`);
  await lobby.run("showScreen('lobby')");
  await h.settle(lobby);
  assert.deepEqual(await listeners(lobby, 'rooms'), ['rooms'], 'rooms 監聽只有一份');
  assert.equal((await listeners(lobby, `games/${room}/presence`)).length, 2, 'presence 監聽沒有重複');
  assert.equal(await lobby.get('window.__iv.size'), 1, '清理計時器只有一個');
  assert.equal(await lobby.get('window.__oldLobby !== _lobby && window.__oldLobby.watch.size === 0'), true, '舊的大廳狀態已釋放');
  assert.equal(await listed(lobby, room), 1, '沒有幽靈或重複列');

  h.hub.seed(`rooms/${room}`, null);
  h.hub.seed(`games/${room}`, null);
  assert.ok(await until(async () => (await listeners(lobby, `games/${room}`)).length === 0), '房間消失後釋放 presence 監聽');
  assert.equal(await listed(lobby, room), 0);
  for (const p of [host, guest]) await p.page.waitForFunction(() => document.getElementById('screen-lobby').classList.contains('active'));
});

it('手機切背景暫離（雙方都斷線，租約內）：大廳隱藏但不刪；回到前景後對局照常且重新列出', async () => {
  const host = await h.newPlayer('甲', { mobile: true }), guest = await h.newPlayer('乙', { mobile: true });
  const lobby = await h.newPlayer('大廳');
  const room = await h.startMatch(host, guest);
  for (const p of [host, guest]) await p.rtdb(r => r.setOnline(false));
  assert.ok(await until(async () => (await listed(lobby, room)) === 0));
  await lobby.run('ROOM_ABANDON_MS = 1e12');   // 這裡驗租約內不刪；雙離線超過寬限的收房見 game-lobby-abandon.test.js
  await shiftClock(lobby, 10 * MIN);
  await lobby.run('LOBBY_SWEEP_MS = 50; startLobbySweep(_lobby)');
  await lobby.page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await sleep(500);
  assert.equal(h.hub.get(`rooms/${room}/status`), 'playing2', '暫離不刪房');
  assert.ok(h.hub.get(`games/${room}/ctl`));
  const before = h.hub.get(`rooms/${room}/createdAt`);
  for (const p of [host, guest]) await p.rtdb(r => r.setOnline(true));
  await host.page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  assert.ok(await until(async () => (await listed(lobby, room)) === 1), '回到前景後重新列出');
  assert.ok(await until(() => h.hub.get(`rooms/${room}/createdAt`) >= before), '回來後照常續租');
  for (const p of [host, guest]) {
    assert.equal(await p.get('roomId'), room);
    assert.equal(await p.get('actionLocked()'), false);
    assert.ok(await p.page.evaluate(() => document.getElementById('screen-game').classList.contains('active')));
  }
});
