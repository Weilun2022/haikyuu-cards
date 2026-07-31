import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildSuggestions } from './card-name-suggest.js';
import { CARD_FIXTURES } from './card-fixtures.js';

test('單一命中：只比對到一張卡時回傳一筆建議', () => {
  const result = buildSuggestions(CARD_FIXTURES, '日向');
  assert.deepEqual(result, ['日向翔陽']);
});

test('多個命中：不同角色都比對到時各自回傳', () => {
  const cards = [
    { name: '日向 翔陽', name_zh: '日向翔陽' },
    { name: '影山 飛雄', name_zh: '影山飛雄' },
    { name: '及川 徹', name_zh: '及川徹' },
  ];
  const result = buildSuggestions(cards, '飛雄');
  assert.deepEqual(result, ['影山飛雄']);
});

test('輸入框空字串時不回傳全部卡片', () => {
  const cards = [{ name: '日向 翔陽', name_zh: '日向翔陽' }];
  assert.deepEqual(buildSuggestions(cards, ''), []);
});

test('同名不同版本（不同 card_no、相同 name_zh）正確去重成一筆', () => {
  const result = buildSuggestions(CARD_FIXTURES, '侑');
  assert.deepEqual(result, ['宮侑']);
});

test('含全形/半形空白差異的名字正確視為同一筆，且用有空格的查詢字也能命中', () => {
  const withHalfWidthSpace = buildSuggestions(CARD_FIXTURES, '宮 侑');
  const withFullWidthSpace = buildSuggestions(CARD_FIXTURES, '宮　侑');
  const withoutSpace = buildSuggestions(CARD_FIXTURES, '宮侑');
  assert.deepEqual(withHalfWidthSpace, ['宮侑']);
  assert.deepEqual(withFullWidthSpace, ['宮侑']);
  assert.deepEqual(withoutSpace, ['宮侑']);
});

test('查無符合結果時回傳空陣列', () => {
  const result = buildSuggestions(CARD_FIXTURES, '完全不相關的亂碼名字');
  assert.deepEqual(result, []);
});

test('排序結果依 name_zh 字元順序（不受卡片輸入順序影響）', () => {
  const cards = [
    { name: '宮 治', name_zh: '宮治' },
    { name: '宮 侑', name_zh: '宮侑' },
  ];
  // 卡片陣列刻意讓「宮治」排在「宮侑」前面，驗證輸出順序是重新排序過的，
  // 不是直接沿用輸入順序。
  const result = buildSuggestions(cards, '宮');
  assert.deepEqual(result, ['宮侑', '宮治']);
});

test('只比對 name/name_zh，不比對 school 等其他欄位', () => {
  const result = buildSuggestions(CARD_FIXTURES, '烏野');
  assert.deepEqual(result, []);
});

test('沒有 name_zh 的卡片即使 name 命中也不產生建議（沒有東西可以填回搜尋框）', () => {
  const cards = [{ name: '日向 翔陽', name_zh: '' }];
  assert.deepEqual(buildSuggestions(cards, '日向'), []);
});
