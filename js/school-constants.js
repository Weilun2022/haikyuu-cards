// 熱門學校標籤／卡名搜尋建議共用的學校 key 白名單，順序與內容對齊
// index.html 既有的 schoolOrder 常數（8 個固定校隊 + ユース、疑似ユース，
// 共 10 個合法 key）。任何不在此清單內的值一律視為不合法，不可被計入熱門度
// 統計，也不可被送進 Firestore increment payload。
export const SCHOOL_KEYS = Object.freeze([
  '烏野',
  '音駒',
  '稲荷崎',
  '白鳥沢',
  '伊達工業',
  '青葉城西',
  '梟谷',
  '鴎台',
  'ユース',
  '疑似ユース',
]);

export function isValidSchoolKey(key) {
  return SCHOOL_KEYS.includes(key);
}
