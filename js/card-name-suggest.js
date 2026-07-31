// 卡名搜尋建議：不碰 DOM 的純函式，見 docs/adr/0005。

/**
 * 給定卡片陣列與目前輸入文字，算出去重、依 name_zh 排序後的卡名建議清單。
 * 只比對 name（日文原文）與 name_zh（中文譯名），不含技能文字/卡號等其他欄位。
 * 去重鍵是 name_zh；比對與去重都先用「去除空白後比對」，讓全形/半形空格
 * 差異的同名版本被視為同一筆。
 *
 * @param {Array<{name?: string, name_zh?: string}>} cards
 * @param {string} query
 * @returns {string[]}
 */
export function buildSuggestions(cards, query) {
  const normalizedQuery = stripSpaces(query);
  if (!normalizedQuery) return [];

  const suggestionByKey = new Map();
  for (const card of cards) {
    const nameZh = card.name_zh || '';
    const name = card.name || '';
    const normalizedNameZh = stripSpaces(nameZh);
    const isMatch =
      stripSpaces(name).includes(normalizedQuery) ||
      normalizedNameZh.includes(normalizedQuery);
    if (!isMatch) continue;

    if (!suggestionByKey.has(normalizedNameZh)) {
      suggestionByKey.set(normalizedNameZh, nameZh);
    }
  }

  return [...suggestionByKey.values()].sort((a, b) => a.localeCompare(b));
}

function stripSpaces(text) {
  return text.replace(/\s+/g, '');
}
