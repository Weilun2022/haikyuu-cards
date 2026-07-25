// 卡片名稱查找：把 Gemini Pass 1 讀到的日文名字（可能有 OCR 誤差）
// 對回卡片資料庫裡的候選卡片清單（同名可能有好幾種版本/稀有度）。
//
// 卡片資料不隨 functions 一起部署（避免部署包跟卡圖庫更新脫節），冷啟動時直接從
// 已經上線的網站抓最新版本，快取在記憶體裡。注意：cards_zh.json 沒有進 git/沒部署
// （見 .gitignore），前端實際載入的是 index.html 用 <script> 引入的 cards_data.js
// （`const CARDS_DATA = {...}` 這種格式，不是純 JSON），這裡要用同一份資料源。

const CARDS_JS_URL = 'https://weilun2022.github.io/haikyuu-cards/cards_data.js';
const IMAGE_BASE_URL = 'https://weilun2022.github.io/haikyuu-cards/images/';

let cachedCards = null;
let cachedByName = null;

function normalizeName(s) {
  if (!s) return '';
  return s
    .replace(/[\s　]+/g, '')
    .replace(/[☆★!！?？「」『』"'.,、。・()（）]/g, '')
    .trim();
}

// 簡易 Levenshtein 距離，短字串（人名通常 2-6 字）算起來很便宜
function editDistance(a, b) {
  const dp = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 0; j <= b.length; j++) dp[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      dp[i][j] = a[i - 1] === b[j - 1]
        ? dp[i - 1][j - 1]
        : 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
    }
  }
  return dp[a.length][b.length];
}

async function loadCards() {
  if (cachedCards) return cachedCards;
  const res = await fetch(CARDS_JS_URL);
  if (!res.ok) throw new Error(`載入 cards_data.js 失敗: ${res.status}`);
  const text = await res.text();
  const eq = text.indexOf('=');
  if (eq === -1) throw new Error('cards_data.js 格式不符預期（找不到 = 賦值）');
  const jsonText = text.slice(eq + 1).trim().replace(/;\s*$/, '');
  const data = JSON.parse(jsonText);
  cachedCards = data.cards;
  cachedByName = new Map();
  for (const c of cachedCards) {
    const key = normalizeName(c.name);
    if (!cachedByName.has(key)) cachedByName.set(key, []);
    cachedByName.get(key).push(c);
  }
  return cachedCards;
}

// 回傳這個 name_jp 猜測值最可能對應的候選卡片清單（可能是好幾個版本/稀有度）。
// 完全比對優先；比對不到才退而求其次用編輯距離找最相近的名字（處理 OCR 漏字/多字）。
export async function findCandidates(nameJp, maxCandidates = 8) {
  await loadCards();
  const target = normalizeName(nameJp);
  if (!target) return [];

  if (cachedByName.has(target)) {
    return cachedByName.get(target).slice(0, maxCandidates);
  }

  // 找編輯距離最小的已知名字（容忍 OCR 漏字，例如「渡 親治」對「渡辺 親治」）
  let bestDist = Infinity;
  let bestKeys = [];
  for (const key of cachedByName.keys()) {
    const d = editDistance(target, key);
    const threshold = Math.max(1, Math.floor(Math.max(target.length, key.length) * 0.34));
    if (d > threshold) continue;
    if (d < bestDist) {
      bestDist = d;
      bestKeys = [key];
    } else if (d === bestDist) {
      bestKeys.push(key);
    }
  }
  const out = [];
  for (const key of bestKeys) {
    out.push(...cachedByName.get(key));
    if (out.length >= maxCandidates) break;
  }
  return out.slice(0, maxCandidates);
}

export function imageUrlFor(imageFile) {
  return IMAGE_BASE_URL + imageFile;
}

const imageCache = new Map();

export async function fetchImageBase64(imageFile) {
  if (imageCache.has(imageFile)) return imageCache.get(imageFile);
  const res = await fetch(imageUrlFor(imageFile));
  if (!res.ok) throw new Error(`下載卡圖失敗 ${imageFile}: ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  const b64 = buf.toString('base64');
  imageCache.set(imageFile, b64);
  return b64;
}
