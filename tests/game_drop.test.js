// 回歸：game.html handleDrop（牌庫→手牌/棄牌、Guts→攔網指定格）與堆疊 ↑↓ 重排。
// 以 vm 抽出實際函式，mock DOM/Firebase（不碰真實同步）。
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const vm = require('node:vm');
const src = fs.readFileSync(require('node:path').join(__dirname, '..', 'game.html'), 'utf8');

function extract(name) {
  let st = src.indexOf('async function ' + name + '(');
  if (st < 0) st = src.indexOf('function ' + name + '(');
  assert.ok(st >= 0, name);
  const m = { index: st };
  let i = src.indexOf('{', m.index), d = 0;
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{') d++; else if (src[j] === '}' && --d === 0) return src.slice(m.index, j + 1);
  }
}

function makeCtx(over = {}) {
  const calls = [];
  const ctx = {
    dragData: null, isSpectator: false, calls,
    L: { pile: ['a', 'b'], hand: [], name: 'me' },
    allCards: {}, zonesState: { drop: [] },
    // 再開一場的入口守衛與寫入脈絡：這個測試不涉及鎖定，一律放行
    guardAction: () => true, gx: () => ({}), cxLive: () => true,
    toast: m => calls.push(['toast', m]),
    saveUndo: () => calls.push(['undo']),
    drawCard: () => calls.push(['draw']),
    myZonesCopy() { return JSON.parse(JSON.stringify(ctx.zonesState)); },
    syncPileCount() {}, pushZones: async z => { ctx.pushed = z; },
    addLog() {}, cardState: () => '',
    document: { getElementById: () => ({}) },
    moveGutsCard: (...a) => calls.push(['guts', ...a]),
    moveCardFromStack() {}, getZoneCard: () => null, discardFromHand() {}, discardTopFromZone() {},
    moveCard() {}, placeCard() {}, showPlaceConfirm() {}, _doReturnToPile() {},
    setZoneCard: (z, n, c) => { z[n] = c; }, openStack() {}, ...over,
  };
  vm.createContext(ctx);
  vm.runInContext(extract('handleDrop') + extract('swapStackPosition'), ctx);
  return ctx;
}

test('牌庫拖到手牌 → 抽牌', async () => {
  const c = makeCtx(); c.dragData = { src: 'pile' };
  await vm.runInContext("handleDrop('hand', false)", c);
  assert.deepStrictEqual(c.calls, [['draw']]);
});

test('牌庫拖到棄牌 → 牌庫頂進棄牌，總數守恆', async () => {
  const c = makeCtx(); c.dragData = { src: 'pile' };
  await vm.runInContext("handleDrop('drop', false)", c);
  assert.deepStrictEqual(c.L.pile, ['a']);
  assert.deepStrictEqual(c.pushed.drop, ['b']);
  assert.ok(c.calls.some(x => x[0] === 'undo'));
});

test('牌庫已空 → 提示且不動作', async () => {
  const c = makeCtx(); c.L.pile = []; c.dragData = { src: 'pile' };
  await vm.runInContext("handleDrop('drop', false)", c);
  assert.deepStrictEqual(c.calls, [['toast', '牌庫已空']]);
});

test('Guts 拖到 block:2 保留完整格位', async () => {
  const c = makeCtx(); c.dragData = { src: 'guts', zoneName: 'block:0', cardData: {}, gutsImg: 'g' };
  await vm.runInContext("handleDrop('block:2', false)", c);
  assert.strictEqual(c.calls[0][4], 'block:2');
});

test('Guts 拖回同一格不動作；非攔網仍為區名', async () => {
  const c = makeCtx(); c.dragData = { src: 'guts', zoneName: 'block:1', cardData: {}, gutsImg: 'g' };
  await vm.runInContext("handleDrop('block:1', true)", c);
  assert.strictEqual(c.calls.length, 0);
  c.dragData = { src: 'guts', zoneName: 'serve', cardData: {}, gutsImg: 'g' };
  await vm.runInContext("handleDrop('attack', true)", c);
  assert.strictEqual(c.calls[0][4], 'attack');
});

test('堆疊 ↑/↓ 交換位置確實寫回', async () => {
  const c = makeCtx();
  // 顯示順序 all[0]=頂牌；儲存 {img: 頂, guts: 由下往上}
  await vm.runInContext("swapStackPosition('serve', ['t','m','b'], 1, 0)", c);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(c.pushed.serve)), { img: 'm', guts: ['b', 't'] });
});
