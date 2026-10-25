'use strict';
// js/game-rematch.js 的純邏輯測試：ctl transaction 更新函式、狀態規劃、牌組驗證、session、寫入脈絡。
// 與 game.html 的接線（真實 listener、兩個頁面）由 tests/game-rematch-e2e.test.js 負責。
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const src = fs.readFileSync(path.join(__dirname, '..', 'js', 'game-rematch.js'), 'utf8');
const holder = {};
new Function('window', src)(holder);   // 在本 realm 執行，物件才能直接 deepStrictEqual
const GR = holder.GameRematch;

const emptyZones = () => ({ serve: null, block: [null, null, null], receive: null, toss: null, attack: null, event: [], drop: [], set: [] });

const baseCtl = (over = {}) => ({ proto: 2, rev: 1, started: true, phase: 'idle', activeMatch: 'M1', epoch: 1, ...over });

const cards = {};
for (let i = 0; i < 60; i++) cards[`c${i}.webp`] = { category: i < 50 ? 'CHARACTER' : 'EVENT' };
const mkDeck = (n, ev = 0, over = {}) => ({
  id: 'd', name: '牌組',
  cards: [
    ...Array.from({ length: n - ev }, (_, i) => ({ image_file: `c${i}.webp`, count: 1 })),
    ...Array.from({ length: ev }, (_, i) => ({ image_file: `c${50 + i}.webp`, count: 1 })),
  ],
  ...over,
});

test('txInvite：只有 started 且 idle 才能發起，並把發起者標成已準備', () => {
  const next = GR.txInvite(baseCtl(), { rid: 'R1', role: 'host', now: 5 });
  assert.equal(next.phase, 'inviting');
  assert.deepEqual(next.req, { id: 'R1', by: 'host', at: 5 });
  assert.deepEqual(next.ready, { host: 'R1' });
  assert.equal(next.rev, 2);
  assert.equal(GR.txInvite(baseCtl({ started: false }), { rid: 'R', role: 'host' }), undefined);
  assert.equal(GR.txInvite(next, { rid: 'R2', role: 'guest' }), undefined, '同時邀請：後到的中止');
  assert.equal(GR.txInvite(null, { rid: 'R', role: 'host' }), undefined, '第一次拿到 null 的快取值也要能安全中止');
  assert.equal(GR.txInvite(baseCtl({ proto: 1 }), { rid: 'R', role: 'host' }), undefined);
});

test('txInvite 會清掉上一輪殘留的 ready／ack（晚到的舊 ready 不會污染新邀請）', () => {
  const dirty = baseCtl({ ready: { guest: 'OLD' }, ack: { host: 'OLDM' } });
  const next = GR.txInvite(dirty, { rid: 'R2', role: 'host' });
  assert.deepEqual(next.ready, { host: 'R2' });
  assert.equal(next.ack, null);
});

test('txCommit：需要 requestId 相符且雙方 ready 的值都等於它', () => {
  const inv = GR.txInvite(baseCtl(), { rid: 'R1', role: 'host' });
  assert.equal(GR.txCommit(inv, { rid: 'R1' }), undefined, '只有發起者 ready');
  const oneStale = { ...inv, ready: { host: 'R1', guest: 'OLD' } };
  assert.equal(GR.txCommit(oneStale, { rid: 'R1' }), undefined, '舊邀請的 ready 不算數');
  const both = { ...inv, ready: { host: 'R1', guest: 'R1' } };
  const done = GR.txCommit(both, { rid: 'R1' });
  assert.equal(done.phase, 'applying');
  assert.equal(done.activeMatch, 'R1');
  assert.equal(done.prevMatch, 'M1');
  assert.equal(done.epoch, 2);
  assert.equal(done.ready, null);
  assert.equal(GR.txCommit(both, { rid: 'OTHER' }), undefined);
  assert.equal(GR.txCommit(done, { rid: 'R1' }), undefined, '已經提交過不能再提交（冪等）');
});

test('取消與提交互斥：先到者贏，後到者的 transaction 在新值上中止', () => {
  const both = { ...GR.txInvite(baseCtl(), { rid: 'R1', role: 'host' }), ready: { host: 'R1', guest: 'R1' } };
  // 取消先到
  const cancelled = GR.txCancel(both, { rid: 'R1' });
  assert.equal(cancelled.phase, 'idle');
  assert.equal(cancelled.req, null);
  assert.equal(GR.txCommit(cancelled, { rid: 'R1' }), undefined);
  // 提交先到
  const committed = GR.txCommit(both, { rid: 'R1' });
  assert.equal(GR.txCancel(committed, { rid: 'R1' }), undefined, '提交後不能取消');
});

