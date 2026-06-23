#!/usr/bin/env node
/**
 * fetch_promo.js — 情報站影片爬蟲
 * 抓取合作商家 YouTube 頻道 RSS → 過濾排球少年相關 → 按學校分類 → 產出 promo_data.js
 * 跑在 GitHub Actions（每 4 小時）或本地：node fetch_promo.js
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

// ── 設定 ──────────────────────────────────────────────
const CHANNELS = [
  // 執貳（@unique7purify31）
  { id: 'UCWTVsru0nSGFIaRGbiN5o-w', name: '執貳' },
  // 未來新增商家：在此加一行即可
];

// 排球少年相關判定（標題命中任一才收錄；混合頻道會發無關影片）
const RELEVANT_KEYWORDS = [
  'バボカ', 'ハイキュー', '排球少年', 'ハイキュー!!', 'HV-', 'VOBACA', 'BREAK',
];

// 學校分類關鍵字（校名 + 代表角色，比對標題）
const SCHOOL_KEYWORDS = {
  '烏野':   ['烏野', '日向', '影山', '澤村', '月島', '西谷', '東峰', '田中', '菅原'],
  '音駒':   ['音駒', '孤爪', '研磨', '黒尾', '黑尾', '夜久', '灰羽'],
  '稻荷崎': ['稲荷崎', '稻荷崎', '宮侑', '宮治', '北信介', '尾白'],
  '白鳥澤': ['白鳥沢', '白鳥澤', '牛島', '天童', '五色'],
  '青葉城西': ['青葉城西', '青城', '及川', '岩泉'],
  '梟谷':   ['梟谷', '木兎', '木兔', '赤葦'],
  '伊達工業': ['伊達工', '伊達工業', '青根', '二口'],
  '鷗台':   ['鴎台', '鷗台', '星海', '昼神'],
};

const OUT_PATH = path.join(__dirname, 'promo_data.js');
const MAX_RETRY = 3;

// ── 抓取（含重試：RSS 偶發 404）──────────────────────
function fetchText(url, attempt = 1) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, r => {
      let body = '';
      r.on('data', d => body += d);
      r.on('end', () => {
        if (r.statusCode !== 200) {
          if (attempt < MAX_RETRY) {
            console.log(`  HTTP ${r.statusCode}，重試 ${attempt}/${MAX_RETRY - 1}...`);
            return setTimeout(() => fetchText(url, attempt + 1).then(resolve, reject), 2000 * attempt);
          }
          return reject(new Error(`HTTP ${r.statusCode}: ${url}`));
        }
        resolve(body);
      });
    }).on('error', e => {
      if (attempt < MAX_RETRY) return setTimeout(() => fetchText(url, attempt + 1).then(resolve, reject), 2000 * attempt);
      reject(e);
    });
  });
}

function unescapeXml(s) {
  return (s || '')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&#(\d+);/g, (_, n) => String.fromCharCode(n));
}

function parseEntries(xml, channelName) {
  return xml.split('<entry>').slice(1).map(e => {
    const pick = re => unescapeXml((e.match(re) || [])[1] || '');
    return {
      videoId:   pick(/<yt:videoId>([^<]*)<\/yt:videoId>/),
      title:     pick(/<title>([^<]*)<\/title>/),
      published: pick(/<published>([^<]*)<\/published>/),   // 完整 ISO 時間戳，前端轉當地時間顯示
      // 描述只用於分類，不輸出（控制檔案大小）
      _desc:     pick(/<media:description>([\s\S]*?)<\/media:description>/),
      channel:   channelName,
    };
  }).filter(v => v.videoId);
}

function isRelevant(title) {
  const t = title.toUpperCase();
  return RELEVANT_KEYWORDS.some(k => t.includes(k.toUpperCase()));
}

// 全文掃描：抓出所有出現的學校（依命中數排序），無則回 ['綜合']
// 位置無關 —— 學校名出現在標題或描述任何位置、第幾個 tag、有無 # 都認得
function classifySchools(text) {
  const hit = [];
  for (const [school, keys] of Object.entries(SCHOOL_KEYWORDS)) {
    const n = keys.filter(k => text.includes(k)).length;
    if (n > 0) hit.push({ school, n });
  }
  hit.sort((a, b) => b.n - a.n);
  return hit.length ? hit.map(h => h.school) : ['綜合'];
}

// 賽別關鍵字（全文掃描，位置無關）。
// ⚠️ 順序＝由具體到籠統：準々決勝/八強 必須排在 決勝/決賽 之前，
//    否則「準決勝」會被 includes('決勝') 誤判成決賽。回傳第一個命中的賽別標籤。
const STAGE_KEYWORDS = [
  ['八強賽', ['八強', '八强', '8強', '準々決勝']],
  ['四強賽', ['四強', '四强', '準決勝', '準決賽', '半決賽', '半决赛', '半決勝']],
  ['季軍賽', ['季軍', '三四名', '3位決定']],
  ['冠軍賽', ['冠軍', '冠军', '總決賽', '总决赛', '決勝', '決賽', '决赛', '優勝', '优胜']],
  ['十六強賽', ['十六強', '16強', '16强']],
  ['預選賽', ['預選', '预选', '預賽', '预赛', '初賽', '初赛', '資格賽', '予選']],
  ['小組賽', ['小組賽', '分組賽', '循環賽']],
];
function extractStage(text) {
  for (const [label, keys] of STAGE_KEYWORDS) {
    if (keys.some(k => text.includes(k))) return label;
  }
  return '';
}

// ── 主流程 ────────────────────────────────────────────
(async () => {
  console.log('情報站爬蟲開始', new Date().toISOString());
  let all = [];
  for (const ch of CHANNELS) {
    try {
      const xml = await fetchText(`https://www.youtube.com/feeds/videos.xml?channel_id=${ch.id}`);
      const entries = parseEntries(xml, ch.name);
      console.log(`[${ch.name}] RSS ${entries.length} 部`);
      all = all.concat(entries);
    } catch (e) {
      console.error(`[${ch.name}] 抓取失敗：${e.message}`);
      // 單一頻道失敗不中斷；若全部失敗則保留舊檔（見下方）
    }
  }

  const videos = all
    .filter(v => isRelevant(v.title + ' ' + v._desc))
    .map(({ _desc, ...v }) => {
      const text = v.title + ' ' + _desc;
      const schools = classifySchools(text);
      return { ...v, schools, school: schools[0], stage: extractStage(text) };
    })
    .sort((a, b) => b.published.localeCompare(a.published));

  console.log(`相關影片 ${videos.length} / 全部 ${all.length}`);
  videos.forEach(v => console.log(`  ${v.published} [${v.schools.join('/')}${v.stage ? ' '+v.stage : ''}] ${v.title.slice(0, 36)}`));

  if (all.length === 0) {
    console.error('所有頻道皆抓取失敗，保留舊 promo_data.js 不覆寫');
    process.exit(1);
  }

  const data = { updated: new Date().toISOString(), videos };
  fs.writeFileSync(OUT_PATH,
    '// Auto-generated by fetch_promo.js — DO NOT EDIT\nconst PROMO_DATA = ' +
    JSON.stringify(data, null, 0) + ';\n');
  console.log(`[OK] 寫入 ${OUT_PATH}`);
})();
