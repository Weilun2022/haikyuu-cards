'use strict';
// 開局步驟提示（issue #112）：雙方各成功出牌一次後自動隱藏。
// 真實瀏覽器 + mock Firebase；標記是遠端的 openingPlayed/r{roundReset}/{role}，與補牌資格（_openingPhase）互相獨立。
// 環境找不到 Playwright／Chromium 時整個檔案 skip（不算失敗）。
const test = require('node:test');
const assert = require('node:assert/strict');
const { createHarness } = require('./helpers/game-harness.js');

const T = { timeout: 120000 };
let h = null;

test.before(async () => { h = await createHarness(); });
test.after(async () => { if (h) await h.close(); });
test.beforeEach(() => { if (h) h.consoleErrors.length = 0; });
test.afterEach(async () => { if (h) await h.closePlayers(); });

function it(name, fn) {
  test(name, T, async t => {
    if (!h) { t.skip('找不到 Playwright／Chromium'); return; }
    await fn(t);
    assert.deepEqual(h.consoleErrors, [], '頁面不應出現未處理的錯誤');
  });
}

async function setup(opts = {}) {
  const host = await h.newPlayer('甲', { mobile: !!opts.hostMobile });
  const guest = await h.newPlayer('乙', { mobile: !!opts.guestMobile });
  const code = await h.startMatch(host, guest);
  const mid = await host.get('_appliedMatchId');
  return { host, guest, code, mid };
}

const marker = (code, mid, role, gen = 'r0') => h.hub.get(`games/${code}/m/${mid}/openingPlayed/${gen}/${role}`) ?? undefined;
const settle = (...ps) => h.settle(...ps);

// 取出指定類別的一張牌放進手牌，回傳它在手牌的 index
const give = (p, cat) => p.run(`(() => {
  const i = L.pile.findIndex(x => allCards[x] && allCards[x].category === ${JSON.stringify(cat)});
  L.hand.push(L.pile.splice(i, 1)[0]); renderHand(); return L.hand.length - 1;
})()`);

// 讀某個開局步驟面板（原版 #sb-setup，或抽屜裡的 clone）目前的樣子
const guide = (p, drawer = false) => p.page.evaluate(d => {
  const el = d ? document.querySelector('#mobile-drawer-content .sb-setup') : document.getElementById('sb-setup');
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return {
    display: getComputedStyle(el).display, hidden: el.hidden, open: el.open, height: r.height,
    text: el.textContent.replace(/\s+/g, ' '), steps: el.querySelectorAll('ol li').length,
    self: (el.querySelector('[data-og="self"]') || {}).textContent, opp: (el.querySelector('[data-og="opp"]') || {}).textContent,
  };
}, drawer);

const rejoin = async (p, ...all) => {
  h.hub.dropClient(p.clientId);
  await p.page.reload();
  await p.page.waitForSelector('#rejoin-banner', { state: 'visible' });
  await p.page.click('#rejoin-banner button.primary');
  await p.page.waitForFunction(() => document.getElementById('screen-game').classList.contains('active'));
  await settle(...all);
};

const visible = g => g && g.display !== 'none' && g.height > 0;

it('開場：醒目展開、七步不變、兩個「尚未出牌」；抽牌／棄牌／補牌不算出牌', async () => {
  const { host, guest, code, mid } = await setup();
  for (const p of [host, guest]) {
    const g = await guide(p);
    assert.ok(visible(g) && g.open);
    assert.equal(g.steps, 7);
    assert.match(g.self, /○.*你尚未出牌/);
    assert.match(g.opp, /○.*對手尚未出牌/);
    assert.match(g.text, /雙方各出一張牌後自動隱藏/);
  }
  await host.run('drawToSix()');
  await host.run('discardFromHand(0)');
  await settle(host, guest);
  assert.equal(await host.get('L.hand.length'), 5);
  assert.equal(marker(code, mid, 'host'), undefined);
  assert.ok(visible(await guide(host)) && visible(await guide(guest)));
  assert.equal(await host.get('_openingPhase'), true, '開局補牌資格不受教學影響');
});

it('單方出牌：該方顯示已出牌、對方看到對手已出牌，整塊仍在；雙方都出才消失', async () => {
  const { host, guest, code, mid } = await setup();
  await host.run('drawToSix()');
  await host.run("placeCard(0, 'attack')");
  await settle(host, guest);
  assert.equal(marker(code, mid, 'host'), true);
  assert.equal(marker(code, mid, 'guest'), undefined);
  const gh = await guide(host), gg = await guide(guest);
  assert.ok(visible(gh) && visible(gg));
  assert.match(gh.self, /✓.*你已出牌/); assert.match(gh.opp, /○.*對手尚未出牌/);
  assert.match(gg.self, /○.*你尚未出牌/); assert.match(gg.opp, /✓.*對手已出牌/);

  await guest.run('drawToSix()');
  await guest.run("placeCard(0, 'receive')");
  await settle(host, guest);
  for (const p of [host, guest]) {
    const g = await guide(p);
    assert.equal(g.display, 'none');
    assert.equal(g.height, 0, '整塊不占空間');
  }
});

