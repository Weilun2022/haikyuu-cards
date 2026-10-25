'use strict';
// 「再開一場／換牌組」端到端測試：兩個獨立的真實瀏覽器頁面跑真正的 game.html，
// Firebase 全部接到 Node 端的 mock hub（沒有任何真實寫入）。涵蓋：
//   完整流程、取消回原局、逾時、同時邀請、ready/ack 延遲、取消與提交的競態、預先回呼後被駁回、
//   舊寫入晚到只影響舊場、關頁重連（含缺 pending 的恢復）、localStorage 失敗、
//   舊版房間／觀戰者、40 張守恆、鎖定時的入口守衛、上一題輸一球補牌資格、presence 清理、手機版面。
// 環境找不到 Playwright／Chromium 時整個檔案 skip（不算失敗）。
const test = require('node:test');
const assert = require('node:assert/strict');
const { createHarness } = require('./helpers/game-harness.js');

const T = { timeout: 120000 };
let h = null;

test.before(async () => { h = await createHarness(); });
test.after(async () => { if (h) await h.close(); });
test.beforeEach(() => { if (h) h.consoleErrors.length = 0; });
test.afterEach(async () => { if (h) { await h.closePlayers(); } });

const ready = () => { if (!h) return false; return true; };
function it(name, fn) {
  test(name, T, async t => {
    if (!ready()) { t.skip('找不到 Playwright／Chromium'); return; }
    await fn(t);
    assert.deepEqual(h.consoleErrors, [], '頁面不應出現未處理的錯誤');
  });
}

// ── 共用工具 ────────────────────────────────────────────────
function deckSets() {
  const bad39 = { id: 'dk_39', name: '少一張', cards: h.makeDeck({ id: 'x', name: 'x', offset: 7 }).cards.slice(1) };
  const ev9 = h.makeDeck({ id: 'dk_ev9', name: '事件九張', offset: 2, events: 9 });
  const unknown = h.makeDeck({ id: 'dk_unk', name: '未知卡圖', offset: 9 });
  unknown.cards[0] = { image_file: 'not-in-database.webp', count: 1 };
  return {
    host: [h.makeDeck({ id: 'dk_a', name: '甲牌A' }), h.makeDeck({ id: 'dk_b', name: '甲牌B', offset: 3 })],
    guest: [h.makeDeck({ id: 'dk_a', name: '乙牌A', offset: 1 }), h.makeDeck({ id: 'dk_c', name: '乙牌C', offset: 5 }), bad39, ev9, unknown],
  };
}

async function setup(opts = {}) {
  const d = deckSets();
  const host = await h.newPlayer('甲', { decks: d.host, mobile: !!opts.hostMobile });
  const guest = await h.newPlayer('乙', { decks: d.guest, mobile: !!opts.guestMobile });
  const code = await h.startMatch(host, guest);
  const m1 = await host.get('_appliedMatchId');
  return { host, guest, code, m1, decks: d };
}

const ctlOf = code => h.hub.get(`games/${code}/ctl`);
const matchOf = (code, mid) => h.hub.get(`games/${code}/m/${mid}`);
const sessionOf = async p => JSON.parse(await p.page.evaluate(() => localStorage.getItem('hv_game_session')));
const toolButton = '#sb-actions [data-rematch-open]';

async function openModal(p) {
  await p.page.click(toolButton);
  await p.page.waitForSelector('#rematch-overlay.open');
}

async function pickAndSubmit(p, { source = 'snapshot', deckId } = {}) {
  await p.page.waitForSelector('#rematch-overlay.open');
  if (source === 'library') {
    await p.page.click('#rm-opt-library');
    await p.page.selectOption('#rematch-deck-select', deckId);
  } else {
    await p.page.click('#rm-opt-snapshot');
  }
  await p.page.click('#rematch-main-btn');
}

async function invite(p, opts) {
  await openModal(p);
  await pickAndSubmit(p, opts);
}

async function waitNewMatch(players, oldMid, timeout = 20000) {
  for (const p of players) {
    await p.waitFor(`_appliedMatchId !== ${JSON.stringify(oldMid)} && !actionLocked()`, timeout);
  }
}

const settle = (...ps) => h.settle(...ps);

async function snapshotOf(p) {
  return p.get('JSON.stringify({hand: L.hand, pile: L.pile, setPool: L.setPool, undo: L.undoStack.length, zones: gameState.players[myRole].zones, mid: _appliedMatchId})');
}

// ── 1. 完整流程 ──────────────────────────────────────────────
it('完整流程：發起方沿用本場牌組、對手改選牌組庫的牌組，雙方進新場', async () => {
  const { host, guest, code, m1 } = await setup();
  await host.run('drawCard(); drawCard(); drawCard()');
  await host.run("adjustSets('host', 1)");
  await settle(host, guest);
  assert.equal(matchOf(code, m1).setScore.host, 1);

  await host.page.click(toolButton);
  await host.page.waitForSelector('#rematch-overlay.open');
  assert.match(await host.page.textContent('#rm-snapshot-name'), /甲牌A/);
  await host.page.click('#rematch-main-btn');

  await guest.page.waitForSelector('#rematch-overlay.open');           // 對手端自動彈出
  assert.match(await guest.page.textContent('#rematch-status'), /邀請你再開一場/);
  assert.equal(await guest.get('actionLocked()'), true);
  assert.equal(await guest.page.evaluate(() => document.body.classList.contains('rm-locked')), true);
  await guest.page.click('#rm-opt-library');
  await guest.page.selectOption('#rematch-deck-select', 'dk_c');
  await guest.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], m1);
  await settle(host, guest);

  const ctl = ctlOf(code);
  assert.equal(ctl.phase, 'idle');
  assert.equal(ctl.epoch, 2);
  assert.notEqual(ctl.activeMatch, m1);
  assert.equal(ctl.req, undefined);
  const m2 = ctl.activeMatch;
  for (const p of [host, guest]) {
    assert.equal(await p.get('L.hand.length'), 0);
    assert.equal(await p.get('L.pile.length'), 40);
    assert.equal(await p.get('L.setPool.length'), 0);
    assert.equal(await p.get('L.undoStack.length'), 0);
    assert.equal(await p.get('_openingPhase'), true);
    assert.equal(await p.get('_postLossRedrawEligible'), false);
    assert.equal(await p.page.evaluate(() => document.body.classList.contains('rm-locked')), false);
    assert.equal(await p.page.evaluate(() => document.getElementById('rematch-overlay').classList.contains('open')), false);
  }
  const fresh = matchOf(code, m2);
  assert.deepEqual(fresh.setScore, { host: 0, guest: 0 });
  assert.equal(fresh.players.host.setCardsLeft, 0);
  assert.equal(fresh.players.guest.setCardsLeft, 0);
  assert.equal(fresh.turn, 'host');
  assert.deepEqual(Object.keys(fresh.log), ['!divider']);
  // 舊場原封不動地留著
  assert.equal(matchOf(code, m1).setScore.host, 1);
  assert.ok(Object.keys(matchOf(code, m1).log).length > 1);
  // 房號、身分、在線都還在；牌組名照既有行為公開
  assert.equal(h.hub.get(`rooms/${code}`).status, 'playing2');
  assert.deepEqual(h.hub.get(`games/${code}/presence`), { host: true, guest: true });
  assert.equal(h.hub.get(`games/${code}/players/guest/deckName`), '乙牌C');
  assert.equal(h.hub.get(`games/${code}/players/host/deckName`), '甲牌A');
  // 完整牌表與牌序不上傳
  const wire = JSON.stringify(h.hub.get(`games/${code}`));
  assert.ok(!/"(pile|pending|deckSnapshot|snapshot|cards)"\s*:/.test(wire), '牌庫、待套用牌庫、牌組快照不應出現在 Firebase');
  assert.ok(!/\.webp/.test(JSON.stringify(fresh)), '新場節點裡沒有任何卡圖');
  // 本機：session 帶著新場號與原始牌組快照，pending 已消耗
  const sess = await sessionOf(guest);
  assert.equal(sess.appliedMatchId, m2);
  assert.equal(sess.deckSnapshot.name, '乙牌C');
  assert.equal(sess.pending, undefined);
  // 40 張：牌庫就是所選牌組的卡
  const want = h.makeDeck({ id: 'x', name: 'x', offset: 5 }).cards.map(c => c.image_file).sort();
  assert.deepEqual((await guest.get('L.pile')).slice().sort(), want);
});

