// 牌組指紋 deck-fingerprint-v1（規格見 docs/deck-analysis-panel-plan.md §1.3）。
// 用途是把網站端的玩家牌組跟研究端（deck_health/）的牌表對上，所以兩端必須算出同一個值——
// 規格已由 Python 端與 JS 端各自獨立驗算吻合，任何「看起來等價」的改寫都可能讓兩端分家：
//
// - 排序用預設字元序（JS 的 Array#sort、Python 的 sorted 對 ASCII 一致），**不用 localeCompare**：
//   localeCompare 在某些 locale 會把 '-' 當可忽略字元，排出不同順序。
// - 序列化成無空白的二維陣列，不依賴物件鍵順序。
// - 卡號是權威卡庫的完整 card_no（例 HV-P01-001），不移除前綴、不改大小寫。
//
// 序列化（純同步）跟雜湊（非同步）刻意分開：瀏覽器只有非同步的 crypto.subtle，
// 分開之後規格的核心——排序與序列化——可以用同步斷言測，不被 Promise 包住。

const CARD_NO_PATTERN = /^\S+$/;

function mergeCounts(cardCounts) {
  const merged = new Map();
  const add = (cardNo, count) => {
    if (typeof cardNo !== 'string' || !CARD_NO_PATTERN.test(cardNo)) {
      throw new Error(`牌組指紋需要權威卡號，拿到的是 ${JSON.stringify(cardNo)}`);
    }
    // 負數在這裡就擋掉，不等合併完才看總和——牌組裡出現 -2 本身就是壞資料，
    // 讓它跟 +2 抵銷成 0 會把問題吃掉。
    if (!Number.isInteger(count) || count < 0) {
      throw new Error(`牌組指紋的張數必須是非負整數，${cardNo} 拿到的是 ${JSON.stringify(count)}`);
    }
    merged.set(cardNo, (merged.get(cardNo) || 0) + count);
  };

  if (cardCounts instanceof Map) {
    for (const [cardNo, count] of cardCounts) add(cardNo, count);
  } else if (Array.isArray(cardCounts)) {
    // 牌組文件的 cards 陣列形狀：同一個 card_no 可能出現多次（不同稀有度版本），要先相加
    for (const entry of cardCounts) add(entry?.card_no, entry?.count);
  } else {
    for (const [cardNo, count] of Object.entries(cardCounts || {})) add(cardNo, count);
  }
  return merged;
}

// 回傳 §1.3 的序列化字串，例：[["HV-P01-001",3],["HV-P01-002",2]]
export function serializeDeck(cardCounts) {
  const merged = mergeCounts(cardCounts);
  const pairs = [];
  for (const cardNo of [...merged.keys()].sort()) {
    const count = merged.get(cardNo);
    if (count > 0) pairs.push([cardNo, count]);
  }
  return JSON.stringify(pairs);
}

export async function sha1Hex(text) {
  const bytes = new TextEncoder().encode(text);
  const digest = await globalThis.crypto.subtle.digest('SHA-1', bytes);
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('');
}

export async function deckFingerprint(cardCounts) {
  return sha1Hex(serializeDeck(cardCounts));
}
