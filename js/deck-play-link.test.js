import { test } from 'node:test';
import assert from 'node:assert/strict';
import { deckPlayStatus, deckPlayUrl } from './deck-play-link.js';

test('deckPlayStatus：剛好 40 張、事件卡 8 張可以帶去對練台', () => {
  const s = deckPlayStatus({ total: 40, events: 8 });
  assert.equal(s.ready, true);
  assert.equal(s.label, '🏐 對練 ↗');
});

test('deckPlayStatus：未滿 40 張不能出發，標示還差幾張', () => {
  const s = deckPlayStatus({ total: 33, events: 2 });
  assert.equal(s.ready, false);
  assert.equal(s.label, '還差 7 張');
});

test('deckPlayStatus：超過 40 張也不能出發（對練台要剛好 40 張），標示多幾張', () => {
  const s = deckPlayStatus({ total: 43, events: 2 });
  assert.equal(s.ready, false);
  assert.equal(s.label, '多 3 張');
});

test('deckPlayStatus：40 張但事件卡超過 8 張不能出發，標示事件卡多幾張', () => {
  const s = deckPlayStatus({ total: 40, events: 10 });
  assert.equal(s.ready, false);
  assert.equal(s.label, '事件卡多 2 張');
});

test('deckPlayStatus：張數跟事件卡都不合格時，標籤先講張數，說明把兩個門檻跟目前數字都列出來', () => {
  const s = deckPlayStatus({ total: 35, events: 10 });
  assert.equal(s.ready, false);
  assert.equal(s.label, '還差 5 張');
  assert.equal(s.reason, '對練台需要剛好 40 張、事件卡最多 8 張（目前 35 張，事件卡 10 張）');
});

test('deckPlayStatus：可以出發時，說明標示會另開外部網站', () => {
  const s = deckPlayStatus({ total: 40, events: 3 });
  assert.equal(s.reason, '用這副牌到 BREAK 對練台跟 AI 對練（另開外部網站 haikyuu-playmat.web.app）');
});

test('deckPlayUrl：分享碼原樣接在對練台固定網址的 deck 參數後面', () => {
  assert.equal(deckPlayUrl('N4Ig-abc_123'), 'https://haikyuu-playmat.web.app/break-v9.5/?deck=N4Ig-abc_123');
});