// ── 2. 取消／拒絕 ────────────────────────────────────────────
it('提交前取消：手牌、牌庫、場上、復原紀錄、場號全部不變，操作立刻恢復', async () => {
  const { host, guest, code, m1 } = await setup();
  await host.run("drawCard(); drawCard(); placeCard(0, 'attack')");
  await settle(host, guest);
  const before = await snapshotOf(host);
  const guestBefore = await snapshotOf(guest);

  await invite(host);
  await guest.page.waitForSelector('#rematch-overlay.open');
  await guest.page.click('#rematch-cancel-btn');                     // 對手拒絕
  for (const p of [host, guest]) await p.waitFor('!actionLocked()');
  await settle(host, guest);

  assert.equal(await snapshotOf(host), before);
  assert.equal(await snapshotOf(guest), guestBefore);
  const ctl = ctlOf(code);
  assert.equal(ctl.phase, 'idle');
  assert.equal(ctl.activeMatch, m1);
  assert.equal(ctl.req, undefined);
  for (const p of [host, guest]) {
    assert.equal((await sessionOf(p)).pending, undefined, 'pending 隨取消清掉');
    assert.equal(await p.page.evaluate(() => document.getElementById('rematch-overlay').classList.contains('open')), false);
  }
  await host.run('drawCard()');
  assert.equal(await host.get('L.hand.length'), 2, '取消後可以繼續操作（原本手上 1 張，再抽 1 張）');
});

it('邀請沒人理會會自動取消；發起方離線時對方仍能取消，重連後雙方回到原局', async () => {
  const { host, guest, code, m1 } = await setup();
  for (const p of [host, guest]) await p.run('RM_INVITE_TTL_MS = 500');
  await invite(host);
  for (const p of [host, guest]) await p.waitFor('!actionLocked()', 8000);
  assert.equal(ctlOf(code).phase, 'idle');

  await invite(host);
  await guest.page.waitForSelector('#rematch-overlay.open');
  await host.rtdb(r => r.setOnline(false));
  await guest.waitFor('gameState && gameState.presence && !gameState.presence.host');
  assert.match(await guest.page.textContent('#rematch-status'), /目前離線/);
  await guest.run('RM_INVITE_TTL_MS = 600000');
  await guest.page.click('#rematch-cancel-btn');
  await guest.waitFor('!actionLocked()');
  await host.rtdb(r => r.setOnline(true));
  await host.waitFor('!actionLocked()');
  await settle(host, guest);
  assert.equal(ctlOf(code).phase, 'idle');
  assert.equal(ctlOf(code).activeMatch, m1);
  assert.equal(h.hub.get(`games/${code}/presence/host`), true, '重連後 presence 自動恢復');
});

// ── 3. 同時邀請 ─────────────────────────────────────────────
it('雙方同時按邀請：只有一個成立，另一方變成回應者，仍能完成', async () => {
  const { host, guest, code, m1 } = await setup();
  await Promise.all([host.run('sendInvite()'), guest.run('sendInvite()')]);
  await settle(host, guest);
  const ctl = ctlOf(code);
  assert.equal(ctl.phase, 'inviting');
  const winner = ctl.req.by;
  const loser = winner === 'host' ? guest : host;
  const winnerP = winner === 'host' ? host : guest;
  assert.deepEqual(Object.keys(ctl.ready), [winner], '只有發起者 ready');
  assert.equal(await winnerP.get('_rmBusy'), false);
  assert.equal(await loser.get('_rmBusy'), false);
  await loser.page.waitForSelector('#rematch-overlay.open');
  assert.match(await loser.page.textContent('#rematch-status'), /邀請你再開一場/);
  assert.equal((await sessionOf(loser)).pending?.requestId ?? ctl.req.id, ctl.req.id, '輸的一方不留下自己那次的 pending');
  await loser.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], m1);
  assert.equal(ctlOf(code).epoch, 2);
});

// ── 4. ready／ack 延遲與同時提交 ───────────────────────────────
it('ack 延遲：兩端都套用了仍維持鎖定，雙 ack 到齊才解鎖；新場節點只建立一次', async () => {
  const { host, guest, code, m1 } = await setup();
  h.hub.delay(guest.clientId, /\/ctl\/ack\/guest$/);
  await invite(host);
  await pickAndSubmit(guest);
  await guest.waitFor(`_appliedMatchId !== ${JSON.stringify(m1)}`);
  await host.waitFor(`_appliedMatchId !== ${JSON.stringify(m1)}`);
  await settle(host, guest);
  assert.equal(ctlOf(code).phase, 'applying');
  assert.equal(await host.get('actionLocked()'), true);
  assert.equal(await guest.get('actionLocked()'), true);
  const m2 = ctlOf(code).activeMatch;
  // 先存 session 才 ack：ack 還沒到伺服器時，本機 session 已經是新場
  assert.equal((await sessionOf(guest)).appliedMatchId, m2);
  assert.match(await host.page.textContent('#rematch-status'), /等待中/);
  h.hub.flushDelayed(guest.clientId);
  await waitNewMatch([host, guest], m1);
  assert.equal(ctlOf(code).phase, 'idle');
  const commits = h.hub.log.filter(e => e.path === `games/${code}/ctl` && e.kind === 'tx' && e.value.phase === 'applying');
  const prepares = h.hub.log.filter(e => e.path === `games/${code}/m/${m2}` && e.kind === 'tx');
  assert.equal(commits.length, 1, '只提交一次');
  assert.equal(prepares.length, 1, '新場節點只建立一次');
  assert.equal(Object.keys(matchOf(code, m2).log).length, 1, '不會有重複的分隔線');
});

// ── 5. 取消 vs 提交 ──────────────────────────────────────────
it('取消後才到的舊 ready 不會污染下一次邀請，也不會觸發提交', async () => {
  const { host, guest, code, m1 } = await setup();
  h.hub.delay(guest.clientId, /\/ctl\/ready\/guest$/);
  await invite(host);
  await guest.page.waitForSelector('#rematch-overlay.open');
  await guest.page.click('#rematch-main-btn');                        // ready 寫入卡在路上
  await guest.waitFor('_rmBusy === true');
  await host.page.click('#rematch-cancel-btn');
  await host.waitFor('!actionLocked()');
  assert.equal(ctlOf(code).phase, 'idle');
  const oldRid = (await guest.get('_rmBusyRid'));
  h.hub.flushDelayed(guest.clientId);                                // 舊 ready 現在才落地
  await guest.waitFor('!_rmBusy');
  await settle(host, guest);
  assert.equal(ctlOf(code).phase, 'idle', '舊 ready 不能讓流程往前走');
  assert.equal(ctlOf(code).activeMatch, m1);
  assert.equal(ctlOf(code).ready.guest, oldRid, '舊 ready 確實落地了（作為殘留）');
  assert.equal((await sessionOf(guest)).pending, undefined);
  for (const p of [host, guest]) assert.equal(await p.get('actionLocked()'), false);

  await invite(host);                                                 // 下一次邀請照常完成
  assert.deepEqual(Object.keys(ctlOf(code).ready), ['host'], '新邀請清掉殘留的 ready');
  await pickAndSubmit(guest);
  await waitNewMatch([host, guest], m1);
});