test('txCancel 只認 requestId：舊邀請的取消不會砍到新邀請', () => {
  const inv2 = GR.txInvite(baseCtl(), { rid: 'R2', role: 'guest' });
  assert.equal(GR.txCancel(inv2, { rid: 'R1' }), undefined);
  assert.equal(GR.txCancel(baseCtl(), { rid: 'R1' }), undefined);
});

test('txFinish：雙方 ack 都等於 activeMatch 才回到 idle', () => {
  const applying = GR.txCommit({ ...GR.txInvite(baseCtl(), { rid: 'R1', role: 'host' }), ready: { host: 'R1', guest: 'R1' } }, { rid: 'R1' });
  assert.equal(GR.txFinish(applying, { mid: 'R1' }), undefined);
  assert.equal(GR.txFinish({ ...applying, ack: { host: 'R1' } }, { mid: 'R1' }), undefined);
  assert.equal(GR.txFinish({ ...applying, ack: { host: 'R1', guest: 'OLD' } }, { mid: 'R1' }), undefined, '舊場的 ack 不算數');
  const fin = GR.txFinish({ ...applying, ack: { host: 'R1', guest: 'R1' } }, { mid: 'R1' });
  assert.equal(fin.phase, 'idle');
  assert.equal(fin.req, null);
  assert.equal(fin.ack, null);
  assert.equal(fin.activeMatch, 'R1');
});

test('每個改變階段的 transaction 都讓 rev 遞增（供本機判斷 transaction 結果是否比快照新）', () => {
  const a = GR.txInvite(baseCtl(), { rid: 'R', role: 'host' });
  const b = GR.txCancel(a, { rid: 'R' });
  const c = GR.txCommit({ ...a, ready: { host: 'R', guest: 'R' } }, { rid: 'R' });
  const d = GR.txFinish({ ...c, ack: { host: 'R', guest: 'R' } }, { mid: 'R' });
  assert.deepEqual([a.rev, b.rev, c.rev, d.rev], [2, 3, 3, 4]);
});

test('txPrepare：新場節點已有內容就中止，絕不覆寫已啟用的場', () => {
  const data = { turn: 'host' };
  assert.equal(GR.txPrepare(null, data), data);
  assert.equal(GR.txPrepare({ turn: 'guest' }, data), undefined);
});

test('transaction 更新函式不修改傳入的值（Firebase 會用不同的值重跑）', () => {
  const cur = baseCtl();
  const frozen = JSON.stringify(cur);
  GR.txInvite(cur, { rid: 'R', role: 'host' });
  GR.txCancel(cur, { rid: 'R' });
  GR.txCommit(cur, { rid: 'R' });
  GR.txFinish(cur, { mid: 'R' });
  assert.equal(JSON.stringify(cur), frozen);
});

test('newMatchData：比分、SET 池、setCardsLeft 全 0，盤面清空，log 以分隔線開頭', () => {
  const d = GR.newMatchData(emptyZones, { epoch: 3, requestId: 'R', by: 'guest', ts: 9 });
  assert.deepEqual(d.setScore, { host: 0, guest: 0 });
  assert.equal(d.players.host.setCardsLeft, 0);
  assert.equal(d.players.guest.setCardsLeft, 0);
  assert.deepEqual(d.players.host.zones, emptyZones());
  assert.equal(d.turn, 'host');
  assert.equal(d.log[GR.LOG_DIVIDER_KEY].action, '── 第 3 場開始 ──');
  assert.equal(d.log[GR.LOG_DIVIDER_KEY].player, 'system');
  assert.equal(d.meta.requestId, 'R');
  assert.ok(!('rallyLoss' in d) && !('roundReset' in d) && !('diceRoll' in d), '輸球事件／重置游標／骰子不跨場');
  assert.ok(GR.LOG_DIVIDER_KEY < '-M', '分隔線 key 必須排在 push key 之前');
});

