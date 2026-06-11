#!/usr/bin/env node
/**
 * fetch_news.js — 官方新品資訊爬蟲
 * 抓取塔卡拉多美 バボカ!!BREAK 官網產品列表 → 合併手動資料 → 產出 promo_news.js
 * 跑在 GitHub Actions（每天 1 次）或本地：node fetch_news.js
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'https://www.takaratomy.co.jp/products/haikyuvobacabreak/';
const OUTPUT_FILE = path.join(__dirname, 'promo_news.js');
const BAK_FILE = path.join(__dirname, 'promo_news.js.bak');

// 已知 fallback 日期（官網子頁面抓不到時使用）
const FALLBACK_DATES = {
  'HV-P01': '2025-10-25',
  'HV-D01': '2025-10-25',
  'HV-D02': '2025-10-25',
  'HV-P02': '2026-02-28',
  'HV-D03': '2026-02-28',
  'HV-P03': '2026-06-27',
};

// ── 抓取 HTML ────────────────────────────────────────────
function fetchHtml(url) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, r => {
      if (r.statusCode >= 300 && r.statusCode < 400 && r.headers.location) {
        return fetchHtml(r.headers.location).then(resolve, reject);
      }
      let body = '';
      r.setEncoding('utf8');
      r.on('data', d => body += d);
      r.on('end', () => resolve(body));
      r.on('error', reject);
    }).on('error', reject);
  });
}

// ── 從主頁解析產品列表 ────────────────────────────────────
// 注意：官網 HTML 有 bug，HV-P03 連結內的 alt 寫著 P02。
// 策略：以 href 連結取 productCode（準確），以 alt 取名稱（先找同 <a> 塊內最後一個 ttl alt，
//        若 alt code 對不上則用 fallback 名稱）。
const FALLBACK_TITLES = {
  'HV-P01': 'HV-P01 ハイキュー!! バボカ!! BREAK ブースターパック ゴミ捨て場の決戦',
  'HV-P02': 'HV-P02 ハイキュー!! バボカ!! BREAK ブースターパック 最強の挑戦者',
  'HV-P03': 'HV-P03 ハイキュー!! バボカ!! BREAK ブースターパック ユース&選抜強化合宿',
  'HV-D01': 'HV-D01 ハイキュー!! バボカ!! BREAK スターターデッキ 烏野高校',
  'HV-D02': 'HV-D02 ハイキュー!! バボカ!! BREAK スターターデッキ 音駒高校',
  'HV-D03': 'HV-D03 ハイキュー!! バボカ!! BREAK スターターデッキ 稲荷崎高校',
};

function parseProductLinks(html) {
  const items = [];
  const seen = new Set();

  // 1. 從 href 取所有產品代號（P/D 系列）
  const hrefRe = /href="(\.\/product\/(HV-[PDS]\d+)\.html)"/g;
  let m;
  while ((m = hrefRe.exec(html)) !== null) {
    const href = m[1];
    const code = m[2];
    if (seen.has(code)) continue;
    seen.add(code);

    // 找 <a>...</a> 區塊（href 之後到 </a>）
    const blockEnd = html.indexOf('</a>', m.index) + 4;
    const block    = html.slice(m.index, blockEnd);

    // 找 ttl 圖片的 alt 和 src
    const ttlRe = /<img[^>]+src="([^"]*ttl[^"]*)"[^>]+alt="([^"]*)"/;
    const ttlM  = block.match(ttlRe) || block.match(/<img[^>]+alt="([^"]*)"[^>]+src="([^"]*ttl[^"]*)"/);
    let alt = '', imgSrc = '';
    if (ttlM) {
      // 兩種 attr 順序都支援
      if (ttlM[0].indexOf('src=') < ttlM[0].indexOf('alt=')) {
        imgSrc = ttlM[1]; alt = ttlM[2];
      } else {
        alt = ttlM[1]; imgSrc = ttlM[2];
      }
    }

    // alt code 對不上（官網 bug）時用 fallback
    if (!alt.startsWith(code)) alt = FALLBACK_TITLES[code] || code;

    const productType = alt.includes('ブースターパック') ? 'ブースターパック'
                      : alt.includes('スターターデッキ')  ? 'スターターデッキ'
                      : '';

    const img  = imgSrc ? BASE_URL + imgSrc.replace(/^\.\//, '') : '';
    const link = BASE_URL + href.replace(/^\.\//, '');

    items.push({ productCode: code, title: alt, productType, img, link });
  }

  // 2. 補上 D 系列（主頁沒有 href，從 alt 掃描）
  const altRe = /alt="(HV-([DS]\d+)[^"]*)"/g;
  while ((m = altRe.exec(html)) !== null) {
    const code = 'HV-' + m[2];
    if (seen.has(code)) continue;
    const imgTagStart = html.lastIndexOf('<img', m.index);
    const imgTag = html.slice(imgTagStart, m.index + m[0].length + 10);
    if (!imgTag.includes('ttl')) continue;
    seen.add(code);

    const alt = m[1];
    const productType = alt.includes('スターターデッキ') ? 'スターターデッキ' : '';
    const srcM = imgTag.match(/src="([^"]+)"/);
    const img  = srcM ? BASE_URL + srcM[1].replace(/^\.\//, '') : '';
    const link = `${BASE_URL}product/${code}.html`;

    items.push({ productCode: code, title: alt, productType, img, link });
  }

  return items;
}

// ── 從產品子頁面抓發售日 ──────────────────────────────────
async function fetchProductDate(code) {
  const url = `${BASE_URL}product/${code}.html`;
  try {
    const html = await fetchHtml(url);
    const m = html.match(/(\d{4})年(\d{1,2})月(\d{1,2})日/);
    if (m) return `${m[1]}-${m[2].padStart(2,'0')}-${m[3].padStart(2,'0')}`;
  } catch (_) { /* fall through */ }
  return FALLBACK_DATES[code] || '';
}