it('提交先到：之後才到的取消會在伺服器上中止，不會把已開始的新場拆掉', async () => {
  const { host, guest, code, m1 } = await setup();
  h.hub.delay(guest.clientId, /\/ctl\/ack\/guest$/);                  // 讓 applying 階段停留
  await invite(host);
  await pickAndSubmit(guest);
  await host.waitFor(`_ctl && _ctl.phase === 'applying'`);
  const m2 = ctlOf(code).activeMatch;
  // 模擬「取消」是在看到提交之前按下的：本機快照還停在邀請中
  await host.run(`_ctl = Object.assign({}, _ctl, { phase: 'inviting', req: { id: ${JSON.stringify(m2)}, by: 'host' } }); cancelRematch()`);
  await host.waitFor('_rmUi.error.length > 0');
  assert.match(await host.get('_rmUi.error'), /已無法取消/);
  assert.equal(ctlOf(code).activeMatch, m2);
  assert.equal(ctlOf(code).phase, 'applying');
  h.hub.flushDelayed(guest.clientId);
  await waitNewMatch([host, guest], m1);
});

// ── 6. 預先回呼之後被駁回 ─────────────────────────────────────
it('ready 寫入被駁回：預先回呼不會導致提交，畫面回滾並提示，重試後成功', async () => {
  const { host, guest, code, m1 } = await setup();
  await invite(host);
  await guest.page.waitForSelector('#rematch-overlay.open');
  h.hub.reject(guest.clientId, /\/ctl\/ready\/guest$/);
  await guest.page.click('#rematch-main-btn');
  await guest.waitFor('_rmUi.error.length > 0');
  await settle(host, guest);
  assert.equal(ctlOf(code).phase, 'inviting', '伺服器沒收到 guest 的 ready，所以不能提交');
  assert.equal(ctlOf(code).ready.guest, undefined);
  assert.equal(await guest.get('_ctl.ready && _ctl.ready.guest'), undefined, '預先回呼的 ready 已回滾');
  assert.equal(await guest.page.evaluate(() => document.getElementById('rematch-main-btn').style.display !== 'none'), true, '還能再按一次');
  await guest.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], m1);
});

it('提交 transaction 被駁回一次：自動重試後仍能開新場', async () => {
  const { host, guest, code, m1 } = await setup();
  await invite(host);
  await guest.page.waitForSelector('#rematch-overlay.open');
  for (const p of [host, guest]) await p.run('RM_RETRY_MS = 300');
  for (const p of [host, guest]) h.hub.reject(p.clientId, new RegExp(`^games/${code}/ctl$`));
  await guest.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], m1, 30000);
  assert.equal(ctlOf(code).phase, 'idle');
});

it('準備新場節點時本機快取是冷的：被伺服器駁回後用真實值重跑，絕不覆寫已經存在的場', async () => {
  const { host, guest, code, m1 } = await setup();
  await invite(host);
  await guest.page.waitForSelector('#rematch-overlay.open');
  const rid = ctlOf(code).req.id;
  // 對方（或先到的提交者）已經把這一場準備好了，裡面還有一個標記
  h.hub.seed(`games/${code}/m/${rid}`, { turn: 'host', phase: 'serve', marker: 'keep-me', log: { '!divider': { player: 'system', action: 'orig', timestamp: 1 } } });
  await guest.rtdb(r => r.coldNextTransaction());                      // 準備用的 transaction 第一次拿到 null
  await guest.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], m1);
  const node = matchOf(code, rid);
  assert.equal(node.marker, 'keep-me');
  assert.equal(node.log['!divider'].action, 'orig');
});

// ── 7. 舊寫入晚到 ───────────────────────────────────────────
it('舊動作還沒落定就不能 ready；落定後它只影響舊場，新場不受任何影響', async () => {
  const { host, guest, code, m1 } = await setup();
  for (const p of [host, guest]) await p.run('RM_QUIESCE_MS = 600');
  await host.page.evaluate(() => { window.__oldCx = gx(); });
  await host.run('drawCard()');
  h.hub.delay(host.clientId, new RegExp(`/m/${m1}/players/host/zones$`));
  await host.page.evaluate(() => { placeCard(0, 'attack'); });        // 場上寫入卡在路上（不等它）
  await invite(guest);
  await host.page.waitForSelector('#rematch-overlay.open');
  await host.page.click('#rematch-main-btn');
  await host.waitFor('_rmUi.error.length > 0', 8000);
  assert.match(await host.get('_rmUi.error'), /還有操作正在送出/);
  assert.equal(ctlOf(code).ready.host, undefined, '操作沒落定前不宣稱準備好');
  assert.equal(ctlOf(code).phase, 'inviting');

  h.hub.flushDelayed(host.clientId);
  await host.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], m1);
  await settle(host, guest);
  const m2 = ctlOf(code).activeMatch;
  assert.ok(matchOf(code, m1).players.host.zones.attack, '晚到的寫入落在舊場');
  assert.equal(matchOf(code, m2).players.host.zones, undefined, '新場的場面是空的');

  // 已經交給 SDK、之後才到達的寫入（用原始 ref 模擬）：依舊只落在舊場路徑
  await host.page.evaluate(([c, m]) => db.ref(`games/${c}/m/${m}/players/host/zones/serve`).set({ img: 'late.webp', guts: [] }), [code, m1]);
  await settle(host, guest);
  assert.equal(matchOf(code, m1).players.host.zones.serve.img, 'late.webp');
  assert.equal(matchOf(code, m2).players.host.zones, undefined);
  assert.equal(await host.get('gameState.players.host.zones && gameState.players.host.zones.serve'), undefined);

  // 還沒送出的舊脈絡寫入：直接變成 no-op，不會到達 SDK
  const before = h.hub.log.length;
  const dropped = await host.page.evaluate(async () => {
    const stale = window.__oldCx;
    await stale.ref('players/host/zones').set({ attack: { img: 'stale.webp' } });
    await stale.ref('log').push({ player: 'x', action: 'stale' });
    return [stale.live(), stale.stats.dropped];
  });
  assert.equal(dropped[0], false);
  assert.ok(dropped[1] >= 2);
  assert.equal(h.hub.log.length, before, '死掉的脈絡不能讓任何寫入到達伺服器');
});

