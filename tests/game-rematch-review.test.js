'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { createHarness } = require('./helpers/game-harness.js');

async function setup(t) {
  const h = await createHarness();
  if (!h) { t.skip('需要 Playwright／Chromium'); return null; }
  t.after(() => h.close());
  const host = await h.newPlayer('審查甲');
  const guest = await h.newPlayer('審查乙');
  const room = await h.startMatch(host, guest);
  return { h, host, guest, room };
}

test('提交後保存新場失敗：維持鎖定、不 ack；儲存恢復後保留原牌序再完成', { timeout: 60000 }, async t => {
  const s = await setup(t);
  if (!s) return;
  const { h, host, guest, room } = s;
  const old = await guest.get('_appliedMatchId');
  await host.run('openRematch()');
  await host.page.click('#rematch-main-btn');
  await guest.waitFor('_ctl.phase === "inviting"');
  await guest.evaluate(old => {
    window.__reviewSetItem = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (key === 'hv_game_session' && JSON.parse(value).appliedMatchId !== old) {
        throw new Error('模擬套用新場時儲存空間不足');
      }
      return window.__reviewSetItem.call(this, key, value);
    };
  }, old);
  await guest.page.click('#rematch-main-btn');
  await host.waitFor('_ctl.activeMatch !== ' + JSON.stringify(old));
  await h.settle(host, guest);
  const ctl = h.hub.get(`games/${room}/ctl`);
  const saved = await guest.evaluate(() => JSON.parse(localStorage.getItem('hv_game_session')));
  const expectedPile = saved.pending.pile.slice();
  assert.equal(await guest.get('actionLocked()'), true);
  assert.equal(ctl.phase, 'applying');
  assert.notEqual(ctl.ack?.guest, ctl.activeMatch, '沒有持久保存就不能確認完成');
  assert.equal(saved.appliedMatchId, old);
  await guest.evaluate(() => { Storage.prototype.setItem = window.__reviewSetItem; });
  await guest.run('rematchReact()');
  await guest.waitFor('!actionLocked()', 15000);
  await host.waitFor('!actionLocked()', 15000);
  assert.deepEqual(await guest.get('L.pile'), expectedPile, '重試不能重新洗牌');
  assert.equal(await guest.evaluate(() => JSON.parse(localStorage.getItem('hv_game_session')).appliedMatchId), ctl.activeMatch);
  assert.deepEqual(h.consoleErrors, []);
});

test('雙方切去改牌組而暫時離線：新版與舊版大廳的清理都不應立即刪除新房間', { timeout: 60000 }, async t => {
  const s = await setup(t);
  if (!s) return;
  const { h, host, guest, room } = s;
  await h.newPlayer('大廳觀察者');
  for (const p of [host, guest]) await p.rtdb(r => r.setOnline(false));
  await new Promise(resolve => setTimeout(resolve, 100));
  h.hub.seed('rooms/trigger', { id: 'trigger', status: 'waiting', createdAt: Date.now(), hostName: '其他房間' });
  await new Promise(resolve => setTimeout(resolve, 300));
  assert.ok(h.hub.get(`rooms/${room}`), '新版大廳不得因兩端暫時離線立即刪房');
  assert.ok(h.hub.get(`games/${room}`));
  const r = h.hub.get(`rooms/${room}`);
  const presence = h.hub.get(`games/${room}/presence`) || {};
  // 已部署的舊大廳只對 playing 房檢查 presence；新版房必須避開這條既有清理路徑。
  if (r.status === 'playing' && !presence.host && !presence.guest) {
    h.hub.seed(`rooms/${room}`, null);
    h.hub.seed(`games/${room}`, null);
  }
  assert.ok(h.hub.get(`games/${room}`), '舊版大廳也不能立即刪除新版房間');
  for (const p of [host, guest]) await p.rtdb(r => r.setOnline(true));
  await h.settle(host, guest);
  for (const p of [host, guest]) {
    assert.equal(await p.get('roomId'), room);
    assert.equal(await p.get('actionLocked()'), false);
  }
  assert.deepEqual(h.consoleErrors, []);
});