it('四種出牌入口各自寫自己的標記：手牌角色、手牌事件、手牌疊 GUTS、牌庫直接上場', async () => {
  const { host, guest, code, mid } = await setup();
  const path = `games/${code}/m/${mid}/openingPlayed`;
  const clear = async () => { h.hub.seed(path, null); await settle(host, guest); assert.equal(marker(code, mid, 'host'), undefined); };

  const c = await give(host, 'CHARACTER');
  await host.run(`placeCard(${c}, 'attack')`);
  await settle(host, guest);
  assert.equal(marker(code, mid, 'host'), true, '手牌角色');

  await clear();
  const e = await give(host, 'EVENT');
  await host.run(`placeCard(${e}, 'event')`);
  await settle(host, guest);
  assert.equal(marker(code, mid, 'host'), true, '手牌事件');

  await clear();
  const g = await give(host, 'CHARACTER');
  await host.run(`applyGuts(${g}, 'attack')`);
  await settle(host, guest);
  assert.equal(marker(code, mid, 'host'), true, '手牌疊 GUTS');

  await clear();
  await host.run("dragData = { src: 'pile' }; handleDrop('toss', false)");
  await settle(host, guest);
  assert.equal(marker(code, mid, 'host'), true, '牌庫直接上場');
  assert.equal(marker(code, mid, 'guest'), undefined, '不會替對手寫');
});

it('非出牌動作不算：場上移動、棄牌（手牌／場上）、牌庫送棄牌、SET 補牌、結束回合', async () => {
  const { host, guest, code, mid } = await setup();
  await host.run('drawToSix()');
  await host.run("placeCard(0, 'attack')");
  await settle(host, guest);
  h.hub.seed(`games/${code}/m/${mid}/openingPlayed`, null);
  await settle(host, guest);

  await host.run("moveCard('attack', 'receive', getZoneCard(myZonesCopy(), 'attack'))");
  await host.run("discardTopFromZone('receive', getZoneCard(myZonesCopy(), 'receive'))");
  await host.run('discardFromHand(0)');
  await host.run("dragData = { src: 'pile' }; handleDrop('drop', false)");
  await host.run('endTurn()');
  await host.run('void addToSetPool()');
  await host.page.click('#gen-confirm-ok-btn');
  await host.waitFor('L.setPool.length === 2');
  await settle(host, guest);
  assert.equal(marker(code, mid, 'host'), undefined);
  assert.ok(visible(await guide(host)));
});

it('曾出牌的進度不因卡片離場或復原撤回', async () => {
  const { host, guest, code, mid } = await setup();
  await host.run('drawToSix()');
  await host.run("placeCard(0, 'attack')");
  await settle(host, guest);
  await host.run('undoLastAction()');
  await settle(host, guest);
  assert.equal(await host.get('collectCardsFromZones(myZonesCopy()).length'), 0, '牌確實回手牌了');
  assert.equal(marker(code, mid, 'host'), true);
  assert.match((await guide(host)).self, /✓/);
  await host.run("placeCard(0, 'attack')");
  await host.run("discardTopFromZone('attack', getZoneCard(myZonesCopy(), 'attack'))");
  await settle(host, guest);
  assert.equal(marker(code, mid, 'host'), true);
});

it('寫入被伺服器駁回：不算出牌，面板仍在，標記不會永久留在本機', async () => {
  const { host, guest, code, mid } = await setup();
  await host.run('drawToSix()');
  h.hub.reject(host.clientId, new RegExp(`^games/${code}/m/${mid}/(players/host/zones|openingPlayed/r0/host)$`), { times: 2 });
  await host.run("placeCard(0, 'attack').catch(() => {})");
  await settle(host, guest);
  assert.equal(marker(code, mid, 'host'), undefined);
  assert.ok(visible(await guide(host)) && visible(await guide(guest)));
  assert.match((await guide(host)).self, /○/);
  assert.equal(await host.get('gameState.openingPlayed && gameState.openingPlayed.r0 && gameState.openingPlayed.r0.host'), undefined);
});