test('isLocked：本機樂觀鎖、邀請中、套用中、場號對不上都鎖；舊版房間不鎖', () => {
  const k = { proto: 2, appliedMatchId: 'M1', localHold: false };
  assert.equal(GR.isLocked({ ...k, ctl: baseCtl() }), false);
  assert.equal(GR.isLocked({ ...k, ctl: null }), true, '還沒收到 ctl 前先鎖');
  assert.equal(GR.isLocked({ ...k, ctl: baseCtl({ phase: 'inviting' }) }), true);
  assert.equal(GR.isLocked({ ...k, ctl: baseCtl({ phase: 'applying' }) }), true);
  assert.equal(GR.isLocked({ ...k, ctl: baseCtl({ activeMatch: 'M2' }) }), true, '遠端已換場、本機還沒套用');
  assert.equal(GR.isLocked({ ...k, ctl: baseCtl(), localHold: true }), true, '送出中就鎖，不等伺服器回應');
  assert.equal(GR.isLocked({ proto: 1, ctl: null, appliedMatchId: null, localHold: false }), false);
});

test('planRematch：各階段該做的事', () => {
  const me = { proto: 2, role: 'guest', appliedMatchId: 'M1', pending: null };
  const inv = (ready) => baseCtl({ phase: 'inviting', req: { id: 'R', by: 'host' }, ready });
  assert.equal(GR.planRematch({ ...me, ctl: baseCtl() }).lock, false);
  assert.equal(GR.planRematch({ ...me, ctl: inv({ host: 'R' }) }).lock, true);
  assert.equal(GR.planRematch({ ...me, ctl: inv({ host: 'R' }) }).commit, false);
  assert.equal(GR.planRematch({ ...me, ctl: inv({ host: 'R', guest: 'R' }) }).commit, true);
  assert.equal(GR.planRematch({ ...me, ctl: inv({ host: 'R', guest: 'OLD' }) }).commit, false);

  const applying = baseCtl({ phase: 'applying', activeMatch: 'R', req: { id: 'R', by: 'host' } });
  const needApply = GR.planRematch({ ...me, ctl: applying, pending: { requestId: 'R' } });
  assert.equal(needApply.apply, true);
  assert.equal(GR.planRematch({ ...me, ctl: applying, pending: null }).recover, true, '缺 pending → 走恢復選牌，不能永久鎖住');
  assert.equal(GR.planRematch({ ...me, ctl: applying, pending: { requestId: 'OTHER' } }).recover, true);
  const applied = { ...me, appliedMatchId: 'R' };
  assert.equal(GR.planRematch({ ...applied, ctl: applying }).ack, true);
  assert.equal(GR.planRematch({ ...applied, ctl: { ...applying, ack: { guest: 'R' } } }).ack, false);
  assert.equal(GR.planRematch({ ...applied, ctl: { ...applying, ack: { guest: 'R', host: 'R' } } }).finish, true);
  assert.equal(GR.planRematch({ ...applied, ctl: { ...applying, ack: { host: 'R' } } }).finish, false);
});

test('planRematch：過期的 pending 會被丟掉，但正在送出的邀請不會被誤判成過期', () => {
  const me = { proto: 2, role: 'host', appliedMatchId: 'M1' };
  const idle = baseCtl();
  assert.equal(GR.planRematch({ ...me, ctl: idle, pending: { requestId: 'OLD' } }).dropPending, true);
  assert.equal(GR.planRematch({ ...me, ctl: idle, pending: { requestId: 'NEW' }, hold: 'NEW' }).dropPending, false,
    '剛存好 pending、邀請還沒進 ctl：不能被丟掉');
  const inv = baseCtl({ phase: 'inviting', req: { id: 'R2', by: 'guest' } });
  assert.equal(GR.planRematch({ ...me, ctl: inv, pending: { requestId: 'R1' } }).dropPending, true, '邀請已經換了一個');
  assert.equal(GR.planRematch({ ...me, ctl: inv, pending: { requestId: 'R2' } }).dropPending, false);
});

test('planRematch：本機與房間對不上而又不在套用流程中 → 無法恢復', () => {
  const p = GR.planRematch({ proto: 2, role: 'host', appliedMatchId: 'OLD', pending: null, ctl: baseCtl() });
  assert.equal(p.unrecoverable, true);
  assert.equal(p.lock, true);
});

test('planRematch：舊版房間（proto 1）完全不啟動任何流程', () => {
  const p = GR.planRematch({ proto: 1, ctl: null, role: 'host', appliedMatchId: null, pending: null });
  assert.deepEqual(Object.values({ ...p, rid: null }).filter(Boolean), []);
});

