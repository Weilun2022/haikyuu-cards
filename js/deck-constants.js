// ana-model.js（瀏覽）與 deck-stats-model.js（分析）共用的牌組常數與時間讀法。
// 兩邊各自宣告一份會慢慢漂開，而這幾個值漂開的代價特別高——預設牌組認錯會整批誤砍玩家的牌，
// 兩個面板對「40 張」的定義不一致則會算出對不起來的分母。

// 預設的「快速查詢」牌組（index.html 的 QUICK_DECK_ID）。認定一律用這個固定 id，不用名稱——
// 實測 560 份文件裡有 5 份是玩家自己把牌組取名叫「快速查詢」，用名稱比對會把真牌組誤砍。
export const QUICK_DECK_ID = 'dk_quick';

export const LEGAL_DECK_SIZE = 40;

export function deckUpdatedMs(doc) {
  if (Number.isFinite(doc.clientUpdatedAt)) return doc.clientUpdatedAt;
  const t = doc.updatedAt?.toMillis?.();
  return Number.isFinite(t) ? t : 0;
}