it('重新整理再加入：進度延續（單方仍顯示、雙方已出仍隱藏）', async () => {
  const { host, guest, code, mid } = await setup();
  await host.run('drawToSix()');
  await host.run("placeCard(0, 'attack')");
  await settle(host, guest);
  const rejoin = async p => {
    h.hub.dropClient(p.clientId);
    await p.page.reload();
    await p.page.waitForSelector('#rejoin-banner', { state: 'visible' });
    await p.page.click('#rejoin-banner button.primary');
    await p.page.waitForFunction(() => document.getElementById('screen-game').classList.contains('active'));
    await settle(host, guest);
  };
  await rejoin(host);
  const g1 = await guide(host);
  assert.ok(visible(g1));
  assert.match(g1.self, /✓/); assert.match(g1.opp, /○/);
  await guest.run('drawToSix()');
  await guest.run("placeCard(0, 'receive')");
  await settle(host, guest);
  await rejoin(guest);
  assert.equal((await guide(guest)).display, 'none');
  await rejoin(host);
  assert.equal((await guide(host)).display, 'none');
  assert.equal(marker(code, mid, 'guest'), true);
});

it('重置本局重新顯示；舊世代標記不影響新局；補牌資格照舊', async () => {
  const { host, guest, code, mid } = await setup();
  await host.run('drawToSix()');
  await guest.run('drawToSix()');
  await host.run("placeCard(0, 'attack')");
  await guest.run("placeCard(0, 'receive')");
  await settle(host, guest);
  assert.equal((await guide(host)).display, 'none');
  assert.equal(await host.get('_openingPhase'), false);

  await host.run('void declareLost()');
  await host.page.click('#gen-confirm-ok-btn');
  await host.waitFor('_roundResetBusy === false && gameState && gameState.roundReset > 0');
  await settle(host, guest);
  for (const p of [host, guest]) {
    const g = await guide(p);
    assert.ok(visible(g), '重置後重新顯示');
    assert.match(g.self, /○/); assert.match(g.opp, /○/);
    assert.equal(await p.get('_openingPhase'), true, '重置後開局補牌資格恢復');
    assert.equal(await p.get('L.hand.length'), 0);
  }
  // 舊世代的遲到寫入（r0）不得讓新世代變成「已出牌」
  h.hub.seed(`games/${code}/m/${mid}/openingPlayed/r0/guest`, true);
  await settle(host, guest);
  assert.ok(visible(await guide(host)));
  // 新世代有人出牌 → 寫到新 key
  await host.run('drawToSix()');
  await host.run("placeCard(0, 'attack')");
  await settle(host, guest);
  const rr = await host.get('gameState.roundReset');
  assert.equal(marker(code, mid, 'host', `r${rr}`), true);
  assert.match((await guide(guest)).opp, /✓/);
});

it('同房再開一場：新場重新顯示，不沿用舊場進度', async () => {
  const { host, guest, code, mid } = await setup();
  await host.run('drawToSix()');
  await guest.run('drawToSix()');
  await host.run("placeCard(0, 'attack')");
  await guest.run("placeCard(0, 'receive')");
  await settle(host, guest);
  assert.equal((await guide(guest)).display, 'none');
  await host.page.click('#sb-actions [data-rematch-open]');
  await host.page.waitForSelector('#rematch-overlay.open');
  await host.page.click('#rm-opt-snapshot');
  await host.page.click('#rematch-main-btn');
  await guest.page.waitForSelector('#rematch-overlay.open');
  await guest.page.click('#rm-opt-snapshot');
  await guest.page.click('#rematch-main-btn');
  for (const p of [host, guest]) await p.waitFor(`_appliedMatchId !== ${JSON.stringify(mid)} && !actionLocked()`, 20000);
  await settle(host, guest);
  for (const p of [host, guest]) {
    const g = await guide(p);
    assert.ok(visible(g) && g.open);
    assert.match(g.self, /○/); assert.match(g.opp, /○/);
  }
});

it('手動收合不會被同步重新打開；缺標記的場保守顯示尚未出牌、不補寫', async () => {
  const { host, guest, code, mid } = await setup();
  await host.page.evaluate(() => { const el = document.getElementById('sb-setup'); el.open = false; el.dispatchEvent(new Event('toggle')); });
  await host.run('drawToSix()');
  await guest.run('drawToSix()');
  await host.run("placeCard(0, 'attack')");
  await settle(host, guest);
  assert.equal((await guide(host)).open, false, '使用者收合後，對手出牌等同步不重開');
  // 缺標記的場（例如升級前已在打）：保守顯示尚未出牌，不推斷、不補寫
  h.hub.seed(`games/${code}/m/${mid}/openingPlayed`, null);
  await settle(host, guest);
  await rejoin(guest, host, guest);
  assert.equal(marker(code, mid, 'host'), undefined, '沒有偷偷補寫遷移');
  assert.match((await guide(guest)).opp, /○.*對手尚未出牌/);
  await guest.run("placeCard(0, 'receive')");   // 之後真正出牌就補上標記
  await settle(host, guest);
  assert.equal(marker(code, mid, 'guest'), true);
});

