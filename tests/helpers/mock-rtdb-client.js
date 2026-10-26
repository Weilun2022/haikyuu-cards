/* Firebase Realtime Database 的最小模擬（客戶端這一半）。
 *
 * 傳統腳本：測試以 vm 載入，也用 page.addInitScript 注入到真實的 game.html 頁面。
 * 伺服器那一半是 mock-rtdb-hub.js（Node 端）。兩邊用訊息溝通，傳輸層由使用者注入，
 * 所以同一份客戶端既能跟 Node 內的 hub 直連，也能跨 Playwright 頁面連到共用的 hub。
 *
 * 刻意模擬的真實行為（game.html 的同步邏輯會靠它們）：
 *  - 本機寫入先發出「預先回呼」，伺服器確認後保留、駁回則回滾並再發一次事件
 *  - 同一個客戶端的寫入照發出順序送出；離線或被 hold 時留在佇列，之後照順序重放
 *  - transaction：第一次用本機快取（可強制成 null）執行，被伺服器駁回就用真實值重跑；
 *    applyLocally=false 時不發本機預先事件
 *  - onDisconnect 由伺服器在連線中斷時代為執行
 *  - 陣列讀出時的 null 空洞、空容器消失、.info/connected
 */
(function (root) {
  'use strict';

  const clone = v => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));
  const parts = p => String(p || '').split('/').filter(Boolean);

  // 寫入時：null 與空容器不存在；陣列當成整數 key 的物件
  function normalize(v) {
    if (v === null || v === undefined) return null;
    if (Array.isArray(v)) {
      const o = {};
      v.forEach((x, i) => { const n = normalize(x); if (n !== null) o[i] = n; });
      return Object.keys(o).length ? o : null;
    }
    if (typeof v === 'object') {
      if (v['.sv']) return v;
      const o = {};
      Object.keys(v).forEach(k => { const n = normalize(v[k]); if (n !== null) o[k] = n; });
      return Object.keys(o).length ? o : null;
    }
    return v;
  }

  // 讀出時：key 全是整數且夠密集的物件還原成陣列（缺的位置是 null）
  function toRead(v) {
    if (v === null || v === undefined || typeof v !== 'object') return v === undefined ? null : v;
    const keys = Object.keys(v);
    const out = {};
    keys.forEach(k => { out[k] = toRead(v[k]); });
    if (keys.length && keys.every(k => /^(0|[1-9]\d*)$/.test(k))) {
      const max = Math.max(...keys.map(Number));
      if (max < keys.length * 2) {
        const arr = [];
        for (let i = 0; i <= max; i++) arr.push(out[i] === undefined ? null : out[i]);
        return arr;
      }
    }
    return out;
  }

  function getPath(tree, path) {
    let cur = tree;
    for (const k of parts(path)) {
      if (cur === null || typeof cur !== 'object') return null;
      cur = cur[k];
      if (cur === undefined) return null;
    }
    return cur === undefined ? null : cur;
  }

  function setPath(tree, path, value) {
    const ks = parts(path);
    const v = normalize(clone(value));
    if (!ks.length) return v;
    const root0 = tree && typeof tree === 'object' ? clone(tree) : {};
    let cur = root0;
    for (let i = 0; i < ks.length - 1; i++) {
      if (cur[ks[i]] === null || typeof cur[ks[i]] !== 'object') cur[ks[i]] = {};
      cur = cur[ks[i]];
    }
    if (v === null) delete cur[ks[ks.length - 1]]; else cur[ks[ks.length - 1]] = v;
    return normalize(root0);
  }

  // 把 {'.sv':'timestamp'} 換成實際時間
  function resolveSV(v, now) {
    if (v === null || typeof v !== 'object') return v;
    if (v['.sv'] === 'timestamp') return now;
    if (Array.isArray(v)) return v.map(x => resolveSV(x, now));
    const o = {};
    Object.keys(v).forEach(k => { o[k] = resolveSV(v[k], now); });
    return o;
  }

  const stable = v => JSON.stringify(sortKeys(v));
  function sortKeys(v) {
    if (v === null || typeof v !== 'object') return v;
    if (Array.isArray(v)) return v.map(sortKeys);
    const o = {};
    Object.keys(v).sort().forEach(k => { o[k] = sortKeys(v[k]); });
    return o;
  }

  function createClient({ send, clientId = 'c', clock = () => Date.now() }) {
    let serverTree = null;
    let ready = false;
    let connected = true;
    let held = false;
    let coldTx = false;
    let keySeq = 0;
    let ridSeq = 0;
    const queue = [];            // 還沒送出的訊息（離線或 hold 中）
    const pending = [];          // 對本機已生效、伺服器尚未確認的寫入
    const waiting = new Map();   // rid -> { resolve, reject }
    const listeners = [];        // { path, cb, last, initial }
    const infoListeners = [];
    const writeLog = [];         // 每一次「發出」寫入（不管有沒有送達）
    let firing = false, again = false;

    function localView() {
      let t = serverTree;
      for (const op of pending) {
        if (op.kind === 'update') {
          Object.keys(op.values).forEach(k => { t = setPath(t, parts(op.path).concat(parts(k)).join('/'), resolveSV(op.values[k], clock())); });
        } else {
          t = setPath(t, op.path, resolveSV(op.value, clock()));
        }
      }
      return t;
    }

    function snapOf(tree, path) {
      const raw = getPath(tree, path);
      const val = toRead(clone(raw));
      const key = parts(path).slice(-1)[0] || null;
      return {
        key,
        val: () => clone(val),
        exists: () => raw !== null,
        child: c => snapOf(tree, parts(path).concat(parts(c)).join('/')),
      };
    }

    function fire() {
      if (!ready) return;
      if (firing) { again = true; return; }
      firing = true;
      try {
        do {
          again = false;
          const view = localView();
          for (const l of listeners.slice()) {
            const cur = stable(getPath(view, l.path));
            if (l.initial || cur !== l.last) {
              l.initial = false;
              l.last = cur;
              try { l.cb(snapOf(view, l.path)); } catch (e) { console.error('[mock-rtdb] listener error', e); }
            }
          }
        } while (again);
      } finally { firing = false; }
    }

    function fireInfo() {
      infoListeners.forEach(l => { try { l.cb({ val: () => connected, exists: () => true, key: 'connected' }); } catch (e) { console.error(e); } });
    }

    function drain() {
      while (connected && !held && queue.length) {
        const msg = queue.shift();
        send(msg);
      }
    }

    function request(msg, { pendingOp = null } = {}) {
      const rid = `${clientId}-${++ridSeq}`;
      const m = Object.assign({ rid }, msg);
      return new Promise((resolve, reject) => {
        waiting.set(rid, { resolve, reject, pendingOp });
        queue.push(m);
        drain();
      });
    }

    function write(kind, path, payload) {
      writeLog.push({ kind, path: parts(path).join('/') });
      const op = Object.assign({ kind, path: parts(path).join('/') }, payload);
      pending.push(op);
      // 真實 SDK 先把寫入交給連線，才發出本機預先事件；回呼裡再發的寫入只能排在它後面
      const p = request({ t: 'w', kind, path: op.path, value: payload.value, values: payload.values }, { pendingOp: op });
      fire();                                  // 預先回呼
      return p;
    }

    function deliver(msg) {
      if (msg.t === 'tree') { serverTree = msg.tree; ready = true; fire(); return; }
      if (msg.t === 'reply') {
        const w = waiting.get(msg.rid);
        if (!w) return;
        waiting.delete(msg.rid);
        if (w.pendingOp) {
          const i = pending.indexOf(w.pendingOp);
          if (i >= 0) pending.splice(i, 1);
          fire();                              // 確認後保留（樹已先更新）或駁回後回滾
        }
        if (msg.ok) w.resolve(msg); else {
          const err = new Error(msg.error || 'PERMISSION_DENIED');
          err.code = msg.error || 'PERMISSION_DENIED';
          err.conflict = !!msg.conflict;
          err.current = msg.current;
          w.reject(err);
        }
      }
    }

    function makeRef(path) {
      const p = parts(path).join('/');
      const ref = {
        path: p,
        get key() { return parts(p).slice(-1)[0] || null; },
        toString() { return `mock://${p}`; },
        child(c) { return makeRef(parts(p).concat(parts(c)).join('/')); },
        set(v) { return write('set', p, { value: v === undefined ? null : v }).then(() => undefined); },
        update(values) { return write('update', p, { values }).then(() => undefined); },
        remove() { return write('set', p, { value: null }).then(() => undefined); },
        push(v) {
          const id = `-M${clock().toString(36).padStart(9, '0')}${String(++keySeq).padStart(4, '0')}${clientId.replace(/[^a-z0-9]/gi, '').slice(0, 2) || 'x'}`;
          const child = makeRef(parts(p).concat(id).join('/'));
          if (v === undefined) return child;
          const pr = child.set(v);
          const thenable = { key: id, then: (a, b) => pr.then(a, b), catch: b => pr.catch(b) };
          return thenable;
        },
        once() {
          if (p === '.info/connected') return Promise.resolve({ val: () => connected, exists: () => true });
          return request({ t: 'get', path: p }).then(m => snapOf(setPath(null, p, m.value), p));
        },
        on(ev, cb) {
          if (p === '.info/connected') { infoListeners.push({ cb }); Promise.resolve().then(() => cb({ val: () => connected })); return cb; }
          if (p === '.info/serverTimeOffset') { Promise.resolve().then(() => cb({ val: () => 0 })); return cb; }
          listeners.push({ path: p, cb, last: undefined, initial: true });
          Promise.resolve().then(fire);
          return cb;
        },
        off() {
          if (p === '.info/connected') { infoListeners.length = 0; return; }
          for (let i = listeners.length - 1; i >= 0; i--) if (listeners[i].path === p) listeners.splice(i, 1);
        },
        onDisconnect() {
          const od = (action, value) => request({ t: 'od', path: p, action, value: value === undefined ? null : value }).then(() => undefined);
          return {
            set: v => od('set', v), remove: () => od('remove'),
            update: v => od('update', v), cancel: () => od('cancel'),
          };
        },
        transaction(fn, onComplete, applyLocally) {
          return new Promise((resolve, reject) => {
            let attempts = 0;
            let input = coldTx ? null : toRead(getPath(serverTree, p));
            coldTx = false;
            const attempt = () => {
              const out = fn(clone(input));
              if (out === undefined) {
                const snap = snapOf(serverTree, p);
                if (onComplete) onComplete(null, false, snap);
                resolve({ committed: false, snapshot: snap });
                return;
              }
              writeLog.push({ kind: 'tx', path: p });
              request({ t: 'tx', path: p, expected: normalize(clone(input)), value: out }).then(m => {
                const snap = snapOf(setPath(null, p, m.value), p);
                if (onComplete) onComplete(null, true, snap);
                resolve({ committed: true, snapshot: snap });
              }, err => {
                if (err.conflict && attempts++ < 25) { input = toRead(err.current); attempt(); return; }
                if (onComplete) onComplete(err, false, null);
                reject(err);
              });
            };
            attempt();
          });
        },
      };
      return ref;
    }

    const api = {
      ref: path => makeRef(path),
      deliver,
      hello: () => send({ t: 'hello' }),
      controls: {
        isConnected: () => connected,
        setOnline(on) {
          if (on === connected) return;
          connected = on;
          if (!on) { send({ t: 'offline' }); fireInfo(); return; }
          send({ t: 'online' });
          drain();                              // 先重放離線期間排隊的寫入，再通知「已連線」
          fireInfo();
        },
        hold(on) { held = on; if (!on) drain(); },
        release() { held = false; drain(); },
        coldNextTransaction() { coldTx = true; },
        pendingWrites: () => pending.map(o => ({ kind: o.kind, path: o.path })),
        listenerPaths: () => listeners.map(l => l.path),
        queuedCount: () => queue.length,
        writeLog: () => writeLog.slice(),
        clearWriteLog: () => { writeLog.length = 0; },
        localTree: () => clone(localView()),
        serverTree: () => clone(serverTree),
      },
    };
    return api;
  }

  // 提供 firebase 全域（compat 介面的最小子集）：initializeApp／apps／database()／ServerValue
  function createFirebase(client) {
    const database = () => ({ ref: path => client.ref(path || '') });
    database.ServerValue = { TIMESTAMP: { '.sv': 'timestamp' } };
    const fb = { apps: [], initializeApp(cfg) { fb.apps.push({ delete: () => Promise.resolve() }); return fb.apps[0]; }, database };
    return fb;
  }

  root.MockRtdb = { createClient, createFirebase, helpers: { normalize, toRead, getPath, setPath, resolveSV, stable, clone } };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.MockRtdb;
})(typeof window !== 'undefined' ? window : globalThis);
