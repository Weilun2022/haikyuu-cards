'use strict';
// 真實瀏覽器 + mock Firebase 的對戰測試 harness：
//  - 本機靜態伺服器提供 repo 內的 game.html（不碰任何外部網路；Firebase SDK 的 CDN 請求直接換成空腳本）
//  - 每位玩家一個獨立的 browser context（localStorage 各自獨立）
//  - 所有頁面的 Firebase 都接到同一個 Node 端 hub（tests/helpers/mock-rtdb-hub.js），不會有任何真實寫入
// 環境找不到 playwright-core／chromium 時 loadPlaywright() 回傳 null，測試檔自行 skip。

const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const { createHub, clientSource } = require('./mock-rtdb-hub.js');

const ROOT = path.join(__dirname, '..', '..');

function loadPlaywright() {
  const candidates = [];
  if (process.env.PLAYWRIGHT_CORE) candidates.push(process.env.PLAYWRIGHT_CORE);
  candidates.push('playwright-core', 'playwright');
  const home = os.homedir();
  const local = process.env.LOCALAPPDATA || path.join(home, 'AppData', 'Local');
  try {
    const npx = path.join(local, 'npm-cache', '_npx');
    for (const d of fs.readdirSync(npx)) candidates.push(path.join(npx, d, 'node_modules', 'playwright-core'));
  } catch (_) {}
  candidates.push(path.join(home, '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright-core'));
  for (const c of candidates) {
    try { const pw = require(c); if (pw && pw.chromium) return pw; } catch (_) {}
  }
  return null;
}

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.mp3': 'audio/mpeg',
};

function startStaticServer() {
  const server = http.createServer((req, res) => {
    try {
      const url = new URL(req.url, 'http://localhost');
      let rel = decodeURIComponent(url.pathname);
      if (rel === '/') rel = '/game.html';
      const file = path.normalize(path.join(ROOT, rel));
      if (!file.startsWith(ROOT)) { res.writeHead(403); res.end(); return; }
      fs.readFile(file, (err, buf) => {
        if (err) { res.writeHead(404); res.end(); return; }
        res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
        res.end(buf);
      });
    } catch (e) { res.writeHead(500); res.end(); }
  });
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve({
    server, origin: `http://127.0.0.1:${server.address().port}`, close: () => new Promise(r => server.close(r)),
  })));
}

// 從 cards_data.js 挑出能組成合法牌組的卡：32 張角色 + 8 張事件（各 1 張）
function loadCards() {
  const src = fs.readFileSync(path.join(ROOT, 'cards_data.js'), 'utf8');
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(src + '\nthis.CD = CARDS_DATA;', ctx);
  return JSON.parse(JSON.stringify(ctx.CD.cards));
}

function makeDeck(cards, { id, name, offset = 0, events = 8 }) {
  const chars = cards.filter(c => c.category === 'CHARACTER').slice(offset, offset + (40 - events));
  const evs = cards.filter(c => c.category === 'EVENT').slice(offset, offset + events);
  return { id, name, cards: [...chars, ...evs].map(c => ({ image_file: c.image_file, count: 1 })) };
}

class Player {
  constructor(name, page, context) { this.name = name; this.page = page; this.context = context; }
  evaluate(fn, arg) { return this.page.evaluate(fn, arg); }
  // 頁面全域 let 變數要用 indirect eval 才讀得到（ADR 0003）
  get(expr) { return this.page.evaluate(e => (0, eval)(e), expr); }
  run(code) { return this.page.evaluate(c => (0, eval)(c), code); }
  rtdb(fn, arg) { return this.page.evaluate(([f, a]) => (new Function('r', 'a', `return (${f})(r, a)`))(window.__rtdb, a), [fn.toString(), arg]); }
  async waitFor(expr, timeout = 8000) {
    await this.page.waitForFunction(e => !!(0, eval)(e), expr, { timeout });
  }
}

