'use strict';
// 新版（proto2）房間雙方都離線超過寬限（ROOM_ABANDON_MS，預設 1 分鐘）就自動收房。
// 先前 PR111/#114 只讓大廳隱藏、資料與「重新加入」橫幅留滿 30 分鐘；使用者關掉瀏覽器後回來仍看得到可加入的舊局。
// 真實瀏覽器頁面跑 game.html，Firebase 全部接到 Node 端 mock hub，沒有任何真實寫入。
// 環境找不到 Playwright／Chromium 時整個檔案 skip（不算失敗）。
const test = require('node:test');
const assert = require('node:assert/strict');
const { createHarness } = require('./helpers/game-harness.js');

const T = { timeout: 120000 };
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

async function closeTabs(...ps) {
  for (const p of ps) { h.hub.dropClient(p.clientId); await p.context.close(); }
}

it('預設寬限是 1 分鐘', async () => {
  const lobby = await h.newPlayer('大廳');
  assert.equal(await lobby.get('ROOM_ABANDON_MS'), 60 * 1000);
});

it('雙方關掉分頁、超過寬限：房間與對局資料一併清除，期間不動', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙'), lobby = await h.newPlayer('大廳');
  const room = await h.startMatch(host, guest);
  await lobby.run('ROOM_ABANDON_MS = 900');
  await closeTabs(host, guest);
  assert.ok(await until(async () => (await listed(lobby, room)) === 0), '雙方離線後大廳先隱藏');
  assert.ok(h.hub.get(`rooms/${room}`) && h.hub.get(`games/${room}/ctl`), '寬限內資料仍在');
  assert.ok(await until(() => !h.hub.get(`rooms/${room}`) && !h.hub.get(`games/${room}`), 6000), '超過寬限後整間清掉');
});

it('寬限內任一方回來：不收房，計時作廢；之後再雙離線重新計時', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙'), lobby = await h.newPlayer('大廳');
  const room = await h.startMatch(host, guest);
  await lobby.run('ROOM_ABANDON_MS = 1200');
  await host.rtdb(r => r.setOnline(false));
  await guest.rtdb(r => r.setOnline(false));
  assert.ok(await until(async () => (await listed(lobby, room)) === 0));
  await sleep(500);
  await guest.rtdb(r => r.setOnline(true));
  assert.ok(await until(async () => (await listed(lobby, room)) === 1), '回來後重新列出');
  await sleep(1600);   // 超過第一次的寬限
  assert.ok(h.hub.get(`rooms/${room}`) && h.hub.get(`games/${room}/ctl`), '舊計時不能在對方已回來後收房');
  await guest.rtdb(r => r.setOnline(false));
  await sleep(500);
  assert.ok(h.hub.get(`rooms/${room}`), '再次離線要重新計滿寬限，不沿用舊計時');
});

it('只有一方離線很久：不收房', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙'), lobby = await h.newPlayer('大廳');
  const room = await h.startMatch(host, guest);
  await lobby.run('ROOM_ABANDON_MS = 300');
  await guest.rtdb(r => r.setOnline(false));
  await sleep(1500);
  assert.ok(h.hub.get(`rooms/${room}`) && h.hub.get(`games/${room}/ctl`));
  assert.equal(await listed(lobby, room), 1);
});

it('presence 還沒讀到（未知）不能當成離線收房', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙');
  const room = await h.startMatch(host, guest);
  const ic = intercept((c, m) => m.t === 'listen' && /presence\/(host|guest)$/.test(m.path || ''));
  const lobby = await h.newPlayer('大廳');
  await lobby.run('ROOM_ABANDON_MS = 200');
  await sleep(900);
  ic.discard();
  assert.ok(h.hub.get(`rooms/${room}`) && h.hub.get(`games/${room}/ctl`), '缺資料不推斷離線');
});

it('判定當下對手剛好回來：清理交易在伺服器重新驗證 presence，對局不被刪', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙'), lobby = await h.newPlayer('大廳');
  const room = await h.startMatch(host, guest);
  const ic = intercept((c, m) => c === lobby.clientId && m.t === 'tx' && m.path === `games/${room}`);
  await lobby.run('ROOM_ABANDON_MS = 300');
  await host.rtdb(r => r.setOnline(false));
  await guest.rtdb(r => r.setOnline(false));
  assert.ok(await until(() => ic.held.length > 0, 6000), '大廳依舊判斷發出清理交易');
  await guest.rtdb(r => r.setOnline(true));
  assert.ok(await until(() => h.hub.get(`games/${room}/presence/guest`)));
  ic.release();
  await sleep(700);
  assert.ok(h.hub.get(`games/${room}/ctl`), '對局資料還在');
  assert.ok(h.hub.get(`rooms/${room}`), '房間紀錄還在');
});

it('晚到的清理遇到同房號的新房：身分不符，新房完好', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙'), lobby = await h.newPlayer('大廳');
  const room = await h.startMatch(host, guest);
  const ic = intercept((c, m) => c === lobby.clientId && m.t === 'tx' && m.path === `games/${room}`);
  await lobby.run('ROOM_ABANDON_MS = 300');
  await closeTabs(host, guest);
  assert.ok(await until(() => ic.held.length > 0, 6000));
  // 房號被新房重用：身分（inst）與內容都不同，且有人在線
  h.hub.seed(`rooms/${room}/inst`, 'new-inst');
  h.hub.seed(`games/${room}/inst`, 'new-inst');
  h.hub.seed(`games/${room}/presence/host`, true);
  ic.release();
  await sleep(700);
  assert.equal(h.hub.get(`games/${room}/inst`), 'new-inst', '新房對局資料不能被舊清理刪掉');
  assert.equal(h.hub.get(`rooms/${room}/inst`), 'new-inst', '新房紀錄也不能被刪');
});

it('收房後「重新加入」橫幅消失，本機存檔一併清掉', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙'), lobby = await h.newPlayer('大廳');
  const room = await h.startMatch(host, guest);
  await lobby.run('ROOM_ABANDON_MS = 600');
  await lobby.run(`localStorage.setItem(SESSION_KEY, JSON.stringify({ roomId: ${JSON.stringify(room)}, role: 'host', savedAt: Date.now() })); checkRejoinSession()`);
  assert.ok(await until(() => lobby.page.evaluate(() => document.getElementById('rejoin-banner').style.display !== 'none')), '橫幅先出現');
  await closeTabs(host, guest);
  assert.ok(await until(() => !h.hub.get(`rooms/${room}`), 6000), '房間被收掉');
  assert.ok(await until(() => lobby.page.evaluate(() => document.getElementById('rejoin-banner').style.display === 'none')), '橫幅消失');
  assert.equal(await lobby.page.evaluate(() => localStorage.getItem('hv_game_session')), null);
});

it('自己所在的房間不被自己收掉', async () => {
  const host = await h.newPlayer('甲'), guest = await h.newPlayer('乙');
  const room = await h.startMatch(host, guest);
  await host.run('ROOM_ABANDON_MS = 200');
  await guest.rtdb(r => r.setOnline(false));
  await sleep(1200);
  assert.ok(h.hub.get(`rooms/${room}`) && h.hub.get(`games/${room}/ctl`));
  assert.equal(await host.get('roomId'), room);
});