it('鎖定時，等待中的動作在續行時自我中止：擲骰動畫、確認框、150ms 去抖', async () => {
  const { host, guest, code, m1 } = await setup();
  const t0 = () => h.hub.log.length;

  // (a) 擲骰動畫跑到一半被邀請鎖住 → 動畫結束後不寫 diceRoll
  const a0 = t0();
  await host.page.evaluate(() => { pickDiceSide('單'); });
  await invite(guest);
  await host.waitFor('actionLocked()');
  await new Promise(r => setTimeout(r, 1500));
  assert.ok(!h.hub.log.slice(a0).some(e => e.path.includes('diceRoll')), '擲骰結果不能在鎖定後才寫出去');
  await host.page.click('#rematch-cancel-btn');
  await host.waitFor('!actionLocked()');
  await guest.waitFor('!actionLocked()');

  // (b) 確認框開著時被鎖住 → 確認框自動關閉，輸球不會發生
  await host.page.evaluate(() => { addToSetPool(); });
  await host.page.waitForSelector('#gen-confirm-overlay', { state: 'visible' });
  await host.page.click('#gen-confirm-ok-btn');
  await host.waitFor('L.setPool.length === 2');
  const b0 = t0();
  await host.page.evaluate(() => { loseRallySetPool(); });
  await host.page.waitForFunction(() => document.getElementById('gen-confirm-overlay').style.display === 'flex');
  await invite(guest);
  await host.waitFor('actionLocked()');
  await host.page.waitForFunction(() => document.getElementById('gen-confirm-overlay').style.display === 'none');
  await settle(host, guest);
  assert.ok(!h.hub.log.slice(b0).some(e => e.path.includes('rallyLoss')), '沒有輸球事件');
  assert.equal(await host.get('_rallyLossBusy'), false);
  assert.equal(await host.get('L.setPool.length'), 2);
  await host.page.click('#rematch-cancel-btn');
  await host.waitFor('!actionLocked()');
  await guest.waitFor('!actionLocked()');

  // (c) 去抖中的牌庫張數：鎖定時立刻寫給舊場，新場的張數是 40，不會被舊值蓋掉
  await host.run('drawCard()');
  const pileNow = await host.get('L.pile.length');
  await invite(guest);
  await host.waitFor('actionLocked()');
  await host.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], m1);
  await settle(host, guest);
  const m2 = ctlOf(code).activeMatch;
  assert.equal(matchOf(code, m1).players.host.pileCount, pileNow, '舊場拿到鎖定前最後的張數');
  assert.equal(matchOf(code, m2).players.host.pileCount, 40);
  const strayToNew = h.hub.log.filter(e => e.path === `games/${code}/m/${m2}/players/host/pileCount` && e.value !== 40);
  assert.deepEqual(strayToNew, []);
});

it('去抖計時被拉長到 3 秒：鎖定時仍會把排隊中的張數立刻寫給舊場，新場不受影響', async () => {
  const { host, guest, code, m1 } = await setup();
  // 只拉長 150ms 的那個去抖計時，其餘計時照舊——這樣唯一能讓舊場拿到最新張數的就是「進入鎖定時沖出去」
  await host.page.evaluate(() => {
    const real = window.setTimeout.bind(window);
    window.setTimeout = (fn, ms, ...a) => real(fn, ms === 150 ? 3000 : ms, ...a);
  });
  await host.page.evaluate(() => { drawCard(); drawCard(); });
  const pileNow = await host.get('L.pile.length');
  assert.equal(pileNow, 38);
  assert.equal(await host.get('hasPendingSyncs()'), true);
  await invite(guest);
  await host.page.waitForSelector('#rematch-overlay.open');
  await host.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], m1);
  await settle(guest);
  const m2 = ctlOf(code).activeMatch;
  assert.equal(matchOf(code, m1).players.host.pileCount, pileNow, '舊場拿到鎖定當下的張數');
  assert.equal(matchOf(code, m1).players.host.handCount, 2);
  assert.equal(await host.get('hasPendingSyncs()'), true, '（新場開局後這份新的去抖還在排隊，屬於新場）');
  assert.equal(matchOf(code, m2).players.guest.pileCount, 40);
});

// ── 8. 關頁重連 ─────────────────────────────────────────────
// pagehide 會把目前記憶體裡的進度存回 localStorage，所以要改 session 得等重新載入之後、按「重新加入」之前
async function reloadAndRejoin(p, tamper) {
  h.hub.dropClient(p.clientId);
  await p.page.reload();
  await p.page.waitForFunction(() => document.getElementById('screen-lobby').classList.contains('active'));
  await p.page.waitForSelector('#rejoin-banner', { state: 'visible' });
  if (tamper) await p.page.evaluate(tamper);
  await p.page.click('#rejoin-banner button.primary');
  await p.page.waitForFunction(() => document.getElementById('screen-game').classList.contains('active'));
}

it('提交後、ack 前關頁：重連用 session 裡的新場資料，牌序不變，補送 ack 後雙方解鎖', async () => {
  const { host, guest, code, m1 } = await setup();
  h.hub.delay(guest.clientId, /\/ctl\/ack\/guest$/);
  await invite(host);
  await pickAndSubmit(guest);
  await guest.waitFor(`_appliedMatchId !== ${JSON.stringify(m1)}`);
  await settle(host, guest);
  const m2 = ctlOf(code).activeMatch;
  const pileBefore = await guest.get('L.pile');
  assert.equal(pileBefore.length, 40);
  assert.equal(ctlOf(code).phase, 'applying');
  h.hub.discardDelayed(guest.clientId);                                // 這個 ack 永遠沒送到（當機）
  await reloadAndRejoin(guest);
  await waitNewMatch([host, guest], m1);
  assert.deepEqual(await guest.get('L.pile'), pileBefore, '已套用的場不會再洗第二次牌');
  assert.equal(await guest.get('_appliedMatchId'), m2);
  assert.equal(ctlOf(code).phase, 'idle');
});

it('提交後、套用前關頁：用 session 的 pending 套用，牌序就是準備時洗好的那份', async () => {
  const { host, guest, code, m1 } = await setup();
  await guest.page.evaluate(() => { window.applyPendingMatch = async () => {}; });   // 讓這一端永遠沒套用到
  await invite(host);
  await pickAndSubmit(guest, { source: 'library', deckId: 'dk_c' });
  await host.waitFor(`_ctl && _ctl.phase === 'applying'`);
  const sess = await sessionOf(guest);
  assert.equal(sess.pending.requestId, ctlOf(code).activeMatch);
  assert.equal(sess.appliedMatchId, m1);
  const pendingPile = sess.pending.pile.slice();
  assert.equal(pendingPile.length, 40);
  await reloadAndRejoin(guest);
  await waitNewMatch([host, guest], m1);
  assert.deepEqual(await guest.get('L.pile'), pendingPile);
  assert.equal(await guest.get('L.hand.length'), 0, '不會把上一場的手牌帶進新場');
  assert.equal((await sessionOf(guest)).pending, undefined);
  assert.equal((await sessionOf(guest)).deckSnapshot.name, '乙牌C');
});

it('缺 pending 快照：顯示恢復選牌流程，自己選牌後套用並 ack，不會永久鎖住', async () => {
  const { host, guest, code, m1 } = await setup();
  await guest.page.evaluate(() => { window.applyPendingMatch = async () => {}; });
  await invite(host);
  await pickAndSubmit(guest);
  await host.waitFor(`_ctl && _ctl.phase === 'applying'`);
  await reloadAndRejoin(guest, () => {           // 這台裝置沒有保存到 pending（例如儲存空間被清掉）
    const s = JSON.parse(localStorage.getItem('hv_game_session'));
    delete s.pending;
    localStorage.setItem('hv_game_session', JSON.stringify(s));
  });
  await guest.page.waitForSelector('#rematch-overlay.open');
  assert.match(await guest.page.textContent('#rematch-status'), /沒有保存你的牌組/);
  assert.equal(await host.get('actionLocked()'), true, '對方還沒 ack，房主維持鎖定');
  assert.equal(await guest.get('L.hand.length'), 0);
  await guest.page.click('#rm-opt-library');
  await guest.page.selectOption('#rematch-deck-select', 'dk_c');
  await guest.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], m1);
  assert.equal(await guest.get('L.pile.length'), 40);
  assert.equal(ctlOf(code).phase, 'idle');
});

