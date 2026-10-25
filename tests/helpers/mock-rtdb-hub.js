'use strict';
// Firebase Realtime Database 模擬的伺服器端（Node）。權威資料樹、依到達順序套用寫入、
// 對每個客戶端按固定順序投遞「資料樹更新 → 回覆」（所以客戶端看到的順序與真實 SDK 一致：先事件、後回呼）。
// 客戶端那一半見 mock-rtdb-client.js；rules 刻意不模擬——專案沒有 RTDB rules，
// 要測「寫入被拒」就用 reject() 明確指定。

const fs = require('node:fs');
const path = require('node:path');

const MockRtdb = require('./mock-rtdb-client.js');
const clientSrc = fs.readFileSync(path.join(__dirname, 'mock-rtdb-client.js'), 'utf8');
const H = MockRtdb.helpers;

const parts = p => String(p || '').split('/').filter(Boolean);

function createHub({ now = () => Date.now() } = {}) {
  let tree = null;
  const clients = new Map();   // id -> { online, deliver, od: [{path, action, value}], rules: [] }
  const log = [];              // 伺服器套用寫入的順序：{ clientId, path, kind, value }
  const listeners = [];

  function emit(entry) { log.push(entry); listeners.forEach(fn => fn(entry)); }

  function broadcastTree() {
    for (const [, c] of clients) if (c.online) c.deliver({ t: 'tree', tree: H.clone(tree) });
  }

  function applySet(p, value, clientId, kind) {
    tree = H.setPath(tree, p, H.resolveSV(value, now()));
    emit({ clientId, path: parts(p).join('/'), kind, value: H.clone(value) });
  }

  function matchesReject(c, paths) {
    for (const rule of c.rules) {
      if (rule.times <= 0) continue;
      if (paths.some(p => rule.re.test(p))) { rule.times--; return rule; }
    }
    return null;
  }

  function runOd(clientId) {
    const c = clients.get(clientId);
    const ops = c.od.splice(0);
    ops.forEach(op => {
      if (op.action === 'remove') applySet(op.path, null, `${clientId}[onDisconnect]`, 'remove');
      else if (op.action === 'set') applySet(op.path, op.value, `${clientId}[onDisconnect]`, 'set');
      else if (op.action === 'update') {
        Object.keys(op.value || {}).forEach(k => applySet(parts(op.path).concat(parts(k)).join('/'), op.value[k], `${clientId}[onDisconnect]`, 'set'));
      }
    });
    if (ops.length) broadcastTree();
  }

  const hub = {
    log,
    clients,
    tree: () => H.clone(tree),
    get: p => H.toRead(H.getPath(tree, p)),
    onWrite(fn) { listeners.push(fn); },
    // 直接塞資料（測試造場用，不經任何客戶端）
    seed(p, value) { applySet(p, value, 'seed', 'set'); broadcastTree(); },

    connect(id, deliver) {
      clients.set(id, { online: true, deliver, od: [], rules: [], delay: [], delayed: [] });
    },

    // 讓某個客戶端接下來符合 pathRegex 的寫入被駁回（預設 1 次）
    reject(id, pathRegex, { times = 1, message = 'PERMISSION_DENIED' } = {}) {
      clients.get(id).rules.push({ re: pathRegex instanceof RegExp ? pathRegex : new RegExp(pathRegex), times, message });
    },

    // 最壞順序：符合 pathRegex 的寫入先卡在「路上」，後面發出的寫入照常套用；flushDelayed() 才讓它們落地。
    // 用來證明舊寫入晚到時只會落在舊場路徑，不依賴 Firebase 是否保序
    delay(id, pathRegex) { clients.get(id).delay.push(pathRegex instanceof RegExp ? pathRegex : new RegExp(pathRegex)); },
    flushDelayed(id) {
      const c = clients.get(id);
      c.delay = [];
      c.delayed.splice(0).forEach(m => hub.receive(id, Object.assign({}, m, { _flushed: true })));
    },
    delayedCount(id) { return clients.get(id).delayed.length; },
    // 丟掉還卡在路上的寫入（模擬送出者在它抵達前就當機）並取消延遲規則
    discardDelayed(id) { const c = clients.get(id); c.delay = []; c.delayed.splice(0); },

    // 模擬伺服器端逾時判定該客戶端斷線（不經客戶端自己的 offline 訊息）
    dropClient(id) {
      const c = clients.get(id);
      if (!c) return;
      c.online = false;
      runOd(id);
    },

    receive(id, msg) {
      const c = clients.get(id);
      if (!c) return;
      const reply = (extra) => c.deliver(Object.assign({ t: 'reply', rid: msg.rid, ok: true }, extra));
      const fail = (error, extra) => c.deliver(Object.assign({ t: 'reply', rid: msg.rid, ok: false, error }, extra));

      switch (msg.t) {
        case 'hello':
          c.online = true;
          c.deliver({ t: 'tree', tree: H.clone(tree) });
          return;
        case 'offline':
          c.online = false;
          runOd(id);
          return;
        case 'online':
          c.online = true;
          c.deliver({ t: 'tree', tree: H.clone(tree) });
          return;
        case 'get':
          return reply({ value: H.clone(H.getPath(tree, msg.path)) });
        case 'od': {
          if (msg.action === 'cancel') c.od = c.od.filter(o => o.path !== msg.path);
          else c.od.push({ path: msg.path, action: msg.action, value: msg.value });
          return reply({});
        }
        case 'w': {
          const paths = msg.kind === 'update'
            ? Object.keys(msg.values || {}).map(k => parts(msg.path).concat(parts(k)).join('/'))
            : [msg.path];
          if (!msg._flushed && c.delay.some(re => paths.some(p => re.test(p)))) { c.delayed.push(msg); return; }
          const rule = matchesReject(c, paths);
          if (rule) return fail(rule.message);
          if (msg.kind === 'update') {
            Object.keys(msg.values || {}).forEach(k => applySet(parts(msg.path).concat(parts(k)).join('/'), msg.values[k], id, 'update'));
          } else {
            applySet(msg.path, msg.value, id, 'set');
          }
          broadcastTree();
          return reply({});
        }
        case 'tx': {
          const rule = matchesReject(c, [msg.path]);
          if (rule) return fail(rule.message);
          const current = H.getPath(tree, msg.path);
          if (H.stable(current) !== H.stable(msg.expected)) {
            return fail('CONFLICT', { conflict: true, current: H.clone(current) });
          }
          const resolved = H.resolveSV(msg.value, now());
          applySet(msg.path, resolved, id, 'tx');
          broadcastTree();
          return reply({ value: H.clone(H.normalize(H.clone(resolved))) });
        }
        default:
          throw new Error('unknown message ' + msg.t);
      }
    },
  };

  return hub;
}

// 在 Node 內直接跑客戶端（不需要瀏覽器）：用於 mock 自身的行為測試。
// latency：單向延遲（ms）。要有延遲才看得到「預先回呼 → 確認」之間的空檔；相同延遲的 setTimeout 仍保持先進先出
function connectDirect(hub, id, { clock, latency = 2 } = {}) {
  const client = MockRtdb.createClient({
    clientId: id,
    clock,
    send: msg => { setTimeout(() => hub.receive(id, msg), latency); },
  });
  hub.connect(id, msg => { setTimeout(() => client.deliver(msg), latency); });
  client.hello();
  return client;
}

module.exports = { createHub, connectDirect, helpers: H, clientSource: clientSrc, MockRtdb };
