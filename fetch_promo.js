#!/usr/bin/env node
/**
 * fetch_promo.js — 情報站影片爬蟲
 * 透過 YouTube Data API v3 抓取合作商家頻道最新影片 → 過濾排球少年相關 → 按學校分類 → 產出 promo_data.js
 * 跑在 GitHub Actions（每 4 小時）或本地：YOUTUBE_API_KEY=xxx node fetch_promo.js
 *
 * 原本用 RSS（feeds/videos.xml），但 GitHub Actions 共用 IP 池常被 YouTube 擋下（403）。
 * 改用官方 API：每頻道 2 quota units/次（channels.list + playlistItems.list），10,000/日額度綽綽有餘。
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

// ── 設定 ──────────────────────────────────────────────
const API_KEY = process.env.YOUTUBE_API_KEY;
const MAX_RESULTS = 15; // 每頻道抓取最新幾部

const CHANNELS = [
  // 執貳（@unique7purify31）
  { id: 'UCWTVsru0nSGFIaRGbiN5o-w', name: '執貳' },
  // HVB俱樂部（@HVB-club）
  { id: 'UCZzLY6IhEanUYnIzthUmYHw', name: 'HVB俱樂部' },
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
const MAX_STORED = 300; // 累積上限：超過只留最新的，避免無上限成長

// ── 抓取（含重試：quota/網路偶發錯誤）──────────────────
function fetchJson(url, attempt = 1) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, r => {
      let body = '';
      r.on('data', d => body += d);
      r.on('end', () => {
        let parsed = null;
        try { parsed = JSON.parse(body); } catch { /* 非 JSON 回應，交給下方狀態碼分支處理 */ }
        if (r.statusCode !== 200) {
          const reason = parsed?.error?.message || `HTTP ${r.statusCode}`;
          if (attempt < MAX_RETRY) {
            console.log(`  ${reason}，重試 ${attempt}/${MAX_RETRY - 1}...`);
            return setTimeout(() => fetchJson(url, attempt + 1).then(resolve, reject), 2000 * attempt);
          }
          return reject(new Error(reason));
        }
        resolve(parsed);
      });
    }).on('error', e => {
      if (attempt < MAX_RETRY) return setTimeout(() => fetchJson(url, attempt + 1).then(resolve, reject), 2000 * attempt);
      reject(e);
    });
  });
}

// 頻道 ID → uploads 播放清單 ID（1 quota unit）
async function getUploadsPlaylistId(channelId) {
  const url = `https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id=${channelId}&key=${API_KEY}`;
  const data = await fetchJson(url);
  const uploads = data?.items?.[0]?.contentDetails?.relatedPlaylists?.uploads;
  if (!uploads) throw new Error('查無 uploads playlist（頻道 ID 是否正確？）');
  return uploads;
}