it('重連時房間已進入新場、本機又沒有那場資料：拒絕還原舊手牌', async () => {
  const { host, guest, code, m1 } = await setup();
  await guest.run('drawCard(); drawCard()');
  await settle(host, guest);
  const sessBefore = await sessionOf(guest);
  assert.equal(sessBefore.hand.length, 2);
  // 使用者在另一個分頁／裝置上完成了重開，這個分頁的 session 還是舊的
  await invite(host);
  await pickAndSubmit(guest);
  await waitNewMatch([host, guest], m1);
  h.hub.dropClient(guest.clientId);
  await guest.page.reload();                                           // pagehide 會把目前（新場）的進度存起來
  await guest.page.waitForSelector('#rejoin-banner', { state: 'visible' });
  await guest.page.evaluate(s => localStorage.setItem('hv_game_session', JSON.stringify(s)), sessBefore);   // 換成「另一個分頁留下的舊 session」
  await guest.page.click('#rejoin-banner button.primary');
  await guest.page.waitForFunction(() => document.getElementById('screen-lobby').classList.contains('active'));
  assert.equal(await guest.page.evaluate(() => localStorage.getItem('hv_game_session')), null);
  assert.equal(await guest.get('L.hand.length'), 0, '沒有還原舊手牌');
});

// ── 9. localStorage 失敗 ─────────────────────────────────────
it('localStorage 寫入失敗：不送邀請、不 ready，並明確提示；恢復後可正常進行', async () => {
  const { host, guest, code, m1 } = await setup();
  const breakStorage = p => p.page.evaluate(() => { window.__realSet = Storage.prototype.setItem; Storage.prototype.setItem = function () { throw new Error('quota'); }; });
  const fixStorage = p => p.page.evaluate(() => { Storage.prototype.setItem = window.__realSet; });

  await breakStorage(host);
  await openModal(host);
  await host.page.click('#rematch-main-btn');
  await host.waitFor('_rmUi.error.length > 0');
  assert.match(await host.get('_rmUi.error'), /無法保存牌組/);
  assert.equal(ctlOf(code).phase, 'idle', '存不下 pending 就不發邀請');
  assert.equal(await host.get('actionLocked()'), false);
  await fixStorage(host);

  await host.page.click('#rematch-main-btn');
  await guest.page.waitForSelector('#rematch-overlay.open');
  await breakStorage(guest);
  await guest.page.click('#rematch-main-btn');
  await guest.waitFor('_rmUi.error.length > 0');
  assert.match(await guest.get('_rmUi.error'), /無法保存牌組/);
  assert.equal(ctlOf(code).ready.guest, undefined, '沒存好 pending 不能 ready');
  assert.equal(await guest.get('saveSession()'), false, 'saveSession 如實回報失敗');
  await fixStorage(guest);
  await guest.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], m1);
});

// ── 10. 舊版房間與 capability ────────────────────────────────
it('新版房間對舊版客戶端不可見也加不進去；新版客戶端的大廳看得到', async () => {
  const d = deckSets();
  const host = await h.newPlayer('甲', { decks: d.host });
  const lobby = await h.newPlayer('丙', { decks: d.guest });
  await host.page.fill('#player-name', '甲');
  await host.page.selectOption('#deck-select', 'dk_a');
  await host.page.click('button[onclick="createRoom()"]');
  await host.page.waitForFunction(() => document.getElementById('screen-waiting').classList.contains('active'));
  const code = (await host.page.textContent('#w-code')).trim();
  const room = h.hub.get(`rooms/${code}`);
  assert.equal(room.status, 'waiting2');
  assert.equal(room.proto, 2);
  assert.notEqual(room.status, 'waiting', '舊版 joinRoom 只認 waiting；舊版大廳只列 waiting／playing');
  await lobby.page.waitForSelector(`.room-code-tag:text("${code}")`);
  assert.equal(h.hub.get(`games/${code}/players/guest`), null);
  assert.equal(h.hub.get(`games/${code}/started`), null, '根層沒有舊版會讀的 started／zones，舊版觀戰者會被擋下');
});

it('舊版（根佈局）房間：照舊玩得下去，寫入走根路徑，再開一場只提示重建房間', async () => {
  const d = deckSets();
  const guest = await h.newPlayer('新', { decks: d.guest });
  const code = '1111';
  h.hub.seed(`rooms/${code}`, { id: code, status: 'waiting', hostName: '舊房主', hostAvatar: '🦅', deckName: 'X', createdAt: Date.now() });
  h.hub.seed(`games/${code}`, {
    started: false, turn: 'host', phase: 'serve', setScore: { host: 0, guest: 0 },
    players: { host: { name: '舊房主', avatar: '🦅', deckName: 'X', ready: true, setCardsLeft: 0, zones: { serve: null, block: [null, null, null], receive: null, toss: null, attack: null, event: [], drop: [], set: [] } } },
  });
  await guest.page.fill('#player-name', '新');
  await guest.page.selectOption('#deck-select', 'dk_a');
  await guest.page.fill('#join-code', code);
  await guest.page.click('button[onclick="joinByCode()"]');
  await guest.page.waitForFunction(() => document.getElementById('screen-waiting').classList.contains('active'));
  assert.equal(h.hub.get(`games/${code}/players/guest/setCardsLeft`), 5, '舊版房間維持舊版的初始資料');
  h.hub.seed(`games/${code}/presence/host`, true);
  h.hub.seed(`games/${code}/started`, true);
  await guest.page.waitForFunction(() => document.getElementById('screen-game').classList.contains('active'));
  assert.equal(await guest.get('_gctx.proto'), 1);
  assert.equal(await guest.get('actionLocked()'), false);
  const n0 = h.hub.log.length;
  await guest.run('drawCard()');
  await h.settle(guest);
  const writes = h.hub.log.slice(n0).map(e => e.path);
  assert.ok(writes.includes(`games/${code}/players/guest/pileCount`), '舊版房間寫根路徑');
  assert.ok(!writes.some(p => p.includes('/m/')));
  await guest.page.click(toolButton);
  assert.match(await guest.page.textContent('#toast'), /舊版建立的/);
  assert.equal(await guest.page.evaluate(() => document.getElementById('rematch-overlay').classList.contains('open')), false);
});

