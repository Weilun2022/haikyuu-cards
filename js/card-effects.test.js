import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildEffectOptions, cardHasEffect } from './card-effects.js';

const card = (card_no, skill_zh) => ({ card_no, skill_zh });

test('數字型標記算特殊效果', () => {
  const c = card('A-001', '[=攻擊區]自己的角色[=佯攻(4)]');
  assert.equal(cardHasEffect(c, '佯攻'), true);
  assert.deepEqual(buildEffectOptions([c]), [{ name: '佯攻', count: 1 }]);
});

test('(N) 型（提到該效果）也算', () => {
  const c = card('A-001', '對手的[=一觸(N)]無效化');
  assert.equal(cardHasEffect(c, '一觸'), true);
});

test('兩段括號只取第一個括號前的文字當效果名', () => {
  const c = card('A-001', '[=同步多點位差攻擊(烏野)(3)]');
  assert.equal(cardHasEffect(c, '同步多點位差攻擊'), true);
  assert.deepEqual(buildEffectOptions([c]), [{ name: '同步多點位差攻擊', count: 1 }]);
});

test('不帶括號的發動時機／位置標記不算', () => {
  const c = card('A-001', '[=登場][=攻擊區][=每回合1次]抽1張卡');
  assert.deepEqual(buildEffectOptions([c]), []);
  assert.equal(cardHasEffect(c, '登場'), false);
});

test('全形方括號與全形括號也收', () => {
  const c = card('A-001', '［=封殺攔網（6）］');
  assert.equal(cardHasEffect(c, '封殺攔網'), true);
});

test('一張卡兩種效果，兩種都有、卡數各加 1', () => {
  const c = card('A-001', '對手的[=封殺攔網(N)]/[=一觸(N)]無效化');
  assert.equal(cardHasEffect(c, '封殺攔網'), true);
  assert.equal(cardHasEffect(c, '一觸'), true);
  assert.deepEqual(buildEffectOptions([c]), [
    { name: '封殺攔網', count: 1 },
    { name: '一觸', count: 1 },
  ]);
});

test('同一個卡號的多個版本只算 1', () => {
  const cards = [card('A-001', '[=佯攻(4)]'), card('A-001', '[=佯攻(4)]'), card('A-002', '[=佯攻(5)]')];
  assert.deepEqual(buildEffectOptions(cards), [{ name: '佯攻', count: 2 }]);
});

test('同一張卡同一效果出現兩次只算 1', () => {
  const c = card('A-001', '[=佯攻(4)]，之後[=佯攻(7)]');
  assert.deepEqual(buildEffectOptions([c]), [{ name: '佯攻', count: 1 }]);
});

test('排序：卡數多的在前，同數照第一次出現的先後', () => {
  const cards = [
    card('A-001', '[=二段攻擊(3)]'),
    card('A-002', '[=佯攻(4)]'),
    card('A-003', '[=一觸(2)]'),
    card('A-004', '[=一觸(2)]'),
    card('A-005', '[=佯攻(1)]'),
  ];
  assert.deepEqual(buildEffectOptions(cards), [
    { name: '佯攻', count: 2 },
    { name: '一觸', count: 2 },
    { name: '二段攻擊', count: 1 },
  ]);
});

test('skill_zh 空字串、"-"、沒有欄位時不出錯也不算', () => {
  const cards = [card('A-001', ''), card('A-002', '-'), { card_no: 'A-003' }];
  assert.deepEqual(buildEffectOptions(cards), []);
  for (const c of cards) assert.equal(cardHasEffect(c, '佯攻'), false);
});

test('內文只是純文字提到效果名、沒有標記，不算', () => {
  const c = card('A-001', '這張卡跟佯攻(4)很搭');
  assert.equal(cardHasEffect(c, '佯攻'), false);
  assert.deepEqual(buildEffectOptions([c]), []);
});

test('效果名完全相等才算，不是子字串', () => {
  const c = card('A-001', '[=封殺攔網(6)]');
  assert.equal(cardHasEffect(c, '攔網'), false);
  assert.equal(cardHasEffect(c, '攔網出界'), false);
  assert.equal(cardHasEffect(card('A-002', '[=攔網出界(2)]'), '封殺攔網'), false);
});