test('舊房邀請 transaction 晚回覆：離房並開始另一房後不得污染新房控制狀態', { timeout: 60000 }, async t => {
  const s = await setup(t);
  if (!s) return;
  const { h, host, room } = s;
  const receive = h.hub.receive.bind(h.hub);
  const delayed = [];
  let holding = true;
  h.hub.receive = (client, message) => {
    if (holding && client === host.clientId && message.t === 'tx' && message.path === `games/${room}/ctl`) {
      delayed.push([client, message]);
      return;
    }
    return receive(client, message);
  };
  await host.run('openRematch()');
  await host.page.click('#rematch-main-btn');
  await host.waitFor('_rmBusy');
  for (let i = 0; i < 100 && !delayed.length; i++) await new Promise(resolve => setTimeout(resolve, 20));
  assert.ok(delayed.length, '確實將 transaction 扣在傳輸層');
  await host.run('leaveRoom()');
  await host.waitFor('roomId === null');
  const nextGuest = await h.newPlayer('另一房對手');
  const nextRoom = await h.startMatch(host, nextGuest);
  const nextMatch = await host.get('_appliedMatchId');
  holding = false;
  for (const [client, message] of delayed) receive(client, message);
  await h.settle(host, nextGuest);
  assert.equal(await host.get('roomId'), nextRoom);
  assert.equal(await host.get('_ctl.activeMatch'), nextMatch);
  assert.equal(await host.get('_appliedMatchId'), nextMatch);
  assert.equal(await host.get('actionLocked()'), false);
  assert.equal(await host.get('_rmUi.fatal'), false);
  assert.deepEqual(h.consoleErrors, []);
});

test('房間已清除後才送達的續租：不能重新建立缺少身分與狀態的幽靈房間', { timeout: 60000 }, async t => {
  const s = await setup(t);
  if (!s) return;
  const { h, host, room } = s;
  const receive = h.hub.receive.bind(h.hub);
  const delayed = [];
  let holding = true;
  h.hub.receive = (client, message) => {
    const leaseWrite = (message.t === 'w' && message.path === `rooms/${room}/createdAt`) ||
      (message.t === 'tx' && message.path === `rooms/${room}`);
    if (holding && client === host.clientId && leaseWrite) {
      delayed.push([client, message]);
      return;
    }
    return receive(client, message);
  };
  await host.run('renewRoomLease()');
  for (let i = 0; i < 100 && !delayed.length; i++) await new Promise(resolve => setTimeout(resolve, 20));
  assert.ok(delayed.length, '確實扣住房間續租寫入');
  h.hub.seed(`rooms/${room}`, null);
  h.hub.seed(`games/${room}`, null);
  await host.waitFor('roomId === null');
  holding = false;
  for (const [client, message] of delayed) receive(client, message);
  await new Promise(resolve => setTimeout(resolve, 300));
  assert.equal(h.hub.get(`rooms/${room}`), null, '晚到續租不得復活已清除的房間');
  assert.equal(h.hub.get(`games/${room}`), null);
  assert.deepEqual(h.consoleErrors, []);
});

test('離房後續租遇到交易衝突：重試不得再更新仍有對手在線的舊房間', { timeout: 60000 }, async t => {
  const s = await setup(t);
  if (!s) return;
  const { h, host, room } = s;
  const receive = h.hub.receive.bind(h.hub);
  const delayed = [];
  let holding = true;
  h.hub.receive = (client, message) => {
    if (holding && client === host.clientId && message.t === 'tx' && message.path === `rooms/${room}`) {
      delayed.push([client, message]);
      return;
    }
    return receive(client, message);
  };
  await host.run('renewRoomLease()');
  for (let i = 0; i < 100 && !delayed.length; i++) await new Promise(resolve => setTimeout(resolve, 20));
  assert.ok(delayed.length);
  await host.run('leaveRoom()');
  await host.waitFor('roomId === null');
  h.hub.seed(`rooms/${room}/createdAt`, Date.now() + 1000);
  const baseline = h.hub.log.length;
  holding = false;
  for (const [client, message] of delayed) receive(client, message);
  await new Promise(resolve => setTimeout(resolve, 300));
  const lateWrites = h.hub.log.slice(baseline).filter(entry => entry.clientId === host.clientId && entry.path === `rooms/${room}`);
  assert.deepEqual(lateWrites, [], '房間生命週期已失效，交易重試必須中止');
  assert.deepEqual(h.consoleErrors, []);
});