// ── 11. 觀戰者 ──────────────────────────────────────────────
it('觀戰者會跟著切到新場，而且全程不能操作、不寫入', async () => {
  const { host, guest, code, m1 } = await setup();
  const d = deckSets();
  const spec = await h.newPlayer('旁', { decks: d.guest });
  await spec.page.evaluate(c => spectateRoom(c), code);
  await spec.page.waitForFunction(() => document.getElementById('screen-game').classList.contains('active'));
  await spec.waitFor(`isSpectator && _gctx.matchId === ${JSON.stringify(m1)} && gameState && gameState.log`);
  await invite(host);
  await pickAndSubmit(guest);
  await waitNewMatch([host, guest], m1);
  const m2 = ctlOf(code).activeMatch;
  await spec.waitFor(`_gctx.matchId === ${JSON.stringify(m2)} && gameState && gameState.log && Object.keys(gameState.log).length === 1`);
  assert.equal(await spec.get('actionLocked()'), false, '觀戰者的鎖定不看 ctl，但所有入口都先擋觀戰');
  await spec.run('drawCard(); endTurn(); declareLost(); sendInvite(); openRematch()');
  await spec.page.waitForTimeout(300);
  assert.deepEqual(await spec.rtdb(r => r.writeLog()), [], '觀戰者從頭到尾沒有發出任何寫入');
  assert.equal(await spec.page.evaluate(() => document.getElementById('rematch-overlay').classList.contains('open')), false);
});

// ── 12. 40 張守恆與牌組驗證 ───────────────────────────────────
it('不合格的牌組（39 張、事件超過 8、卡圖不認得）不能選也送不出；合格的新場 40 張守恆', async () => {
  const { host, guest, code, m1 } = await setup();
  await invite(host);
  await guest.page.waitForSelector('#rematch-overlay.open');
  await guest.page.click('#rm-opt-library');
  const disabled = await guest.page.$$eval('#rematch-deck-select option:disabled', os => os.map(o => o.value).sort());
  assert.deepEqual(disabled, ['dk_39', 'dk_ev9', 'dk_unk']);
  for (const bad of ['dk_39', 'dk_ev9', 'dk_unk']) {
    await guest.run(`rematchPickDeck(${JSON.stringify(bad)})`);
    await guest.page.click('#rematch-main-btn');
    await guest.waitFor('_rmUi.error.length > 0');
    assert.match(await guest.get('_rmUi.error'), /不能使用/);
    assert.equal(ctlOf(code).ready.guest, undefined);
    assert.equal((await sessionOf(guest)).pending, undefined);
  }
  await guest.page.selectOption('#rematch-deck-select', 'dk_c');
  await guest.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], m1);

  await guest.run("for (let i = 0; i < 6; i++) drawCard(); placeCard(0, 'attack'); placeCard(0, 'toss'); discardFromHand(0)");
  await settle(host, guest);
  const total = await guest.get(`L.hand.length + L.pile.length + L.setPool.length + collectCardsFromZones(myZonesCopy()).length`);
  assert.equal(total, 40);
  const all = await guest.get('[...L.hand, ...L.pile, ...L.setPool, ...collectCardsFromZones(myZonesCopy())].sort()');
  assert.deepEqual(all, h.makeDeck({ id: 'x', name: 'x', offset: 5 }).cards.map(c => c.image_file).sort());
});

it('牌組庫在別處被改動：候選清單會更新，但本場快照與已確認的 pending 不會被偷換', async () => {
  const { host, guest, code } = await setup();
  await openModal(guest);
  await guest.page.click('#rm-opt-library');
  const optionsBefore = await guest.page.$$eval('#rematch-deck-select option', os => os.map(o => o.textContent));
  const snapName = await guest.get('_deckSnapshot.name');
  await guest.page.evaluate(() => {
    const decks = JSON.parse(localStorage.getItem('hv_decks'));
    decks.push({ id: 'dk_new', name: '剛組好的新牌組', cards: decks[0].cards });
    decks[0].name = '改過名的牌組A';
    decks[0].cards = decks[0].cards.slice(1);
    localStorage.setItem('hv_decks', JSON.stringify(decks));
    window.dispatchEvent(new StorageEvent('storage', { key: 'hv_decks' }));
  });
  const optionsAfter = await guest.page.$$eval('#rematch-deck-select option', os => os.map(o => o.textContent));
  assert.notDeepEqual(optionsAfter, optionsBefore);
  assert.ok(optionsAfter.some(t => t.includes('剛組好的新牌組')));
  assert.equal(await guest.get('_deckSnapshot.name'), snapName, '本場快照不變');
  assert.equal(await guest.get('_deckSnapshot.cards.length'), 40);
  await guest.page.evaluate(() => { document.dispatchEvent(new Event('visibilitychange')); window.dispatchEvent(new Event('focus')); });
  await guest.page.click('button[onclick="refreshRematchCandidates(true)"]');
  assert.match(await guest.page.textContent('#toast'), /已重新讀取牌組庫/);
  // 沿用本場：即使牌組庫裡原本那副被改壞了，沿用的仍是開局當下的完整 40 張
  await guest.page.click('#rm-opt-snapshot');
  await guest.page.click('#rematch-main-btn');
  await host.page.waitForSelector('#rematch-overlay.open');
  await host.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], await host.get('JSON.stringify(1) && _ctl.prevMatch'));
  assert.equal(await guest.get('L.pile.length'), 40);
  assert.ok(ctlOf(code).epoch === 2);
});

// ── 13. 鎖定時的入口守衛 ─────────────────────────────────────
it('邀請期間所有會改牌或寫入的入口都被擋下：不改本機、不送出任何寫入', async () => {
  const { host, guest } = await setup();
  await host.run('drawCard(); drawCard(); drawCard()');
  await settle(host, guest);
  await invite(guest);
  await host.waitFor('actionLocked()');

  const entries = [
    'drawCard()', 'drawToSix()', 'shufflePile()', 'endTurn()', "selectAction('serve')", 'undoLastAction()',
    'declareLost()', "adjustSets('host', 1)", "adjustScore('host', 1)", "adjustCounter('atk', 1)", 'adjustSet()',
    "forcePhase('serve')", 'addToSetPool()', 'loseRallySetPool()', 'openPeekSetup()', 'executePeek()', 'openDiceModal()',
    "pickDiceSide('單')", "chooseTurn('先攻')", "placeCard(0, 'attack')", 'discardFromHand(0)', "returnHandToPile(0, 'top')",
    "applyGuts(0, 'attack')", "bulkReturnDrop('top')", "_dropPlace('x.webp', 'hand')", "handleDrop('hand', false)",
    "moveCardFromStack('attack', 'x.webp', 'hand')",
  ];
  const before = await host.get('JSON.stringify({h: L.hand, p: L.pile, s: L.setPool, u: L.undoStack.length})');
  const n0 = h.hub.log.length;
  const wl0 = (await host.rtdb(r => r.writeLog())).length;
  for (const e of entries) {
    await host.page.evaluate(code => { try { const r = (0, eval)(code); if (r && r.catch) r.catch(() => {}); } catch (_) {} }, e);
  }
  await host.page.keyboard.press('d');
  await host.page.keyboard.press('Enter');
  await host.page.waitForTimeout(300);
  assert.equal(await host.get('JSON.stringify({h: L.hand, p: L.pile, s: L.setPool, u: L.undoStack.length})'), before);
  assert.equal(h.hub.log.length, n0, '沒有任何寫入到達伺服器');
  assert.equal((await host.rtdb(r => r.writeLog())).length, wl0, '也沒有任何寫入被發出');
  assert.equal(await host.page.evaluate(() => getComputedStyle(document.getElementById('hand-area')).pointerEvents), 'none');
});

it('樂觀鎖：按下邀請的同一個瞬間，舊動作就已經進不去（不等伺服器回應）', async () => {
  const { host, guest } = await setup();
  const r = await host.page.evaluate(async () => {
    const p = sendInvite();
    const before = L.hand.length;
    drawCard();
    const after = L.hand.length;
    await p;
    return [before, after, actionLocked()];
  });
  assert.deepEqual(r, [0, 0, true]);
  await settle(host, guest);
});

