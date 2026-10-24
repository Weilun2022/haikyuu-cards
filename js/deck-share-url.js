// 牌組分享連結（QR Code 掃進去的那條網址）的 payload 編碼。
// 解碼端是 index.html 的 decodeDeck——那邊是傳統全域 <script>、載入時機早於 ES module，
// 沒辦法 import 這裡，所以兩邊是各自一份實作。欄位名（n/c/k）一改就會讓既有連結匯不進去，
// 這個模組刻意不碰 DOM、不 import LZString（lz-string 是全域 <script>），
// 讓 node:test 能把 payload 形狀釘住。

// 舊資料的卡片可能沒有 count 欄位，比照 ana-model.js 的 cardCount 視為 1 張
const countOf = c => (Number.isFinite(c.count) ? c.count : 1);

export function buildDeckSharePayload(deck) {
  const payload = {
    n: deck.name,
    c: (deck.cards || []).map(c => [c.image_file, countOf(c)]),
  };
  const colors = deck.colors;
  if (colors && Object.keys(colors).length) payload.k = colors;
  return payload;
}

export function encodeDeckShare(deck, lz = globalThis.LZString) {
  return lz.compressToEncodedURIComponent(JSON.stringify(buildDeckSharePayload(deck)));
}

// base 預設是呼叫端自己的網址：從 ana.html 分享時要指向 index.html（卡牌資料庫才有匯入流程）
export function deckShareUrl(deck, { base, page = 'index.html', lz } = {}) {
  const url = new URL(page, base ?? location.href);
  url.search = `deck=${encodeDeckShare(deck, lz)}`;
  return url.href;
}
