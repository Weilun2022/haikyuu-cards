// 牌組 JSON → 網站分享連結（與 index.html 的 encodeDeck/decodeDeck 相同格式：LZString 壓縮 {n, c, k}）
// 用法：node share_link.js encode <牌組.json> <牌組名稱> [顏色.json]
//       node share_link.js decode <連結或 deck= 後面的字串>
// 牌組.json：{"卡號": 張數}，或 {"卡號": [張數, "圖檔名"]} 指定版本
// 顏色.json：{"卡號": {"free":n,"receive":n,"set":n,"attack":n}}（網站上每張卡標的角色顏色，張數合計要等於該卡張數）
const fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..');
eval(fs.readFileSync(path.join(ROOT, 'lib/lz-string.min.js'), 'utf8') + ';global.LZString=LZString;');
const src = fs.readFileSync(path.join(ROOT, 'cards_data.js'), 'utf8');
const CARDS = JSON.parse(src.slice(src.indexOf('{'), src.lastIndexOf('}') + 1)).cards;
const BASE = 'https://weilun2022.github.io/haikyuu-cards/';

function imageOf(no) {
  const c = CARDS.find(x => x.card_no === no);
  if (!c) throw new Error('找不到卡號 ' + no);
  return c.image_file;
}

function encode(deck, name, colors) {
  const c = [], k = {};
  for (const [no, v] of Object.entries(deck)) {
    const [n, img] = Array.isArray(v) ? v : [v, imageOf(no)];
    if (!CARDS.some(x => x.image_file === img)) throw new Error('找不到圖檔 ' + img);
    c.push([img, n]);
    if (colors && colors[no]) {
      const s = Object.values(colors[no]).reduce((a, b) => a + b, 0);
      if (s !== n) throw new Error(`${no} 顏色合計 ${s} ≠ 張數 ${n}`);
      k[img] = colors[no];
    }
  }
  const total = c.reduce((s, x) => s + x[1], 0);
  if (total !== 40) throw new Error('總張數 ' + total + '，不是 40');
  const payload = { n: name, c };
  if (Object.keys(k).length) payload.k = k;
  return BASE + '?deck=' + LZString.compressToEncodedURIComponent(JSON.stringify(payload));
}

function decode(s) {
  const m = s.match(/deck=([^&]+)/); if (m) s = m[1];
  return JSON.parse(LZString.decompressFromEncodedURIComponent(s));
}

if (require.main === module) {
  const [cmd, a, b, c] = process.argv.slice(2);
  if (cmd === 'encode') {
    const deck = JSON.parse(fs.readFileSync(a, 'utf8'));
    const colors = c ? JSON.parse(fs.readFileSync(c, 'utf8')) : null;
    console.log(encode(deck, b, colors));
  } else if (cmd === 'decode') {
    console.log(JSON.stringify(decode(a), null, 1));
  } else console.log('用法：node share_link.js encode <牌組.json> <名稱> [顏色.json] | decode <連結>');
}
module.exports = { encode, decode };