// ── 14. 上一題的輸一球補牌資格不受影響 ─────────────────────────
it('輸一球補牌資格：重開後清空、舊事件不授予新場資格，新場裡雙方連動照舊', async () => {
  const { host, guest, code, m1 } = await setup();
  await host.run('drawCard(); drawCard()');
  await host.page.evaluate(() => { addToSetPool(); });
  await host.page.click('#gen-confirm-ok-btn');
  await host.waitFor('L.setPool.length === 2');
  await host.page.evaluate(() => { loseRallySetPool(); });
  await host.page.waitForFunction(() => document.getElementById('gen-confirm-overlay').style.display === 'flex');
  await host.page.click('#gen-confirm-ok-btn');
  await host.waitFor('_postLossRedrawEligible === true');
  await guest.waitFor('_postLossRedrawEligible === true');

  await invite(host);
  await pickAndSubmit(guest);
  await waitNewMatch([host, guest], m1);
  await settle(host, guest);
  for (const p of [host, guest]) {
    assert.equal(await p.get('_postLossRedrawEligible'), false);
    assert.equal(await p.get('_lastRallyLossId'), null);
    assert.equal(await p.get('_openingPhase'), true);
    assert.equal(await p.get('gameState.rallyLoss'), undefined);
  }

  // 新場：房主補池、輸一球 → 雙方再次取得資格，guest 一鍵補到 6 張
  await host.run('drawCard()');
  await host.page.evaluate(() => { addToSetPool(); });
  await host.page.click('#gen-confirm-ok-btn');
  await host.waitFor('L.setPool.length === 2');
  await host.page.evaluate(() => { loseRallySetPool(); });
  await host.page.waitForFunction(() => document.getElementById('gen-confirm-overlay').style.display === 'flex');
  await host.page.click('#gen-confirm-ok-btn');
  await host.waitFor('_postLossRedrawEligible === true');
  await guest.waitFor('_postLossRedrawEligible === true');
  await guest.run('setOpeningPhase(false); drawToSix()');
  assert.equal(await guest.get('L.hand.length'), 6);
});

// ── 15. presence 清理 ───────────────────────────────────────
it('套用途中房主離開：脈絡失效、不留殘餘寫入；對手看到離線，也能離開房間', async () => {
  const { host, guest, code, m1 } = await setup();
  h.hub.delay(guest.clientId, /\/ctl\/ack\/guest$/);
  await invite(host);
  await pickAndSubmit(guest);
  await host.waitFor(`_appliedMatchId !== ${JSON.stringify(m1)}`);
  assert.equal(ctlOf(code).phase, 'applying');
  const hostCx = await host.page.evaluate(() => { window.__cx = gx(); return true; });
  await host.page.evaluate(() => leaveRoom());
  await host.page.waitForFunction(() => document.getElementById('screen-lobby').classList.contains('active'));
  assert.equal(await host.page.evaluate(() => window.__cx.live() === false && _gctx === null), true);
  await guest.waitFor('gameState && gameState.presence && !gameState.presence.host');
  assert.match(await guest.page.textContent('#rematch-status'), /目前離線/);
  assert.equal(h.hub.get(`games/${code}/presence/host`), null);
  assert.equal(await guest.get('actionLocked()'), true);
  await guest.page.evaluate(() => leaveRoom());
  await guest.page.waitForFunction(() => document.getElementById('screen-lobby').classList.contains('active'));
  h.hub.flushDelayed(guest.clientId);
});

// ── 15b. 房間租約與清理（proto 2 的 playing2）────────────────────
it('在線續租：長時間打牌 createdAt 持續更新；離房後租約計時器停止，不寫已離開的房', async () => {
  const { host, guest, code } = await setup();
  const t0 = h.hub.get(`rooms/${code}/createdAt`);
  for (const p of [host, guest]) await p.run('ROOM_LEASE_MS = 150; startRoomLease()');
  await new Promise(r => setTimeout(r, 900));
  const t1 = h.hub.get(`rooms/${code}/createdAt`);
  assert.ok(t1 > t0, `createdAt 被續租 ${t0} -> ${t1}`);
  assert.equal(h.hub.get(`rooms/${code}/status`), 'playing2');
  for (const p of [host, guest]) {
    await p.page.evaluate(() => leaveRoom());
    await p.page.waitForFunction(() => document.getElementById('screen-lobby').classList.contains('active'));
    assert.equal(await p.get('_leaseTimer'), null);
  }
  await new Promise(r => setTimeout(r, 500));                         // 離房前已送出的續租可能還在路上，先讓它落地
  const t2 = h.hub.get(`rooms/${code}/createdAt`);
  await new Promise(r => setTimeout(r, 700));
  assert.equal(h.hub.get(`rooms/${code}/createdAt`), t2, '離房後不再續租');
});

it('大廳清理：playing2 不看 presence 只看租約期限；舊版 playing 的 presence 政策不變', async () => {
  const d = deckSets();
  const lobby = await h.newPlayer('旁觀大廳', { decks: d.host });
  const now = Date.now();
  const mk = (id, status, age) => {
    h.hub.seed(`rooms/${id}`, { id, status, createdAt: now - age, hostName: id, hostAvatar: '🦅', deckName: 'X', proto: 2 });
    h.hub.seed(`games/${id}`, { ctl: { proto: 2, started: true } });
  };
  mk('2001', 'playing2', 5 * 60 * 1000);          // 兩端都沒 presence，但租約還新 → 保留
  mk('2002', 'playing2', 31 * 60 * 1000);         // 超過 30 分鐘沒人續租 → 清掉
  h.hub.seed('rooms/2003', { id: '2003', status: 'playing', createdAt: now - 1000, hostName: 'x' });
  h.hub.seed('games/2003', { started: true });    // 舊版 playing 且沒有 presence → 舊政策照舊清掉
  h.hub.seed('rooms/2004', { id: '2004', status: 'playing', createdAt: now, hostName: 'x' });
  h.hub.seed('games/2004/presence/host', true);   // 舊版 playing 有人在線 → 保留
  h.hub.seed('rooms/trigger2', { id: 'trigger2', status: 'waiting', createdAt: now, hostName: 't' });
  // 大廳清理是事件驅動＋非同步讀 presence：輪詢到結果出現（上限 5 秒），不靠固定等待時間
  for (let i = 0; i < 100 && (h.hub.get('rooms/2002') || h.hub.get('rooms/2003')); i++) await new Promise(r => setTimeout(r, 50));
  await new Promise(r => setTimeout(r, 200));
  assert.ok(h.hub.get('rooms/2001'), 'playing2 租約內不因 presence 為空而被清');
  assert.ok(h.hub.get('games/2001'));
  assert.equal(h.hub.get('rooms/2002'), null);
  assert.equal(h.hub.get('games/2002'), null);
  assert.equal(h.hub.get('rooms/2003'), null);
  assert.ok(h.hub.get('rooms/2004'));
  const row = await lobby.page.$eval('.room-item:has(.room-code-tag:text("2001")) .room-status', el => el.textContent.trim());
  assert.match(row, /對戰中/);
});

