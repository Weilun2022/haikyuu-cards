#!/usr/bin/env node
/**
 * fetch_schedule.js — 店家賽程表爬蟲
 * 讀取官方（遊戲代理商）公開維護的 Google Sheet → 正規化 → 與上次結果 fuzzy diff →
 * 產出 schedule_data.js（網站顯示用）與 schedule_registry.json（跨次執行的持久狀態）。
 *
 * 跑在 GitHub Actions（定期）或本地：node fetch_schedule.js
 *
 * 設計背景（跟 GPT-5.5 討論定案）：
 * 這份 Sheet 是官方自己維護、我們沒有編輯權也不能要求他們加 ID 欄位，「序」只是流水號、
 * 插入/刪除列就會位移，不能當穩定 ID。所以改用「合成 ID + 持久化 registry + fuzzy diff」：
 * 每次抓取後跟上一版 registry 比對，判斷是同一場的異動還是全新場次，決定沿用舊 ID 或發新 ID。
 * 只有真正影響使用者行事曆判斷的欄位變動（日期/時間/店名/地址/類型/報名方式/電話）才會讓
 * revision 遞增 —— 前端 Phase1.5 用 revision 判斷是否要提醒使用者「這場已加入的賽事已改期」。
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

// ── 設定 ──────────────────────────────────────────────
const SHEET_ID = '1SuLydg-rVSWSh9Y9JGikC2PvA4vPQixH1t_5WKlQbpU';
const CSV_URL = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/export?format=csv&gid=0`;

const DATA_OUT_PATH = path.join(__dirname, 'schedule_data.js');
const REGISTRY_PATH = path.join(__dirname, 'schedule_registry.json');

const EXPECTED_HEADERS = ['序', '日期', '活動時間', '比賽類型', '店家名稱', '店家連絡電話', '店家地址', '報名人數', '報名方式', '業務分區', '負責業務'];
const BIG_REMOVAL_RATIO = 0.5;      // 這次未來場次「消失比例」超過此值，視為可疑，中止不覆寫
const DATE_MATCH_WINDOW_DAYS = 45;  // fuzzy matching 允許的日期位移範圍
const TOMBSTONE_RETENTION_DAYS = 45; // 場次消失後，registry 保留 tombstone 供比對/前端提示的天數
const MAX_RETRY = 3;

// ── HTTP 抓取（含重試）──────────────────────────────────
function fetchText(url, attempt = 1) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, r => {
      // Google 對未公開分享的試算表會轉址到登入頁；跟隨 3xx 一次即可
      if (r.statusCode >= 300 && r.statusCode < 400 && r.headers.location) {
        r.resume();
        return fetchText(r.headers.location, attempt).then(resolve, reject);
      }
      let body = '';
      r.setEncoding('utf8');
      r.on('data', d => body += d);
      r.on('end', () => {
        if (r.statusCode !== 200) {
          if (attempt < MAX_RETRY) {
            console.log(`  HTTP ${r.statusCode}，重試 ${attempt}/${MAX_RETRY - 1}...`);
            return setTimeout(() => fetchText(url, attempt + 1).then(resolve, reject), 2000 * attempt);
          }
          return reject(new Error(`HTTP ${r.statusCode}`));
        }
        resolve(body);
      });
    }).on('error', e => {
      if (attempt < MAX_RETRY) return setTimeout(() => fetchText(url, attempt + 1).then(resolve, reject), 2000 * attempt);
      reject(e);
    });
  });
}

// ── CSV 解析（處理引號內含逗號/換行/跳脫雙引號）──────────
function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') { cell += '"'; i++; }
        else inQuotes = false;
      } else {
        cell += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ',') {
      row.push(cell); cell = '';
    } else if (ch === '\n') {
      row.push(cell); cell = '';
      rows.push(row); row = [];
    } else if (ch === '\r') {
      // 忽略，交給後面的 \n 收尾（相容 \r\n）
    } else {
      cell += ch;
    }
  }
  if (cell !== '' || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

// ── 找表頭列 ─────────────────────────────────────────
function findHeaderRowIndex(rows) {
  for (let i = 0; i < rows.length; i++) {
    const cells = rows[i].map(c => (c || '').trim());
    if (EXPECTED_HEADERS.every((h, idx) => cells[idx] === h)) return i;
  }
  return -1;
}

// ── 正規化小工具 ─────────────────────────────────────
function slugifyStore(name) {
  return (name || '')
    .trim()
    .toLowerCase()
    .replace(/[\s　]+/g, '')
    .replace(/[()（）\-_./]/g, '');
}

function normalizeRegion(raw) {
  const s = (raw || '').trim();
  if (s.startsWith('北')) return 'north';
  if (s.startsWith('中')) return 'central';
  if (s.startsWith('南')) return 'south';
  return 'unknown';
}

function normalizeTypeKey(raw) {
  const s = (raw || '').trim();
  const hasNewbie = s.includes('新手');
  const hasCasual = s.includes('交流');
  if (hasNewbie && hasCasual) return 'mixed';
  if (hasNewbie) return 'newbie';
  if (hasCasual) return 'casual';
  return 'other';
}

function normalizeCapacity(raw) {
  const s = (raw || '').trim();
  const m = s.match(/^(\d+)\s*人?$/);
  return m ? m[1] : s;
}

// 日期解析：處理 YYYY/M/D、YYYY/M/D(週幾)、M月D日（缺年份，事後靠 context 推斷）
function parseDateRaw(raw) {
  const s = (raw || '').trim().replace(/[（(].*?[）)]/g, '').trim();
  let m = s.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
  if (m) {
    const [, y, mo, d] = m;
    return { year: Number(y), month: Number(mo), day: Number(d), yearExplicit: true };
  }
  m = s.match(/^(\d{1,2})月(\d{1,2})日$/);
  if (m) {
    const [, mo, d] = m;
    return { year: null, month: Number(mo), day: Number(d), yearExplicit: false };
  }
  return null;
}

function isValidYMD(y, mo, d) {
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return false;
  const dt = new Date(Date.UTC(y, mo - 1, d));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === d;
}

function pad2(n) { return String(n).padStart(2, '0'); }
function ymdToIso(y, mo, d) { return `${y}-${pad2(mo)}-${pad2(d)}`; }

// ── 主流程 ────────────────────────────────────────────
(async () => {
  console.log('賽程表爬蟲開始', new Date().toISOString());

  let csvText;
  try {
    csvText = process.env.SCHEDULE_TEST_CSV_PATH
      ? fs.readFileSync(process.env.SCHEDULE_TEST_CSV_PATH, 'utf8')
      : await fetchText(CSV_URL);
  } catch (e) {
    console.error(`抓取 Google Sheet 失敗：${e.message}，保留舊資料不覆寫`);
    process.exit(1);
  }

  const rows = parseCsv(csvText);
  const headerIdx = findHeaderRowIndex(rows);
  if (headerIdx === -1) {
    console.error('找不到預期表頭列，官方 Sheet 格式可能已變動，中止並保留舊資料');
    console.error('預期表頭：' + EXPECTED_HEADERS.join(','));
    process.exit(1);
  }
  console.log(`表頭列位於第 ${headerIdx + 1} 列`);

  const dataRows = rows.slice(headerIdx + 1);

  // 第一輪：解析每列，收集「有明確年份」的日期分布，供缺年份的列推斷用
  const parsedRows = [];
  const explicitYearCount = {};
  for (let i = 0; i < dataRows.length; i++) {
    const r = dataRows[i];
    const seq = (r[0] || '').trim();
    const dateRaw = (r[1] || '').trim();
    const timeRaw = (r[2] || '').trim();
    const formatRaw = (r[3] || '').trim();
    const storeName = (r[4] || '').trim();
    const phone = (r[5] || '').trim();
    const address = (r[6] || '').trim();
    const capacityRaw = (r[7] || '').trim();
    const registrationMethod = (r[8] || '').trim();
    const regionRaw = (r[9] || '').trim();

    if (seq === '範例') continue; // 官方教學範例列
    if (!dateRaw && !timeRaw && !storeName && !formatRaw) continue; // 全空白分隔列
    if (!dateRaw || !timeRaw || !storeName || !formatRaw) {
      console.warn(`[跳過] 第 ${headerIdx + 2 + i} 列缺少關鍵欄位：日期="${dateRaw}" 時間="${timeRaw}" 類型="${formatRaw}" 店家="${storeName}"`);
      continue;
    }

    const dp = parseDateRaw(dateRaw);
    if (!dp) {
      console.warn(`[跳過] 第 ${headerIdx + 2 + i} 列日期格式無法解析："${dateRaw}"`);
      continue;
    }
    if (dp.yearExplicit) {
      if (!isValidYMD(dp.year, dp.month, dp.day)) {
        console.warn(`[跳過] 第 ${headerIdx + 2 + i} 列日期不合法："${dateRaw}"`);
        continue;
      }
      explicitYearCount[dp.year] = (explicitYearCount[dp.year] || 0) + 1;
    }

    const timeMatch = timeRaw.match(/^(\d{1,2}):(\d{2})$/);
    if (!timeMatch) {
      console.warn(`[跳過] 第 ${headerIdx + 2 + i} 列時間格式無法解析："${timeRaw}"`);
      continue;
    }
    const time = `${pad2(Number(timeMatch[1]))}:${timeMatch[2]}`;

    parsedRows.push({
      rowNum: headerIdx + 2 + i,
      dp, time, formatRaw, storeName, phone, address, capacityRaw, registrationMethod, regionRaw,
    });
  }

  // 主流年份：明確年份中出現次數最多者；若完全沒有明確年份，用今年
  const now = new Date();
  const nowTaipei = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));
  let dominantYear = nowTaipei.getFullYear();
  let bestCount = 0;
  for (const [y, c] of Object.entries(explicitYearCount)) {
    if (c > bestCount) { bestCount = c; dominantYear = Number(y); }
  }

  // 第二輪：補上缺年份的日期、組出最終正規化紀錄
  const normalized = [];
  for (const row of parsedRows) {
    let { year, month, day, yearExplicit } = row.dp;
    let dateInferred = false;
    if (!yearExplicit) {
      year = dominantYear;
      dateInferred = true;
      if (!isValidYMD(year, month, day)) {
        console.warn(`[跳過] 第 ${row.rowNum} 列缺年份推斷後日期仍不合法：${month}月${day}日 → ${year}`);
        continue;
      }
    }
    const date = ymdToIso(year, month, day);
    const storeKey = slugifyStore(row.storeName);
    const typeKey = normalizeTypeKey(row.formatRaw);
    const region = normalizeRegion(row.regionRaw);

    normalized.push({
      date, storeKey,
      time: row.time,
      typeKey,
      region,
      storeName: row.storeName,
      phone: row.phone,
      address: row.address,
      format: row.formatRaw,
      capacity: normalizeCapacity(row.capacityRaw),
      registrationMethod: row.registrationMethod,
      dateInferred,
      startAt: `${date}T${row.time}:00+08:00`,
    });
  }

  console.log(`解析出 ${normalized.length} 筆有效賽事（原始 ${dataRows.length} 列）`);
  if (normalized.length === 0) {
    console.error('解析出 0 筆有效賽事，可能是格式跑掉，中止並保留舊資料');
    process.exit(1);
  }

  // ── 讀取上一版 registry ──────────────────────────────
  let registry = { meta: { nextSeq: 1 }, events: [] };
  if (fs.existsSync(REGISTRY_PATH)) {
    try { registry = JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf8')); }
    catch (e) { console.warn('registry 讀取失敗，視為全新開始：' + e.message); }
  }
  if (!registry.meta) registry.meta = { nextSeq: 1 };
  if (!registry.events) registry.events = [];

  const nowIso = new Date().toISOString();
  const todayIso = ymdToIso(nowTaipei.getFullYear(), nowTaipei.getMonth() + 1, nowTaipei.getDate());

  function calendarFieldsHash(ev) {
    return JSON.stringify([ev.date, ev.time, ev.storeName, ev.address, ev.format, ev.registrationMethod, ev.phone]);
  }
  function strongKey(ev) { return [ev.storeKey, ev.typeKey, ev.date, ev.time].join('|'); }
  function dateDiffDays(a, b) { return Math.abs((new Date(a) - new Date(b)) / 86400000); }

  // 只拿「仍然有效、還沒過期」的既有活躍事件當作比對基準
  const prevActive = registry.events.filter(e => e.status === 'active');
  const consumed = new Set();

  const byStrongKey = new Map();
  const byStoreTypeDate = new Map();
  const byStoreTypeTime = new Map();
  for (const e of prevActive) {
    byStrongKey.set(strongKey(e), e);
    const kDate = `${e.storeKey}|${e.typeKey}|${e.date}`;
    const kTime = `${e.storeKey}|${e.typeKey}|${e.time}`;
    if (!byStoreTypeDate.has(kDate)) byStoreTypeDate.set(kDate, []);
    byStoreTypeDate.get(kDate).push(e);
    if (!byStoreTypeTime.has(kTime)) byStoreTypeTime.set(kTime, []);
    byStoreTypeTime.get(kTime).push(e);
  }

  const finalEvents = [];
  let newCount = 0, updatedCount = 0, unchangedCount = 0;

  for (const rec of normalized) {
    let matched = null;

    // 1. 完全相同：店家+類型+日期+時間
    const sk = strongKey(rec);
    const exact = byStrongKey.get(sk);
    if (exact && !consumed.has(exact.id)) matched = exact;

    // 2. 同店同類型同日，時間不同 → 視為改時間（要求唯一候選）
    if (!matched) {
      const cands = (byStoreTypeDate.get(`${rec.storeKey}|${rec.typeKey}|${rec.date}`) || []).filter(e => !consumed.has(e.id));
      if (cands.length === 1) matched = cands[0];
    }

    // 3. 同店同類型同時間，日期在容許範圍內 → 視為改日期（要求唯一候選）
    if (!matched) {
      const cands = (byStoreTypeTime.get(`${rec.storeKey}|${rec.typeKey}|${rec.time}`) || [])
        .filter(e => !consumed.has(e.id) && dateDiffDays(e.date, rec.date) <= DATE_MATCH_WINDOW_DAYS);
      if (cands.length === 1) matched = cands[0];
    }

    // 4. 評分制 fallback：同店家內找分數最高且明顯領先的候選
    if (!matched) {
      const cands = prevActive.filter(e => !consumed.has(e.id) && e.storeKey === rec.storeKey);
      let best = null, bestScore = -1, tie = false;
      for (const e of cands) {
        let score = 40; // sameStore（篩選條件已保證）
        if (e.address === rec.address) score += 20;
        if (e.typeKey === rec.typeKey) score += 20;
        if (e.date === rec.date) score += 15; else if (dateDiffDays(e.date, rec.date) <= 14) score += 10;
        if (e.time === rec.time) score += 10;
        if (score > bestScore) { bestScore = score; best = e; tie = false; }
        else if (score === bestScore) { tie = true; }
      }
      if (best && bestScore >= 75 && !tie) matched = best;
    }

    if (matched) {
      consumed.add(matched.id);
      const newHash = calendarFieldsHash(rec);
      const oldHash = calendarFieldsHash(matched);
      const revision = newHash !== oldHash ? (matched.revision || 1) + 1 : (matched.revision || 1);
      if (newHash !== oldHash) updatedCount++; else unchangedCount++;
      finalEvents.push({
        ...rec,
        id: matched.id,
        revision,
        status: 'active',
        firstSeenAt: matched.firstSeenAt || nowIso,
        lastSeenAt: nowIso,
        removedAt: null,
      });
    } else {
      newCount++;
      const id = 'evt_' + String(registry.meta.nextSeq).padStart(6, '0');
      registry.meta.nextSeq++;
      finalEvents.push({
        ...rec,
        id,
        revision: 1,
        status: 'active',
        firstSeenAt: nowIso,
        lastSeenAt: nowIso,
        removedAt: null,
      });
    }
  }

  // 這次沒被比對到的既有活躍事件 → 視為消失，轉 tombstone
  const missing = prevActive.filter(e => !consumed.has(e.id));
  const missingFutureCount = missing.filter(e => e.date >= todayIso).length;
  const prevActiveFutureCount = prevActive.filter(e => e.date >= todayIso).length;
  if (prevActiveFutureCount > 0 && missingFutureCount / prevActiveFutureCount > BIG_REMOVAL_RATIO) {
    console.error(`本次未來場次消失比例 ${(missingFutureCount / prevActiveFutureCount * 100).toFixed(0)}% 超過門檻，疑似異常，中止並保留舊資料`);
    console.error(`（消失 ${missingFutureCount} / 先前活躍 ${prevActiveFutureCount}）`);
    process.exit(1);
  }

  for (const e of missing) {
    finalEvents.push({ ...e, status: 'removed', removedAt: e.removedAt || nowIso });
  }

  // 保留既有 tombstone（這次沒重新出現在 prevActive 比對池、本來就是 removed 的）
  const alreadyRemoved = registry.events.filter(e => e.status === 'removed');
  for (const e of alreadyRemoved) {
    const ageDays = (Date.now() - new Date(e.removedAt)) / 86400000;
    if (ageDays <= TOMBSTONE_RETENTION_DAYS) finalEvents.push(e);
  }

  registry.events = finalEvents;
  registry.meta.lastRunAt = nowIso;
  registry.meta.lastSuccessfulFetchAt = nowIso;

  fs.writeFileSync(REGISTRY_PATH, JSON.stringify(registry, null, 2));
  console.log(`[OK] 寫入 ${REGISTRY_PATH}（新增 ${newCount}／異動 ${updatedCount}／不變 ${unchangedCount}／消失 ${missing.length}）`);

  // ── 產出網站顯示用 schedule_data.js（只留未來場次 + 近期 tombstone）──
  const activeUpcoming = registry.events
    .filter(e => e.status === 'active' && e.date >= todayIso)
    .sort((a, b) => a.startAt.localeCompare(b.startAt))
    .map(({ storeKey, typeKey, ...pub }) => pub); // storeKey/typeKey 只是內部比對用，前端不需要

  const removedRecent = registry.events
    .filter(e => e.status === 'removed' && (Date.now() - new Date(e.removedAt)) / 86400000 <= TOMBSTONE_RETENTION_DAYS)
    .map(({ storeKey, typeKey, ...pub }) => pub);

  const siteData = {
    updated: nowIso,
    events: activeUpcoming,
    removedRecent,
  };
  fs.writeFileSync(DATA_OUT_PATH,
    '// Auto-generated by fetch_schedule.js — DO NOT EDIT\nconst SCHEDULE_DATA = ' +
    JSON.stringify(siteData, null, 0) + ';\n');
  console.log(`[OK] 寫入 ${DATA_OUT_PATH}（${activeUpcoming.length} 場未來賽事）`);
})();