it('手機：抽屜裡的 clone 即時同步（含已開著抽屜），雙方出牌後不占空間', async () => {
  const { host, guest } = await setup({ hostMobile: true });
  await host.run('openMobileDrawer()');
  let d = await guide(host, true);
  assert.ok(visible(d), '抽屜裡有開局步驟');
  assert.equal(d.steps, 7);
  assert.match(d.self, /○/);
  await guest.run('drawToSix()');
  await guest.run("placeCard(0, 'receive')");
  await settle(host, guest);
  d = await guide(host, true);
  assert.match(d.opp, /✓.*對手已出牌/);
  await host.run('drawToSix()');
  await host.run("placeCard(0, 'attack')");
  await settle(host, guest);
  d = await guide(host, true);
  assert.equal(d.display, 'none');
  assert.equal(d.height, 0);
  await host.run('closeMobileDrawer()');
  await host.run('openMobileDrawer()');
  assert.equal((await guide(host, true)).display, 'none', '重開抽屜仍隱藏');
});

it('觀戰者視角不出現「你」的待操作提示', async () => {
  const { host } = await setup();
  const text = await host.page.evaluate(() => {
    isSpectator = true;
    try { updateOpeningGuide(gameState); } finally { isSpectator = false; }
    return document.getElementById('sb-setup').textContent;
  });
  assert.doesNotMatch(text, /你(尚未|已)出牌/);
  assert.match(text, /尚未出牌/);
  await host.run('updateOpeningGuide(gameState)');
});

it('動作開始後才換世代：延遲到達的舊寫入只落在舊世代 key，新局不被視為已出牌', async () => {
  const { host, guest, code, mid } = await setup();
  await host.run('drawToSix()');
  h.hub.delay(host.clientId, /openingPlayed\/r0\/host$/);
  await host.run("void placeCard(0, 'attack')");          // 動作開始時世代是 r0，寫入卡在路上
  for (let i = 0; i < 50 && !h.hub.delayedCount(host.clientId); i++) await new Promise(r => setTimeout(r, 20));
  assert.ok(h.hub.delayedCount(host.clientId), '寫入確實被扣住');
  await guest.run('void declareLost()');
  await guest.page.click('#gen-confirm-ok-btn');
  await guest.waitFor('gameState && gameState.roundReset > 0');
  await settle(host, guest);
  h.hub.flushDelayed(host.clientId);
  await settle(host, guest);
  assert.equal(marker(code, mid, 'host', 'r0'), true, '舊寫入落在舊世代');
  for (const p of [host, guest]) {
    const g = await guide(p);
    assert.ok(visible(g));
    assert.match(g.self + g.opp, /○.*○/, '新世代兩邊都還沒出牌');
    assert.doesNotMatch(g.self + g.opp, /✓/);
  }
});

it('棄牌後放上場（不算出牌）：單方／雙方重新整理加入後仍是「尚未出牌」，不誤隱藏', async () => {
  const { host, guest, code, mid } = await setup();
  for (const p of [host, guest]) {
    await p.run('drawToSix()');
    await p.run('discardFromHand(0)');
    await p.run("_dropPlaceToZone(myZonesCopy().drop[0], 'attack')");
  }
  await settle(host, guest);
  for (const p of [host, guest]) assert.equal(await p.get('collectCardsFromZones(Object.assign({}, myZonesCopy(), {drop: []})).length'), 1, '牌確實放上場了');
  assert.equal(marker(code, mid, 'host'), undefined);
  assert.equal(marker(code, mid, 'guest'), undefined);
  await rejoin(host, host, guest);
  assert.ok(visible(await guide(host)));
  assert.match((await guide(host)).self, /○/);
  await rejoin(guest, host, guest);
  for (const p of [host, guest]) {
    const g = await guide(p);
    assert.ok(visible(g));
    assert.doesNotMatch(g.self + g.opp, /✓/);
  }
});

it('寫入被駁回後重新整理加入：仍是「尚未出牌」，單方／雙方都不誤隱藏', async () => {
  const { host, guest, code, mid } = await setup();
  for (const p of [host, guest]) {
    await p.run('drawToSix()');
    h.hub.reject(p.clientId, new RegExp(`^games/${code}/m/${mid}/(players/${p === host ? 'host' : 'guest'}/zones|openingPlayed/r0/${p === host ? 'host' : 'guest'})$`), { times: 2 });
    await p.run("placeCard(0, 'attack').catch(() => {})");
  }
  await settle(host, guest);
  await rejoin(host, host, guest);
  await rejoin(guest, host, guest);
  for (const p of [host, guest]) {
    const g = await guide(p);
    assert.ok(visible(g));
    assert.doesNotMatch(g.self + g.opp, /✓/);
  }
});