it('雙方都離線不會被 60 秒踢出房間；回來重新載入仍能看到「重新加入」', async () => {
  const { host, guest, code } = await setup();
  // proto 2 不啟動「雙方離線 → 清房」的計時器
  await host.run("handlePresenceChange({ presence: {}, players: {} }, { presence: { host: true, guest: true } })");
  assert.equal(await host.get('_presenceKickTimer'), null);
  for (const p of [host, guest]) await p.rtdb(r => r.setOnline(false));
  await new Promise(r => setTimeout(r, 300));
  assert.equal(h.hub.get(`games/${code}/presence`), null);
  assert.ok(h.hub.get(`rooms/${code}`));
  await host.page.reload();
  await host.page.waitForSelector('#rejoin-banner', { state: 'visible' });
  await host.page.click('#rejoin-banner button.primary');
  await host.page.waitForFunction(() => document.getElementById('screen-game').classList.contains('active'));
  assert.equal(await host.get('roomId'), code);
});

// ── 15c. 保存失敗不能半套 ───────────────────────────────────
it('套用新場時 localStorage 寫不進去：維持鎖定、不 ack、保留 pending；恢復後不重洗地完成', async () => {
  const { host, guest, code, m1 } = await setup();
  await invite(host);
  await guest.page.waitForSelector('#rematch-overlay.open');
  await guest.page.evaluate(m => {
    window.__real = Storage.prototype.setItem;
    Storage.prototype.setItem = function (k, v) {
      if (k === 'hv_game_session' && JSON.parse(v).appliedMatchId !== m) throw new Error('quota');
      return window.__real.call(this, k, v);
    };
  }, m1);
  await guest.page.click('#rematch-main-btn');
  await guest.waitFor('_rmUi.applyFailed === true');
  const pend = (await sessionOf(guest)).pending;
  assert.ok(pend && pend.pile.length === 40, 'pending 原樣保留');
  assert.equal(await guest.get('_appliedMatchId'), m1, '本機狀態沒有半套');
  assert.equal(await guest.get('actionLocked()'), true);
  assert.equal(await guest.page.textContent('#rematch-main-btn'), '重試套用');
  assert.notEqual(ctlOf(code).ack?.guest, ctlOf(code).activeMatch, '沒存好就不能 ack');
  await guest.page.evaluate(() => { Storage.prototype.setItem = window.__real; });
  await guest.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], m1);
  assert.deepEqual(await guest.get('L.pile'), pend.pile, '同一份牌序，沒有重洗');
});

it('恢復選牌套用時存不進去：同樣不半套，修好後可完成', async () => {
  const { host, guest, m1 } = await setup();
  await guest.page.evaluate(() => { window.applyPendingMatch = async () => {}; });
  await invite(host);
  await pickAndSubmit(guest);
  await host.waitFor(`_ctl && _ctl.phase === 'applying'`);
  await reloadAndRejoin(guest, () => {
    const s = JSON.parse(localStorage.getItem('hv_game_session'));
    delete s.pending;
    localStorage.setItem('hv_game_session', JSON.stringify(s));
  });
  await guest.page.waitForSelector('#rematch-overlay.open');
  await guest.page.evaluate(m => {
    window.__real = Storage.prototype.setItem;
    Storage.prototype.setItem = function (k, v) {
      if (k === 'hv_game_session' && JSON.parse(v).appliedMatchId !== m) throw new Error('quota');
      return window.__real.call(this, k, v);
    };
  }, m1);
  await guest.page.click('#rematch-main-btn');
  await guest.waitFor('_rmUi.applyFailed === true');
  assert.equal(await guest.get('_appliedMatchId'), m1);
  const pile = await guest.get('_rmPending.pile');
  await guest.page.evaluate(() => { Storage.prototype.setItem = window.__real; });
  await guest.page.click('#rematch-main-btn');
  await waitNewMatch([host, guest], m1);
  assert.deepEqual(await guest.get('L.pile'), pile);
});

// ── 15d. 舊房流程不得污染新房 ─────────────────────────────────
it('舊房的 ready 晚回覆：離房進新房後不改新房的 _ctl、mutex、UI', async () => {
  const { host, guest, code } = await setup();
  h.hub.delay(guest.clientId, new RegExp(`^games/${code}/ctl/ready/guest$`));
  await invite(host);
  await guest.page.waitForSelector('#rematch-overlay.open');
  await guest.page.click('#rematch-main-btn');                          // 舊房的 ready 卡在路上
  await guest.waitFor('_rmBusy === true');
  await guest.page.evaluate(() => leaveRoom());
  await guest.waitFor('roomId === null');
  const other = await h.newPlayer('另一位', { decks: deckSets().host });
  const code2 = await h.startMatch(guest, other);
  const m2 = await guest.get('_appliedMatchId');
  h.hub.flushDelayed(guest.clientId);                                    // 舊房的回覆現在才到
  await settle(guest, other);
  assert.equal(await guest.get('roomId'), code2);
  assert.equal(await guest.get('_ctl.activeMatch'), m2);
  assert.equal(await guest.get('_rmBusy'), false);
  assert.equal(await guest.get('_rmUi.fatal'), false);
  assert.equal(await guest.get('actionLocked()'), false);
  assert.equal(await guest.get('_rmPending'), null);
});

// ── 16. 手機版面 ────────────────────────────────────────────
it('手機：抽屜裡有同一個入口，視窗不超出螢幕，按鈕達觸控尺寸，整個流程用點的完成', async () => {
  const { host, guest, code, m1 } = await setup({ guestMobile: true });
  await guest.page.evaluate(() => window.openMobileDrawer());
  await guest.page.waitForSelector('#mobile-drawer-content [data-rematch-open]');
  const inDrawer = await guest.page.evaluate(() => {
    const b = document.querySelector('#mobile-drawer-content [data-rematch-open]');
    const r = b.getBoundingClientRect();
    return { w: r.width, h: r.height, vis: r.width > 0 && r.height > 0 };
  });
  assert.ok(inDrawer.vis);
  assert.ok(inDrawer.h >= 40, `抽屜按鈕高度 ${inDrawer.h}`);
  await guest.page.tap('#mobile-drawer-content [data-rematch-open]');
  await guest.page.waitForSelector('#rematch-overlay.open');
  await guest.page.evaluate(() => closeRematchModal());
  await guest.page.evaluate(() => window.closeMobileDrawer && window.closeMobileDrawer());

  await invite(host);                                                 // 房主（桌面）發起
  await guest.page.waitForSelector('#rematch-overlay.open');
  const box = await guest.page.evaluate(() => {
    const r = document.getElementById('rematch-box').getBoundingClientRect();
    const btns = [...document.querySelectorAll('#rematch-actions .btn')].filter(b => b.offsetParent).map(b => b.getBoundingClientRect().height);
    return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, vw: innerWidth, vh: innerHeight, btns, sw: document.documentElement.scrollWidth };
  });
  assert.ok(box.left >= 0 && box.right <= box.vw, `視窗左右在螢幕內 ${JSON.stringify(box)}`);
  assert.ok(box.top >= 0 && box.bottom <= box.vh, '視窗上下在螢幕內');
  assert.ok(box.btns.length >= 2 && box.btns.every(x => x >= 44), `按鈕觸控高度 ${box.btns}`);
  assert.ok(box.sw <= box.vw + 1, '沒有橫向捲動');
  await guest.page.tap('#rm-opt-library');
  await guest.page.selectOption('#rematch-deck-select', 'dk_c');
  await guest.page.tap('#rematch-main-btn');
  await waitNewMatch([host, guest], m1);
  assert.equal(await guest.get('L.pile.length'), 40);
  assert.equal(ctlOf(code).phase, 'idle');
});
