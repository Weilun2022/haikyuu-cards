// 卡片「特殊效果」篩選：不碰 DOM 的純函式，見 docs/adr/0005。
//
// 特殊效果 = skill_zh 裡帶括號的方括號標記，例如 [=佯攻(4)]、[=一觸(N)]、
// [=同步多點位差攻擊(烏野)(3)]；不帶括號的 [=登場]、[=攻擊區] 是發動時機／位置，不算。
// 刻意執行時從 skill_zh 抽，不寫死清單、也不讀 official_terms.json 的 bracket_tag_terms：
// 那份是人工維護的術語表，曾經漏列效果，出新彈時也不會自動更新。只讀 skill_zh 不讀 annotation_zh，
// 中文欄位方括號全是半形；全形一併收是保險（日文欄位就出現過全形）。

const EFFECT_TAG = /[\[［]=([^\]］(（]+)[(（][^\]］]*[\]］]/g;

/**
 * 算出下拉選單的效果清單。卡數算不重複的 card_no（版本不重複算）。
 * 排序：卡數多的在前；同數照該效果在陣列裡第一次出現的先後
 * （刻意不用 localeCompare，Node 與瀏覽器的中文排序可能不同）。
 *
 * @param {Array<{card_no?: string, skill_zh?: string}>} cards
 * @returns {Array<{name: string, count: number}>}
 */
export function buildEffectOptions(cards) {
  const cardNosByEffect = new Map();
  for (const card of cards) {
    for (const name of extractEffectNames(card)) {
      if (!cardNosByEffect.has(name)) cardNosByEffect.set(name, new Set());
      cardNosByEffect.get(name).add(card.card_no);
    }
  }
  return [...cardNosByEffect]
    .map(([name, cardNos]) => ({ name, count: cardNos.size }))
    .sort((a, b) => b.count - a.count); // Array.prototype.sort 是穩定排序，同數保留第一次出現的順序
}

/**
 * 卡片的特殊效果標記裡有沒有這個效果名（完全相等，不是子字串）。
 * 包含「提到」該效果的卡，例如讓對手的 [=封殺攔網(N)] 無效。
 *
 * @param {{skill_zh?: string}} card
 * @param {string} effectName
 * @returns {boolean}
 */
export function cardHasEffect(card, effectName) {
  return extractEffectNames(card).has(effectName);
}

function extractEffectNames(card) {
  const names = new Set();
  for (const match of (card.skill_zh || '').matchAll(EFFECT_TAG)) {
    const name = match[1].trim();
    if (name) names.add(name);
  }
  return names;
}