async function createHarness({ viewport = { width: 1280, height: 800 } } = {}) {
  const pw = loadPlaywright();
  if (!pw) return null;
  let browser;
  try { browser = await pw.chromium.launch({ headless: true }); } catch (e) { return null; }
  const web = await startStaticServer();
  const hub = createHub();
  const cards = loadCards();
  const players = [];
  const consoleErrors = [];

  async function newPlayer(name, { deck, decks, mobile = false, vp = viewport, seedStorage = {} } = {}) {
    const clientId = `${name}-${players.length}`;
    const context = await browser.newContext(mobile
      ? { viewport: { width: 390, height: 780 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 }
      : { viewport: vp });
    // 外部網路一律擋掉；Firebase SDK 的 CDN 腳本換成空檔（真正的 firebase 由 mock 提供）
    await context.route('**/*', route => {
      const u = route.request().url();
      if (u.startsWith(web.origin)) return route.continue();
      if (/gstatic\.com\/firebasejs/.test(u)) return route.fulfill({ status: 200, contentType: 'text/javascript', body: '' });
      return route.abort();
    });
    const page = await context.newPage();
    page.on('pageerror', e => consoleErrors.push(`[${name}] pageerror: ${e.message}`));
    page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) consoleErrors.push(`[${name}] console.error: ${m.text()}`); });

    // hub → 頁面：同一個頁面的投遞排成佇列，保證「資料樹更新」一定先於「回覆」
    let chain = Promise.resolve();
    hub.connect(clientId, msg => {
      chain = chain.then(() => page.evaluate(m => window.__hubDeliver(m), msg)).catch(() => {});
    });
    await page.exposeFunction('__hubSend', msg => { hub.receive(clientId, msg); });

    const decksToSeed = decks || [deck || makeDeck(cards, { id: 'dk_a', name: `${name}的牌組A` })];
    await context.addInitScript(({ src, id, decksJson, storage }) => {
      (0, eval)(src);
      const client = window.MockRtdb.createClient({ clientId: id, send: msg => window.__hubSend(msg) });
      window.__hubDeliver = m => client.deliver(m);
      window.__rtdb = client.controls;
      window.firebase = window.MockRtdb.createFirebase(client);
      client.hello();
      try {
        localStorage.setItem('hv_firebase_config', JSON.stringify({ apiKey: 'mock', databaseURL: 'https://mock.invalid' }));
        if (!localStorage.getItem('hv_decks')) localStorage.setItem('hv_decks', decksJson);
        Object.keys(storage).forEach(k => { if (!localStorage.getItem(k)) localStorage.setItem(k, storage[k]); });
      } catch (_) {}
    }, { src: clientSource, id: clientId, decksJson: JSON.stringify(decksToSeed), storage: Object.assign({ hv_tutorial_dismissed: '1' }, seedStorage) });
    await page.goto(web.origin + '/game.html');
    await page.waitForFunction(() => document.getElementById('screen-lobby')?.classList.contains('active'));
    const p = new Player(name, page, context);
    p.clientId = clientId;
    players.push(p);
    return p;
  }

  async function lobbyFill(p, deckId) {
    await p.page.fill('#player-name', p.name);
    await p.page.selectOption('#deck-select', deckId);
  }

  // 建房、加入、開始：全程點真實的按鈕
  async function startMatch(host, guest, { hostDeck = 'dk_a', guestDeck = 'dk_a' } = {}) {
    await lobbyFill(host, hostDeck);
    await host.page.click('button[onclick="createRoom()"]');
    await host.page.waitForFunction(() => document.getElementById('screen-waiting').classList.contains('active'));
    const code = (await host.page.textContent('#w-code')).trim();
    await lobbyFill(guest, guestDeck);
    await guest.page.fill('#join-code', code);
    await guest.page.click('button[onclick="joinByCode()"]');
    await guest.page.waitForFunction(() => document.getElementById('screen-waiting').classList.contains('active'));
    await host.page.waitForFunction(() => !document.getElementById('start-btn').disabled);
    await host.page.click('#start-btn');
    for (const p of [host, guest]) {
      await p.page.waitForFunction(() => document.getElementById('screen-game').classList.contains('active'));
    }
    await settle(host, guest);
    return code;
  }

  // 讓雙方的非同步同步（含去抖計時）都跑完
  async function settle(...ps) {
    for (let i = 0; i < 3; i++) {
      await new Promise(r => setTimeout(r, 220));
      for (const p of ps) await p.page.evaluate(() => new Promise(r => setTimeout(r, 0)));
    }
  }

  async function closePlayers() {
    for (const p of players.splice(0)) { try { await p.context.close(); } catch (_) {} }
  }

  async function close() {
    await closePlayers();
    await browser.close();
    await web.close();
  }

  return { pw, browser, web, hub, cards, players, consoleErrors, newPlayer, startMatch, settle, close, closePlayers, makeDeck: (o) => makeDeck(cards, o) };
}

module.exports = { createHarness, loadPlaywright, makeDeck, loadCards };
