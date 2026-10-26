'use strict';
// 掃描 game.html 原始碼的靜態檢查。這類測試保護的是「架構事實」而不是某個輸入輸出：
//  1. 場內資料（zones、比分、log、骰子…）的寫入一律走 ctx（games/<room>/m/<matchId>/…），
//     原始碼裡不能再出現手寫的 games/${roomId}/<場內欄位> 路徑——那會繞過換場後的隔離。
//  2. 每個會動牌或寫 Firebase 的函式，要嘛開頭過 guardAction()，要嘛明確列在下面的白名單並說明為什麼可以不守衛。
//     新增這類函式卻忘了守衛時，這個測試會失敗並點名。
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const src = fs.readFileSync(path.join(__dirname, '..', 'game.html'), 'utf8').replace(/\r\n/g, '\n');
const lines = src.split('\n');

function topLevelFunctions() {
  const fns = [];
  for (let i = 0; i < lines.length; i++) {
    const m = /^(?:async )?function (\w+)\(/.exec(lines[i]);
    if (!m) continue;
    let end = i;
    const open = (lines[i].match(/\{/g) || []).length;
    const close = (lines[i].match(/\}/g) || []).length;
    if (open === 0 || open !== close) {
      for (end = i + 1; end < lines.length && lines[end] !== '}'; end++);
    }
    fns.push({ name: m[1], line: i + 1, body: lines.slice(i, end + 1).join('\n') });
  }
  return fns;
}
const stripComments = b => b.replace(/\/\*[\s\S]*?\*\//g, '').split('\n').map(l => l.replace(/(^|\s)\/\/.*$/, '$1')).join('\n');

test('抓得到足夠多的函式（確認這個掃描器沒有失靈）', () => {
  const fns = topLevelFunctions();
  assert.ok(fns.length > 200, `只抓到 ${fns.length} 個`);
  for (const n of ['placeCard', 'endTurn', 'applyPendingMatch', 'guardAction', 'declareLost']) {
    assert.ok(fns.some(f => f.name === n), n);
  }
});

test('場內資料的路徑不能手寫成 games/${…}/<場內欄位>，必須走 ctx', () => {
  const matchFields = [
    'players/\\$\\{[^}]+\\}/(zones|handCount|pileCount|setCardsLeft)', 'scores', 'scoreModes', 'counterDelta', 'setScore',
    'turn', 'phase', 'currentAction', 'atkAlert', 'roundReset', 'rallyLoss', 'diceRoll', 'peekNotif', 'peekReveal', 'log',
  ];
  const re = new RegExp('games/\\$\\{[^}]+\\}/(' + matchFields.join('|') + ')\\b');
  const offenders = [];
  lines.forEach((l, i) => { if (re.test(l) && /(db\.ref|updates\[|\.ref\()/.test(l)) offenders.push(`${i + 1}: ${l.trim()}`); });
  assert.deepEqual(offenders, [], '這些行繞過了 ctx，換場後會寫到錯的場');
});

test('只有房間層級的路徑可以用 db.ref(games/…) 直接寫：presence、ctl、players 身分、整個房間', () => {
  const allowed = [
    /games\/\$\{[^}]+\}\/presence/,
    /games\/\$\{[^}]+\}\/ctl/,
    /games\/\$\{[^}]+\}\/players\b/,                          // 身分（name／avatar／deckName／ready）；場內欄位由上一個測試擋下
    /games\/\$\{[^}]+\}\/m\/\$\{(rid|id)\}/,                   // 新場節點的準備與（確定沒人引用後的）清理
    /games\/\$\{[^}]+\}\/m`/,                                  // 預先配第一場的 push key
    /games\/\$\{(id|roomId|r\.id|sess\.roomId|cx\.room|room)\}`/, // 整個房間：建立、刪除、舊版讀取
    /games\/\$\{[^}]+\}\/\$\{path\}/,                          // 掛 ctl／players／presence 監聽
  ];
  const offenders = [];
  lines.forEach((l, i) => {
    if (!/db\.ref\(`games\//.test(l)) return;
    if (!allowed.some(a => a.test(l))) offenders.push(`${i + 1}: ${l.trim()}`);
  });
  assert.deepEqual(offenders, []);
});

// ── 守衛覆蓋 ────────────────────────────────────────────────
// 不需要守衛的函式與理由。新增函式若有動牌／寫入的特徵又不在這裡，測試會失敗。
const NO_GUARD = {
  // 進房、離房、重連、監聽：房間生命週期，不是對局中的玩家動作
  lifecycle: ['startFirebase', 'listenRooms', 'createRoom', 'joinRoom', 'spectateRoom', 'leaveRoom', 'cleanupRoom', 'readRoomHead', 'readMatchHead',
    'rejoinRoom', 'listenGame', 'listenGameLegacy', 'attachMatchListener', '_startPresenceWatch', 'startGame', 'enterGame', 'handlePresenceChange',
    // 大廳：監聽其他房間的 presence、清除過期的其他房間（自己所在的房間會被略過），不碰本機牌組或場內資料
    'syncLobbyWatches', 'reapRoom'],
  // 再開一場自己的機制：必須在鎖定期間運作
  rematch: ['ctlRef', 'touchRoomLease', 'sendReady', 'commitRematch', 'sweepPreparedMatches', 'applyPendingMatch', 'resetLocalForNewMatch', 'sendAck'],
  // 只會從已守衛的入口，或對手事件（重置本局、輸一球）呼叫；寫入都走呼叫端抓好的 ctx，換場後自動變成 no-op
  helpers: ['performLocalRoundCollect', 'resetMyRoundScoreState', 'syncScoreToBase', 'resetCounterDelta', '_checkAndClearAtkAlert',
    'pushZones', 'writePileCount', 'writeHandCount', 'addLog', '_peekRef', 'drawFromPile', 'closePeek', 'performRallyLoss'],
};

test('每個會動牌或寫 Firebase 的函式都過 guardAction()，或明確列在白名單', () => {
  const sig = [
    /\bL\.hand\.(push|splice|unshift|pop)\(/, /\bL\.pile\.(push|splice|unshift|pop)\(/, /\bL\.setPool\.(push|pop|splice)\(/,
    /\bL\.(hand|pile|setPool)\s*=[^=]/, /\bpushZones\(/, /\b(cx|gx\(\))\.ref\(/, /\bdb\.ref\(/,
  ];
  const whitelisted = new Set(Object.values(NO_GUARD).flat());
  const offenders = [];
  for (const f of topLevelFunctions()) {
    const body = stripComments(f.body);
    if (!sig.some(r => r.test(body))) continue;
    if (/guardAction\(\)/.test(body) || whitelisted.has(f.name)) continue;
    offenders.push(`${f.name} (game.html:${f.line})`);
  }
  assert.deepEqual(offenders, [], '新增的這些函式會改牌或寫入，卻沒有過 guardAction()');
});

test('白名單裡的函式都還存在（避免改名後白名單變成擺設）', () => {
  const names = new Set(topLevelFunctions().map(f => f.name));
  const missing = Object.values(NO_GUARD).flat().filter(n => !names.has(n));
  assert.deepEqual(missing, []);
});

test('守衛放在函式開頭附近，且在任何 await 之前', () => {
  const late = [];
  for (const f of topLevelFunctions()) {
    const body = stripComments(f.body);
    const g = body.indexOf('guardAction()');
    if (g < 0) continue;
    const aw = body.indexOf('await ');
    if (aw >= 0 && aw < g) late.push(f.name);
  }
  assert.deepEqual(late, []);
});

test('handleDrop 先清掉 dragData 才過守衛（鎖定時不留下殘存的拖放狀態）', () => {
  const f = topLevelFunctions().find(x => x.name === 'handleDrop');
  const a = f.body.indexOf('dragData = null');
  const b = f.body.indexOf('guardAction()');
  assert.ok(a > 0 && b > a);
});

test('listenRooms 的清理與大廳列表認得新版的等待狀態，並維持 playing 的 4 小時語意', () => {
  assert.match(src, /isWaitingStatus\s*=\s*s\s*=>\s*s === 'waiting' \|\| s === GR\.STATUS\.WAITING_V2/);
  assert.match(src, /const roomStale = \(r\.status === 'playing'\) \? STALE_MS : WAITING_STALE_MS/);
});

test('過期清理只用 transaction（墓碑 → 驗身分刪 games → 驗墓碑刪 rooms），續租遇到墓碑中止', () => {
  const fns = topLevelFunctions();
  const reap = stripComments(fns.find(f => f.name === 'reapRoom').body);
  assert.doesNotMatch(reap, /\.(remove|set|update)\(/, '清理不能用舊快照直接寫入／刪除');
  const order = ['db.ref(`rooms/${id}`).transaction', 'db.ref(`games/${id}`).transaction', 'db.ref(`rooms/${id}`).transaction'];
  let at = -1;
  for (const s of order) { at = reap.indexOf(s, at + 1); assert.ok(at >= 0, s); }
  assert.match(reap, /gamesMatchTomb\(cur, tomb\)/);
  assert.doesNotMatch(stripComments(fns.find(f => f.name === 'gamesMatchTomb').body) + reap, /\|\| null\) ===/, '缺值不能當成身分相等');
  assert.match(fns.find(f => f.name === 'touchRoomLease').body, /cur\.status !== ROOM_REAPING/);
  const sweep = stripComments(fns.find(f => f.name === 'lobbySweep').body);
  assert.doesNotMatch(sweep, /\.remove\(\)/);
});

test('離房與房間消失都走 teardownRoomState（脈絡一定被 kill，不留下可寫入的舊脈絡）', () => {
  const fns = topLevelFunctions();
  for (const n of ['leaveRoom', 'handleGameNodeGone']) {
    assert.match(fns.find(f => f.name === n).body, /teardownRoomState\(\)/, n);
  }
  assert.match(fns.find(f => f.name === 'handlePresenceChange').body, /teardownRoomState\(\)/, '雙方離線 60 秒的清房也要 kill 脈絡');
  const teardown = fns.find(f => f.name === 'teardownRoomState').body;
  assert.match(teardown, /_gctx\.kill\(\)/);
  assert.match(teardown, /detachGameListeners\(\)/);
});