// ── 讀取現有 promo_news.js ────────────────────────────────
function readExisting() {
  try {
    if (!fs.existsSync(OUTPUT_FILE)) return [];
    const src = fs.readFileSync(OUTPUT_FILE, 'utf8');
    // eval 在 CI 可信環境下安全，因為這是自己產生的檔案
    const PROMO_NEWS = {};
    new Function('PROMO_NEWS', src.replace('const PROMO_NEWS', 'PROMO_NEWS'))(PROMO_NEWS);
    return PROMO_NEWS.items || [];
  } catch (_) { return []; }
}

// ── 合併：官方資料 + 手動資料 ─────────────────────────────
// 以 productCode 去重；保留手動欄位（img 若手動有就不覆蓋）
function merge(oldItems, newItems) {
  const map = new Map();
  for (const item of oldItems) map.set(item.productCode || item.title, item);

  for (const n of newItems) {
    const key = n.productCode;
    if (map.has(key)) {
      const old = map.get(key);
      // 更新官方資料，保留手動填寫的 img / desc
      map.set(key, {
        ...n,
        desc: old.desc || n.desc || '',
        img:  old.img  || n.img  || '',
      });
    } else {
      map.set(key, { desc: '', ...n });
    }
  }

  return [...map.values()].sort((a, b) => (b.date||'').localeCompare(a.date||''));
}

// ── 輸出 promo_news.js ────────────────────────────────────
function writeOutput(items) {
  const lines = items.map(it => {
    const esc = s => (s||'').replace(/'/g, "\\'");
    return `    {
      date: '${esc(it.date)}',
      title: '${esc(it.title)}',
      desc: '${esc(it.desc)}',
      link: '${esc(it.link)}',
      img: '${esc(it.img)}',
      productCode: '${esc(it.productCode)}',
      productType: '${esc(it.productType)}',
    }`;
  });
  const content = `// Auto-generated by fetch_news.js — 手動欄位（desc/img）會被保留\nconst PROMO_NEWS = {\n  items: [\n${lines.join(',\n')}\n  ],\n};\n`;
  fs.writeFileSync(OUTPUT_FILE, content, 'utf8');
  console.log(`[OK] 寫入 ${items.length} 筆 → ${OUTPUT_FILE}`);
}

// ── 主流程 ────────────────────────────────────────────────
(async () => {
  console.log('新品爬蟲開始', new Date().toISOString());

  const html = await fetchHtml(BASE_URL);
  console.log(`主頁抓取完成，${html.length} bytes`);

  const products = parseProductLinks(html);
  console.log(`找到 ${products.length} 個產品連結`);

  // 並行抓各產品日期（間隔 800ms 避免過快）
  for (const p of products) {
    p.date = await fetchProductDate(p.productCode);
    console.log(`  ${p.productCode}: ${p.title.slice(0, 30)} → ${p.date}`);
    await new Promise(r => setTimeout(r, 800));
  }

  const oldItems = readExisting();
  console.log(`現有手動資料 ${oldItems.length} 筆`);

  const merged = merge(oldItems, products);

  if (fs.existsSync(OUTPUT_FILE)) fs.copyFileSync(OUTPUT_FILE, BAK_FILE);
  writeOutput(merged);
})().catch(e => { console.error(e); process.exit(1); });