// uploads 播放清單 → 影片列表。預設只抓最新 MAX_RESULTS 部（1 quota unit）；
// full=true 時翻頁抓完整個上傳歷史（回填用，每 50 部 1 quota unit，MAX_PAGES 是安全閥）。
const MAX_PAGES = 20; // 目前頻道 489 部影片／50 部一頁 ≈ 10 頁，抓到未來成長也夠用
async function getPlaylistVideos(playlistId, channelName, { full = false } = {}) {
  const perPage = full ? 50 : MAX_RESULTS;
  let all = [];
  let pageToken = '';
  let pages = 0;
  do {
    const url = `https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId=${playlistId}&maxResults=${perPage}${pageToken ? `&pageToken=${pageToken}` : ''}&key=${API_KEY}`;
    const data = await fetchJson(url);
    all = all.concat((data?.items || [])
      .filter(item => item.snippet?.resourceId?.videoId)
      .map(item => ({
        videoId:   item.snippet.resourceId.videoId,
        title:     item.snippet.title || '',
        published: item.snippet.publishedAt || '',   // 完整 ISO 時間戳，前端轉當地時間顯示
        // 描述只用於分類，不輸出（控制檔案大小）
        _desc:     item.snippet.description || '',
        channel:   channelName,
      })));
    pageToken = data?.nextPageToken || '';
    pages++;
  } while (full && pageToken && pages < MAX_PAGES);
  if (full && pageToken) console.warn(`[${channelName}] 回填在 ${MAX_PAGES} 頁截斷，頻道還有更舊的影片沒抓到（考慮調高 MAX_PAGES）`);
  return all;
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

// 讀取既有 promo_data.js 的 videos（檔案不存在/格式壞掉都當作沒有舊資料）
function loadExistingVideos(outPath) {
  let raw;
  try {
    raw = fs.readFileSync(outPath, 'utf8');
  } catch {
    return [];
  }
  const m = raw.match(/const PROMO_DATA = (.*);\s*$/s);
  if (!m) return [];
  try {
    const parsed = JSON.parse(m[1]);
    return Array.isArray(parsed.videos) ? parsed.videos : [];
  } catch {
    return [];
  }
}

// 累積合併：頻道最新 15 部影片裡，非排球少年相關的內容一多，舊的相關影片就會被擠出
// 這個抓取視窗（見 MAX_RESULTS）。單純覆寫等於讓它們從網站上永久消失，所以改成跟舊
// 資料以 videoId 去重後合併——一旦被判定相關就會留著，直到超過 MAX_STORED 才淘汰最舊的。
function mergeVideos(existing, fresh) {
  const byId = new Map(existing.map(v => [v.videoId, v]));
  for (const v of fresh) byId.set(v.videoId, v); // 新抓到的資料（分類可能更新）覆蓋舊的
  return [...byId.values()]
    .sort((a, b) => b.published.localeCompare(a.published))
    .slice(0, MAX_STORED);
}

// ── 主流程 ────────────────────────────────────────────
// require.main 判斷：被 fetch_promo.test.js require() 時不執行，只借用上面的函式
if (require.main === module) (async () => {
  if (!API_KEY) {
    console.error('缺少 YOUTUBE_API_KEY 環境變數，中止（保留舊 promo_data.js 不覆寫）');
    process.exit(1);
  }

  const backfill = process.env.BACKFILL === 'true' || process.argv.includes('--backfill');
  console.log('情報站爬蟲開始', new Date().toISOString(), backfill ? '（全量回填模式）' : '');
  let all = [];
  for (const ch of CHANNELS) {
    try {
      const uploadsId = await getUploadsPlaylistId(ch.id);
      const entries = await getPlaylistVideos(uploadsId, ch.name, { full: backfill });
      console.log(`[${ch.name}] API ${entries.length} 部`);
      all = all.concat(entries);
    } catch (e) {
      console.error(`[${ch.name}] 抓取失敗：${e.message}`);
      // 單一頻道失敗不中斷；若全部失敗則保留舊檔（見下方）
    }
  }

  if (all.length === 0) {
    console.error('所有頻道皆抓取失敗，保留舊 promo_data.js 不覆寫');
    process.exit(1);
  }

  const fresh = all
    .filter(v => isRelevant(v.title + ' ' + v._desc))
    .map(({ _desc, ...v }) => {
      const text = v.title + ' ' + _desc;
      const schools = classifySchools(text);
      return { ...v, schools, school: schools[0], stage: extractStage(text) };
    });

  console.log(`本次相關影片 ${fresh.length} / 抓取 ${all.length}`);

  const videos = mergeVideos(loadExistingVideos(OUT_PATH), fresh);
  console.log(`累積後共 ${videos.length} 部`);
  videos.forEach(v => console.log(`  ${v.published} [${v.schools.join('/')}${v.stage ? ' '+v.stage : ''}] ${v.title.slice(0, 36)}`));

  const data = { updated: new Date().toISOString(), videos };
  fs.writeFileSync(OUT_PATH,
    '// Auto-generated by fetch_promo.js — DO NOT EDIT\nconst PROMO_DATA = ' +
    JSON.stringify(data, null, 0) + ';\n');
  console.log(`[OK] 寫入 ${OUT_PATH}`);
})();

module.exports = { mergeVideos, loadExistingVideos, isRelevant, classifySchools, extractStage };