test('classifyResume：重連時 appliedMatchId 與遠端比對，不盲目對齊', () => {
  const ctl = baseCtl({ activeMatch: 'M2' });
  assert.equal(GR.classifyResume({ session: { appliedMatchId: 'M2' }, ctl }), 'resume');
  assert.equal(GR.classifyResume({ session: { appliedMatchId: 'M1', pending: { requestId: 'M2' } }, ctl }), 'apply-pending');
  assert.equal(GR.classifyResume({ session: { appliedMatchId: 'M1' }, ctl: { ...ctl, phase: 'applying' } }), 'recover-pick');
  assert.equal(GR.classifyResume({ session: { appliedMatchId: 'M1' }, ctl }), 'unrecoverable',
    '已經打到新場中途、本機又沒有那場的資料：還原舊手牌會把上一場的牌帶進來，必須拒絕');
  assert.equal(GR.classifyResume({ session: { appliedMatchId: 'M1', pending: { requestId: 'OTHER' } }, ctl: { ...ctl, phase: 'applying' } }), 'recover-pick');
  assert.equal(GR.classifyResume({ session: {}, ctl: null }), 'legacy');
});

test('validateDeck：40 張、EVENT ≤ 8、卡圖都認得', () => {
  assert.equal(GR.validateDeck(mkDeck(40, 8), cards).ok, true);
  assert.equal(GR.validateDeck(mkDeck(39), cards).ok, false);
  assert.equal(GR.validateDeck(mkDeck(41), cards).ok, false);
  const nine = GR.validateDeck(mkDeck(40, 9), cards);
  assert.equal(nine.ok, false);
  assert.match(nine.problems.join(), /EVENT/);
  const unknown = mkDeck(40);
  unknown.cards[0].image_file = 'nope.webp';
  const r = GR.validateDeck(unknown, cards);
  assert.equal(r.ok, false);
  assert.deepEqual(r.unknown, ['nope.webp']);
  const counted = { cards: [{ image_file: 'c0.webp', count: 4 }, ...Array.from({ length: 36 }, (_, i) => ({ image_file: `c${i + 1}.webp`, count: 1 }))] };
  assert.equal(GR.validateDeck(counted, cards).ok, true, 'count 欄位要算進張數');
  assert.equal(GR.validateDeck({ cards: [{ image_file: 'c0.webp', count: 0 }] }, cards).ok, false);
});

test('buildPending：洗牌只發生一次且是排列（40 張守恆）；驗證不過就不產生', () => {
  let calls = 0;
  const rand = n => { calls++; return (calls * 7) % n; };
  const { pending } = GR.buildPending({ requestId: 'R', deck: mkDeck(40, 8), allCards: cards, randInt: rand });
  assert.equal(pending.requestId, 'R');
  assert.equal(pending.pile.length, 40);
  assert.deepEqual([...pending.pile].sort(), GR.expandDeck(mkDeck(40, 8)).sort());
  assert.equal(calls, 39, 'Fisher–Yates 每個位置抽一次');
  assert.equal(pending.snapshot.cards.length, 40);
  assert.ok(GR.buildPending({ requestId: 'R', deck: mkDeck(39), allCards: cards }).error);
});

test('snapshotFromCards：舊 session 從所有本機牌收齊，剛好 40 張才提供沿用', () => {
  const all = GR.expandDeck(mkDeck(40, 8));
  const snap = GR.snapshotFromCards(all, cards, 'X');
  assert.equal(GR.validateDeck(snap, cards).ok, true);
  assert.equal(GR.snapshotFromCards(all.slice(1), cards), null);
  assert.equal(GR.snapshotFromCards([...all, 'c1.webp'], cards), null);
});

test('listCandidates：忽略快速牌組，排序，每副附驗證結果', () => {
  const raw = JSON.stringify([
    { id: 'dk_quick', name: 'Q', cards: [] },
    { id: 'b', name: 'B牌', cards: mkDeck(40, 8).cards },
    { id: 'a', name: 'A牌', cards: mkDeck(39).cards },
  ]);
  const list = GR.listCandidates(raw, cards);
  assert.deepEqual(list.map(c => c.id), ['a', 'b']);
  assert.equal(list[0].ok, false);
  assert.equal(list[1].ok, true);
  assert.deepEqual(GR.listCandidates('壞掉的 json', cards), []);
  assert.deepEqual(GR.listCandidates(null, cards), []);
});

test('composeSession：整份重寫時再開一場欄位一定帶著；空值不寫入', () => {
  const core = { roomId: '1', hand: [] };
  const s = GR.composeSession(core, { proto: 2, appliedMatchId: 'M', deckSnapshot: { cards: [] }, pending: { requestId: 'R' } });
  assert.equal(s.appliedMatchId, 'M');
  assert.deepEqual(s.pending, { requestId: 'R' });
  const s2 = GR.composeSession(core, { proto: 2, appliedMatchId: 'M', deckSnapshot: null, pending: null });
  assert.ok(!('pending' in s2) && !('deckSnapshot' in s2));
  assert.equal(GR.parseSession('{'), null);
  assert.equal(GR.parseSession(null), null);
  assert.deepEqual(GR.parseSession('{"a":1}'), { a: 1 });
});

