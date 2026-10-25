/* 對戰「再開一場／換牌組」的純邏輯（不碰 DOM、不直接碰全域 Firebase）。
 *
 * 用傳統 <script src> 載入（game.html 全站沒有模組系統），所以掛成全域 GameRematch；
 * tests/ 以 vm 載入同一份原始碼，不用另外維護一份測試副本。
 * 協議與資料佈局的取捨見 docs/game/docs/adr/0008-per-match-node-rematch.md。
 *
 * 新佈局（proto 2）：
 *   games/<room>/ctl                 房間層控制：started／activeMatch／phase／req／ready／ack
 *   games/<room>/players/<role>      身分（name／avatar／deckName／ready）
 *   games/<room>/presence/<role>     在線
 *   games/<room>/m/<matchId>/…       一場對局的全部可變資料（zones、比分、log、骰子、翻牌…）
 * 舊佈局（proto 1）全部都在 games/<room>/ 底下，沒有 ctl，不支援重開。
 */
(function (root) {
  'use strict';

  const PROTO = 2;
  const PHASE = { IDLE: 'idle', INVITING: 'inviting', APPLYING: 'applying' };
  const DECK_SIZE = 40;
  const EVENT_MAX = 8;
  // v2 房間的等待狀態用不同字串：舊版大廳只認 'waiting'，看不到也加入不了新版房
  const STATUS = { WAITING_V1: 'waiting', WAITING_V2: 'waiting2', READY: 'ready', PLAYING: 'playing', PLAYING_V2: 'playing2' };
  const LOG_DIVIDER_KEY = '!divider'; // '!' 排在 push key 開頭的 '-' 之前，分隔線永遠是這場 log 的第一行

  const otherRole = r => (r === 'host' ? 'guest' : 'host');

  // ── 一場對局的初始資料 ────────────────────────────────
  // SET 池／setCardsLeft 一律 0，雙方手動抽牌（沿用 enterGame 的開局流程）
  function newMatchData(emptyZones, { epoch = 1, requestId = null, by = null, ts = null } = {}) {
    const side = () => ({ setCardsLeft: 0, handCount: 0, zones: emptyZones() });
    const data = {
      turn: 'host',
      phase: 'serve',
      setScore: { host: 0, guest: 0 },
      players: { host: side(), guest: side() },
      meta: { epoch },
      log: {
        [LOG_DIVIDER_KEY]: {
          player: 'system',
          action: epoch > 1 ? `── 第 ${epoch} 場開始 ──` : '── 第 1 場 ──',
          timestamp: ts,
        },
      },
    };
    if (requestId) data.meta.requestId = requestId;
    if (by) data.meta.by = by;
    return data;
  }

  // ── ctl transaction 更新函式（純函式；回傳 undefined = 中止）────────
  // Firebase 的 transaction 第一次可能拿到 null（本機沒快取）、被伺服器駁回後會用真實值重跑，
  // 所以每個函式都要能對任意當前值重複呼叫，且不能有副作用。
  const phaseOf = c => (c && c.phase) || PHASE.IDLE;

  function txInvite(cur, { rid, role, now = 0 }) {
    if (!cur || cur.proto !== PROTO || !cur.started || phaseOf(cur) !== PHASE.IDLE) return undefined;
    return Object.assign({}, cur, {
      rev: (cur.rev || 0) + 1,
      phase: PHASE.INVITING,
      req: { id: rid, by: role, at: now },
      ready: { [role]: rid },
      ack: null,
    });
  }

  function txCancel(cur, { rid }) {
    if (!cur || phaseOf(cur) !== PHASE.INVITING || !cur.req || cur.req.id !== rid) return undefined;
    return Object.assign({}, cur, { rev: (cur.rev || 0) + 1, phase: PHASE.IDLE, req: null, ready: null, ack: null });
  }

  function txCommit(cur, { rid }) {
    if (!cur || phaseOf(cur) !== PHASE.INVITING || !cur.req || cur.req.id !== rid) return undefined;
    if (!cur.ready || cur.ready.host !== rid || cur.ready.guest !== rid) return undefined;
    return Object.assign({}, cur, {
      rev: (cur.rev || 0) + 1,
      phase: PHASE.APPLYING,
      prevMatch: cur.activeMatch || null,
      activeMatch: rid,
      epoch: (cur.epoch || 1) + 1,
      ready: null,
      ack: null,
    });
  }

  function txFinish(cur, { mid }) {
    if (!cur || phaseOf(cur) !== PHASE.APPLYING || cur.activeMatch !== mid) return undefined;
    if (!cur.ack || cur.ack.host !== mid || cur.ack.guest !== mid) return undefined;
    return Object.assign({}, cur, { rev: (cur.rev || 0) + 1, phase: PHASE.IDLE, req: null, ready: null, ack: null });
  }

  // 準備新場節點：已經有內容（例如已被啟用的場）就中止，不覆寫
  function txPrepare(cur, data) {
    return cur ? undefined : data;
  }

  // ── 鎖定與狀態 ───────────────────────────────────────
  function isLocked({ proto, ctl, appliedMatchId, localHold }) {
    if (localHold) return true;
    if (proto !== PROTO) return false;
    if (!ctl) return true;
    if (phaseOf(ctl) !== PHASE.IDLE) return true;
    return ctl.activeMatch !== appliedMatchId;
  }

  // 依 ctl 與本機狀態算出「現在該做什麼」。呼叫端負責執行並避免重入（mutex／hold）。
  // hold：本機正在送出的邀請 id，pending 屬於它時不能因為 ctl 還沒更新就被當成過期而丟掉
  function planRematch({ proto, ctl, role, appliedMatchId, pending, hold = null }) {
    const plan = { lock: false, commit: false, ack: false, finish: false, apply: false, recover: false, dropPending: false, unrecoverable: false, rid: null };
    if (proto !== PROTO || !ctl) return plan;
    const phase = phaseOf(ctl);
    const mismatch = ctl.activeMatch !== appliedMatchId;
    if (phase === PHASE.INVITING) {
      const rid = ctl.req && ctl.req.id;
      plan.lock = true;
      plan.rid = rid || null;
      if (rid && ctl.ready && ctl.ready.host === rid && ctl.ready.guest === rid) plan.commit = true;
      if (pending && pending.requestId !== rid && pending.requestId !== hold) plan.dropPending = true;
      if (mismatch) plan.unrecoverable = true; // 邀請中卻不是在最新一場：本機狀態對不上，沒辦法再開
    } else if (phase === PHASE.APPLYING) {
      plan.lock = true;
      plan.rid = ctl.activeMatch;
      if (mismatch) {
        if (pending && pending.requestId === ctl.activeMatch) plan.apply = true;
        else plan.recover = true;
      } else {
        if (!ctl.ack || ctl.ack[role] !== ctl.activeMatch) plan.ack = true;
        if (ctl.ack && ctl.ack.host === ctl.activeMatch && ctl.ack.guest === ctl.activeMatch) plan.finish = true;
      }
    } else {
      if (mismatch) { plan.lock = true; plan.unrecoverable = true; }
      if (pending && pending.requestId !== hold) plan.dropPending = true;
    }
    return plan;
  }

  // 重新整理／重連時，session 與遠端 ctl 的關係
  function classifyResume({ session, ctl }) {
    if (!ctl) return 'legacy';
    if (session && session.appliedMatchId === ctl.activeMatch) return 'resume';
    if (session && session.pending && session.pending.requestId === ctl.activeMatch) return 'apply-pending';
    if (phaseOf(ctl) === PHASE.APPLYING) return 'recover-pick';
    return 'unrecoverable';
  }

  // ── 牌組 ─────────────────────────────────────────────
  function expandDeck(deck) {
    const out = [];
    ((deck && deck.cards) || []).forEach(e => {
      const n = Number.isInteger(e.count) ? e.count : (e.count == null ? 1 : NaN);
      for (let i = 0; i < n; i++) out.push(e.image_file);
    });
    return out;
  }

  function validateDeck(deck, allCards) {
    const problems = [];
    const unknown = [];
    let total = 0;
    let eventCount = 0;
    ((deck && deck.cards) || []).forEach(e => {
      const n = e.count == null ? 1 : e.count;
      if (!Number.isInteger(n) || n < 1) { problems.push(`張數異常（${e.image_file}）`); return; }
      total += n;
      const card = allCards && allCards[e.image_file];
      if (!card) { if (!unknown.includes(e.image_file)) unknown.push(e.image_file); return; }
      if (card.category === 'EVENT') eventCount += n;
    });
    if (total !== DECK_SIZE) problems.push(`牌組張數 ${total} 張，應為 ${DECK_SIZE} 張`);
    if (eventCount > EVENT_MAX) problems.push(`EVENT 牌 ${eventCount} 張，上限 ${EVENT_MAX} 張`);
    if (unknown.length) problems.push(`有 ${unknown.length} 張卡圖在卡牌資料裡找不到`);
    return { ok: problems.length === 0, total, eventCount, unknown, problems };
  }

  function makeDeckSnapshot(deck) {
    return {
      id: deck.id || '',
      name: deck.name || '',
      cards: ((deck && deck.cards) || []).map(e => ({ image_file: e.image_file, count: e.count == null ? 1 : e.count })),
    };
  }

  // 沒有原始快照的舊 session：把手牌／牌庫／SET 池／場上與棄牌全部收齊，剛好 40 張且都認得才算數
  function snapshotFromCards(cards, allCards, name = '') {
    const counts = new Map();
    cards.forEach(img => counts.set(img, (counts.get(img) || 0) + 1));
    const snap = { id: '', name, cards: [...counts].map(([image_file, count]) => ({ image_file, count })) };
    return validateDeck(snap, allCards).ok ? snap : null;
  }

  // 洗牌（Fisher–Yates）。randInt(n) 回傳 0..n-1；測試可注入固定序列
  function shuffleWith(list, randInt) {
    const a = list.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = randInt(i + 1);
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function cryptoRandInt(n) {
    const buf = new Uint32Array(1);
    root.crypto.getRandomValues(buf);
    return buf[0] % n;
  }

  // 已驗證、已洗牌的待套用牌庫。驗證失敗回傳 { error }
  function buildPending({ requestId, deck, snapshot, allCards, randInt = cryptoRandInt }) {
    const snap = snapshot || makeDeckSnapshot(deck);
    const check = validateDeck(snap, allCards);
    if (!check.ok) return { error: check.problems.join('；') };
    return {
      pending: {
        requestId,
        deckId: snap.id || '',
        deckName: snap.name || '',
        snapshot: snap,
        pile: shuffleWith(expandDeck(snap), randInt),
      },
    };
  }

  // 從 localStorage 的 hv_decks 原始字串整理出候選牌組（含各自的驗證結果）
  function listCandidates(raw, allCards) {
    let decks = [];
    try { decks = JSON.parse(raw || '[]'); } catch { decks = []; }
    if (!Array.isArray(decks)) decks = [];
    return decks
      .filter(d => d && d.id !== 'dk_quick' && Array.isArray(d.cards))
      .map(d => Object.assign({ id: d.id, name: d.name || '(未命名)', deck: d }, validateDeck(d, allCards)))
      .sort((a, b) => a.name.localeCompare(b.name, 'zh-Hant'));
  }

  // ── session（localStorage）─────────────────────────────
  // 固定要保留的欄位。saveSession 每次整份重寫，漏掉任何一個就等於把它丟掉。
  const SESSION_EXTRA_KEYS = ['proto', 'appliedMatchId', 'deckSnapshot', 'pending'];

  function composeSession(core, extra) {
    const out = Object.assign({}, core);
    SESSION_EXTRA_KEYS.forEach(k => { if (extra && extra[k] !== undefined && extra[k] !== null) out[k] = extra[k]; });
    return out;
  }

  function parseSession(raw) {
    if (!raw) return null;
    try {
      const s = JSON.parse(raw);
      return s && typeof s === 'object' ? s : null;
    } catch { return null; }
  }

  // ── 視圖組合 ─────────────────────────────────────────
  // 把 ctl／身分／在線／該場節點拼回舊程式碼一直在讀的那一包 data，syncUI 以下完全不用改
  function composeView({ ctl, meta, presence, match }) {
    if (!ctl) return null;
    const m = match || {};
    const players = {};
    ['host', 'guest'].forEach(r => {
      const a = meta && meta[r];
      const b = m.players && m.players[r];
      if (a || b) players[r] = Object.assign({}, a, b);
    });
    return Object.assign({}, m, { players, presence: presence || {}, started: !!ctl.started, ctl });
  }

  // ── 寫入脈絡（ctx）──────────────────────────────────────
  // 每個「已開始的」非同步動作在入口抓一份 ctx，之後的寫入都走 cx.ref()，不再讀全域房號／場號。
  // 場一切換就 kill()：還沒送出的寫入變成 no-op；已經交給 SDK 的寫入落在舊場路徑，影響不到新場。
  function createCtx(database, { room, role, matchId = null, proto = PROTO }) {
    const cx = {
      room, role, matchId, proto,
      dead: false,
      inflight: new Set(),
      stats: { issued: 0, dropped: 0 },
      base: proto === PROTO ? `games/${room}/m/${matchId}` : `games/${room}`,
      live() { return !cx.dead; },
      kill() { cx.dead = true; },
      track(p) {
        cx.stats.issued++;
        const q = Promise.resolve(p);
        const done = () => cx.inflight.delete(q);
        cx.inflight.add(q);
        q.then(done, done);
        return p;
      },
      // 等已送出的寫入全部落定（成功或失敗）；timeoutMs 內沒完成回傳 false
      drain(timeoutMs = 4000) {
        if (!cx.inflight.size) return Promise.resolve(true);
        return new Promise(resolve => {
          let timer = null;
          const check = () => {
            if (!cx.inflight.size) { clearTimeout(timer); resolve(true); return; }
            Promise.allSettled([...cx.inflight]).then(check);
          };
          timer = setTimeout(() => resolve(false), timeoutMs);
          check();
        });
      },
      path(sub) { return sub ? `${cx.base}/${sub}` : cx.base; },
      ref(sub) {
        if (cx.dead) { cx.stats.dropped++; return inertRef(); }
        const raw = database.ref(cx.path(sub));
        return {
          key: raw.key,
          set: v => cx.track(raw.set(v)),
          update: v => cx.track(raw.update(v)),
          remove: () => cx.track(raw.remove()),
          push: v => (v === undefined ? raw.push() : cx.track(raw.push(v))),
          once: (...a) => raw.once(...a),
          on: (...a) => raw.on(...a),
          off: (...a) => raw.off(...a),
          onDisconnect: () => raw.onDisconnect(),
        };
      },
      // 預先配一個 push key（不寫入），給 rallyLoss 這種要先知道 id 的地方用
      newKey(sub) {
        if (cx.dead) return null;
        return database.ref(cx.path(sub)).push().key;
      },
    };
    return cx;
  }

  function inertRef() {
    const done = () => Promise.resolve();
    const od = { set: done, update: done, remove: done, cancel: done };
    const snap = { val: () => null, exists: () => false };
    return {
      key: null, set: done, update: done, remove: done, push: v => (v === undefined ? { key: null } : done()),
      once: () => Promise.resolve(snap), on() {}, off() {}, onDisconnect: () => od,
    };
  }

  const api = {
    PROTO, PHASE, STATUS, DECK_SIZE, EVENT_MAX, LOG_DIVIDER_KEY,
    otherRole, newMatchData,
    txInvite, txCancel, txCommit, txFinish, txPrepare,
    isLocked, planRematch, classifyResume,
    expandDeck, validateDeck, makeDeckSnapshot, snapshotFromCards, shuffleWith, buildPending, listCandidates,
    composeSession, parseSession, SESSION_EXTRA_KEYS,
    composeView, createCtx,
  };
  root.GameRematch = api;
})(typeof window !== 'undefined' ? window : globalThis);