test('composeView：把 ctl／身分／在線／該場節點拼成 syncUI 讀的那一包', () => {
  const v = GR.composeView({
    ctl: baseCtl(),
    meta: { host: { name: '甲', deckName: 'A' }, guest: null },
    presence: { host: true },
    match: { turn: 'host', players: { host: { zones: 1, handCount: 2 }, guest: { handCount: 0 } } },
  });
  assert.equal(v.started, true);
  assert.equal(v.turn, 'host');
  assert.deepEqual(v.players.host, { name: '甲', deckName: 'A', zones: 1, handCount: 2 });
  assert.deepEqual(v.players.guest, { handCount: 0 });
  assert.deepEqual(v.presence, { host: true });
  assert.equal(GR.composeView({ ctl: null, meta: {}, presence: {}, match: {} }), null);
  const v2 = GR.composeView({ ctl: baseCtl(), meta: {}, presence: null, match: null });
  assert.deepEqual(v2.players, {});
  assert.deepEqual(v2.presence, {});
});

function fakeDb() {
  const writes = [];
  const mk = p => ({
    key: p.split('/').pop(),
    set: v => { writes.push(['set', p, v]); return Promise.resolve(); },
    update: v => { writes.push(['update', p, v]); return Promise.resolve(); },
    remove: () => { writes.push(['remove', p]); return Promise.resolve(); },
    push: v => { writes.push(['push', p, v]); return Object.assign(Promise.resolve(), { key: '-Kpush' }); },
    once: () => Promise.resolve({ val: () => 1, exists: () => true }),
    on() {}, off() {}, onDisconnect: () => ({ remove() {}, set() {}, cancel() {} }),
  });
  return { writes, ref: p => (p === undefined ? mk('') : mk(p)) };
}

test('createCtx：新版寫入路徑含場號，舊版維持根路徑', () => {
  const db = fakeDb();
  const v2 = GR.createCtx(db, { room: '1234', role: 'host', matchId: 'M1', proto: 2 });
  v2.ref('players/host/zones').set(1);
  v2.ref().update({ turn: 'guest' });
  const v1 = GR.createCtx(db, { room: '1234', role: 'host', matchId: null, proto: 1 });
  v1.ref('players/host/zones').set(2);
  assert.deepEqual(db.writes, [
    ['set', 'games/1234/m/M1/players/host/zones', 1],
    ['update', 'games/1234/m/M1', { turn: 'guest' }],
    ['set', 'games/1234/players/host/zones', 2],
  ]);
});

test('createCtx.kill：尚未送出的寫入變成 no-op，並被計數', async () => {
  const db = fakeDb();
  const cx = GR.createCtx(db, { room: '1', role: 'host', matchId: 'M1', proto: 2 });
  const stale = cx;                                   // 非同步動作入口抓的脈絡
  cx.kill();
  await stale.ref('players/host/zones').set(1);
  await stale.ref('log').push({ a: 1 });
  await stale.ref().update({ x: 1 });
  await stale.ref('a').remove();
  const snap = await stale.ref('a').once('value');
  assert.equal(snap.exists(), false);
  assert.equal(db.writes.length, 0, '死掉的脈絡不能讓任何寫入到達 SDK');
  assert.equal(stale.stats.dropped, 5);
  assert.equal(stale.newKey('rallyLoss'), null);
});

test('createCtx.drain：等已送出的寫入落定；逾時回傳 false', async () => {
  let release;
  const slow = new Promise(r => { release = r; });
  const db = { ref: () => ({ set: () => slow, key: 'k' }) };
  const cx = GR.createCtx(db, { room: '1', role: 'host', matchId: 'M', proto: 2 });
  cx.ref('a').set(1);
  assert.equal(cx.inflight.size, 1);
  assert.equal(await cx.drain(30), false);
  release();
  assert.equal(await cx.drain(200), true);
  assert.equal(cx.inflight.size, 0);
  // 失敗的寫入也算落定
  const failing = { ref: () => ({ set: () => Promise.reject(new Error('x')), key: 'k' }) };
  const cx2 = GR.createCtx(failing, { room: '1', role: 'host', matchId: 'M', proto: 2 });
  cx2.ref('a').set(1).catch(() => {});
  assert.equal(await cx2.drain(200), true);
});
