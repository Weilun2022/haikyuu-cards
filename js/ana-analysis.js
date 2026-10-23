// 牌組分析面板的畫面層（ana.html 的「分析面板」分頁）。
// 所有統計都在 deck-stats-model.js 算完，這裡只負責畫，刻意不在這個檔案裡做任何運算決策——
// 要改口徑請改那個有測試的模組。
//
// 這個面板描述的是「網站使用者存了什麼」。畫面上每個圖都必須標分母（帳號數／牌組數），
// 帳號數少於門檻要標「探索性」，而且不能出現勝率、強度、剋制、流行度歷史這類推不出來的說法
// （計畫 §2.3、§2.4）。相似牌表一律叫「跨帳號相似牌表」，不是抄襲。

import { h, fmtDate, fmtTime, pct } from './ana-dom.js';
import {
  describeDeck, crossAccountSimilar, STAT_KEYS, MIN_ACCOUNTS_FOR_CONFIDENCE, SIMILARITY_THRESHOLD,
} from './deck-stats-model.js';

const STAT_LABELS = { srv: '發球', blk: '攔網', rcv: '接球', tos: '舉球', atk: '攻擊' };
const COLOR_LABELS = { free: '自由', receive: '接球', set: '舉球', attack: '攻擊', unassigned: '未指定', event: '事件' };
const ISSUE_LABELS = {
  unknown_card: '查無卡片資料',
  bad_count: '張數不是正整數',
  card_no_mismatch: '卡號與卡庫不符',
  missing_stats: '卡片缺五維數值',
  color_overflow: '用途色張數超過該卡張數',
  invalid_time: '更新時間缺漏或在未來',
};
const EXCLUDE_LABELS = {
  deleted: '已標記刪除',
  quick_deck: '預設「快速查詢」牌組',
  unidentifiable: '有查不到的卡或張數不合法',
  not_40: '不是 40 張',
  too_many_events: '事件卡超過 8 張',
};
const SIMILAR_PAIR_LIMIT = 200;
const CORE_CARD_LIMIT = 24;

const panel = (title, ...body) => h('section', { class: 'a-panel' }, h('h2', {}, title), ...body);
const note = (...text) => h('p', { class: 'a-note' }, ...text);

function sampleBadge(accounts, decks, extra) {
  const parts = [`${accounts} 個帳號`, `${decks} 副牌組`];
  if (extra) parts.push(extra);
  return h('span', { class: 'a-denom' }, parts.join('　'),
    accounts < MIN_ACCOUNTS_FOR_CONFIDENCE ? h('b', { class: 'a-warn' }, '　探索性') : null);
}

function barRow(label, value, max, right) {
  return h('div', { class: 'a-bar' },
    h('span', { class: 'a-bar-label' }, label),
    h('span', { class: 'a-bar-track' }, h('i', { style: `width:${max ? (value / max) * 100 : 0}%` })),
    h('span', { class: 'a-bar-value' }, right));
}

// ── 1 樣本概況 ─────────────────────────────────────────────────────────
function renderFunnel({ cohort, loadedAt }) {
  const max = cohort.funnel[0]?.decks || 0;
  return panel('1　樣本概況：分析了誰',
    h('div', { class: 'a-cards' }, cohort.funnel.map(s => h('div', { class: 'a-card' },
      h('b', {}, String(s.decks)),
      h('span', {}, s.label),
      h('i', {}, `${s.accounts} 帳號`)))),
    h('div', { class: 'a-bars' }, cohort.funnel.map(s => barRow(s.label, s.decks, max, `${s.decks}`))),
    note(`資料讀取於 ${fmtTime(loadedAt)}。上面每一階段都是「這一刻的雲端內容」——`,
      '玩家已刪除但還沒手動同步的牌組仍然算在裡面，所以「全部牌組文件」會偏多且無法分辨；',
      '沒登入 Google 的玩家牌組只存在本機，從頭到尾不會出現在這個漏斗裡。'));
}

// ── 2 學校分布 ─────────────────────────────────────────────────────────
function renderSchools({ agg, state }, rerender) {
  const weighted = state.schoolWeighted;
  const rows = weighted ? agg.schools.weighted : agg.schools.raw;
  const valueOf = r => (weighted ? r.weight : r.decks);
  const max = Math.max(0, ...rows.map(valueOf));
  const { topSchool, flipAccounts } = agg.schools.robustness;

  return panel('2　學校分布：玩家在組什麼',
    h('div', { class: 'a-switch' },
      h('button', {
        class: 'a-tab' + (weighted ? '' : ' active'),
        on: { click: () => { state.schoolWeighted = false; rerender(); } },
      }, '原始副數'),
      h('button', {
        class: 'a-tab' + (weighted ? ' active' : ''),
        on: { click: () => { state.schoolWeighted = true; rerender(); } },
      }, '帳號加權'),
      sampleBadge(agg.schools.denominator.accounts, agg.schools.denominator.decks,
        `${agg.sample.clusters} 個版本群`)),
    h('div', { class: 'a-bars' }, rows.map(r => barRow(
      r.school,
      valueOf(r),
      max,
      weighted ? `${r.weight.toFixed(2)}　${pct(r.share)}　${r.accounts} 帳號` : `${r.decks} 副　${pct(r.share)}`))),
    note('「原始副數」直接數牌組，存檔習慣會放大愛存檔的帳號；',
      '「帳號加權」讓每個帳號的總權重都是 1，帳號內的近似版本先聚成一群再等權分配。',
      '兩個數字都不是人氣，只是「這批使用者存了什麼」。'),
    note('主校判定：最高比例 ≥60% 且領先第二名 ≥20 個百分點才算一校，否則歸「混合」並列前兩校；',
      '整副都沒有學校標記的歸「未知」，不重分配到其他學校。'),
    flipAccounts.length
      ? note(h('b', { class: 'a-warn' }, '穩健性：'), `第一名「${topSchool}」在移除 `,
        flipAccounts.map(u => u.slice(0, 6)).join('、'), ` 這 ${flipAccounts.length} 個帳號中任一個之後就不再是唯一第一名。`)
      : note(`穩健性：移除任一單一帳號後，第一名「${topSchool ?? '—'}」都不變。`));
}

// ── 3 核心卡 ───────────────────────────────────────────────────────────
function renderCoreCards({ agg, index, state }, rerender) {
  if (!agg.coreCards.length) return panel('3　核心卡：各校共同骨架', note('主樣本是空的，沒有核心卡可算。'));
  const school = agg.coreCards.find(s => s.school === state.coreSchool) || agg.coreCards[0];
  state.coreSchool = school.school;
  const cards = school.cards.slice(0, CORE_CARD_LIMIT);

  return panel('3　核心卡：各校共同骨架',
    h('div', { class: 'a-switch' },
      h('select', {
        class: 'a-select',
        on: { change: e => { state.coreSchool = e.target.value; rerender(); } },
      }, agg.coreCards.map(s => h('option', { value: s.school, ...(s.school === school.school ? { selected: '' } : {}) },
        `${s.school}（${s.accounts} 帳號 / ${s.clusters} 群）`))),
      sampleBadge(school.accounts, school.clusters, `顯示前 ${cards.length} 張`)),
    h('table', { class: 'a-table' },
      h('thead', {}, h('tr', {},
        h('th', {}, '卡片'),
        h('th', {}, '帳號採用率'),
        h('th', {}, '採用者平均張數'),
        h('th', {}, '採用帳號數'))),
      h('tbody', {}, cards.map(c => {
        const card = index.byCardNo.get(c.card_no);
        return h('tr', {},
          h('td', {}, h('span', { class: 'a-cardname' }, card ? (card.name_zh || card.name) : c.card_no),
            h('i', { class: 'a-cardno' }, c.card_no)),
          h('td', { class: 'a-heat', style: `--heat:${c.adoptionRate}` }, h('span', {}, pct(c.adoptionRate))),
          h('td', {}, c.meanCopiesAmongAdopters == null ? '—' : c.meanCopiesAmongAdopters.toFixed(1)),
          h('td', {}, String(c.accounts)));
      }))),
    note('採用率先在帳號內等權（帳號裡的近似版本已先聚群），再平均各帳號，所以愛存檔的帳號不會被重複計算。',
      '「採用者平均張數」只算有放這張卡的群，沒放的不會把平均拉低。'),
    note('這是「這批使用者常放什麼」，不是「該放什麼」——沒有勝率或強度依據。'));
}

// ── 4 代表牌組 ─────────────────────────────────────────────────────────
function cardWall(deck, index) {
  const entries = [...deck.vector].sort((a, b) => (a[0] < b[0] ? -1 : 1));
  return h('div', { class: 'a-wall' }, entries.map(([cardNo, count]) => {
    const card = index.byCardNo.get(cardNo);
    const label = card ? (card.name_zh || card.name) : cardNo;
    return h('div', { class: 'a-wall-c', title: `${cardNo} ${label}` },
      card ? h('img', { src: `images/${card.image_file}`, alt: label, loading: 'lazy' }) : h('div', { class: 'a-wall-ph' }, cardNo),
      h('span', { class: 'a-wall-n' }, `×${count}`));
  }));
}

function renderRepresentatives({ agg, index, state }, rerender) {
  if (!agg.representatives.length) return panel('4　代表牌組：哪副最接近共識', note('主樣本是空的。'));
  const school = agg.representatives.find(s => s.school === state.repSchool) || agg.representatives[0];
  state.repSchool = school.school;

  return panel('4　代表牌組：哪副最接近共識',
    h('div', { class: 'a-switch' },
      h('select', {
        class: 'a-select',
        on: { change: e => { state.repSchool = e.target.value; rerender(); } },
      }, agg.representatives.map(s => h('option', { value: s.school, ...(s.school === school.school ? { selected: '' } : {}) },
        `${s.school}（${s.groups.length} 種組法）`))),
      // 這裡的分群是跨帳號的（把各帳號的版本群代表再聚一次），跟面板 2／3 說的「版本群」不是同一件事
      h('span', { class: 'a-denom' }, '同一校可以有多種組法，這是跨帳號再聚一次的結果')),
    h('div', {}, school.groups.slice(0, 4).map((g, i) => h('div', { class: 'a-rep' },
      h('div', { class: 'a-rep-head' },
        h('b', {}, `第 ${i + 1} 群`),
        h('span', {}, g.deck.name),
        h('span', {}, `帳號 ${g.deck.uid.slice(0, 6)}…`),
        h('span', {}, `更新 ${fmtDate(g.deck.updatedMs)}`),
        sampleBadge(g.accounts, g.members.length, `加權 ${g.weight.toFixed(2)}`)),
      cardWall(g.deck, index)))),
    note('代表牌組是群內「帳號加權距離最小的實際牌組」（medoid），不是平均出來的虛構牌表。'));
}

// ── 5 單副輪廓 ─────────────────────────────────────────────────────────
function histogram(stat) {
  const max = Math.max(0, ...stat.histogram.map(b => b.copies));
  return h('div', { class: 'a-hist' }, stat.histogram.map(b => h('span', {
    class: 'a-hist-bar',
    style: `height:${max ? (b.copies / max) * 100 : 0}%`,
    title: `數值 ${b.value}：${b.copies} 張`,
  }, h('i', {}, String(b.value)))));
}

function renderProfile({ cohort, index, state }, rerender) {
  const decks = cohort.included;
  if (!decks.length) return panel('5　單副輪廓：數值與用途偏哪邊', note('主樣本是空的。'));
  const deck = decks.find(d => d.id === state.profileDeckId && d.uid === state.profileUid) || decks[0];
  state.profileDeckId = deck.id;
  state.profileUid = deck.uid;
  const p = describeDeck(deck, index);
  const colorTotal = Object.values(p.colorUse).reduce((s, n) => s + n, 0);

  return panel('5　單副輪廓：數值與用途偏哪邊',
    h('div', { class: 'a-switch' },
      h('select', {
        class: 'a-select wide',
        on: {
          change: e => {
            const [uid, id] = e.target.value.split('\u0000');
            state.profileUid = uid;
            state.profileDeckId = id;
            rerender();
          },
        },
      }, decks.map(d => h('option', {
        value: `${d.uid}\u0000${d.id}`,
        ...(d === deck ? { selected: '' } : {}),
      }, `${d.uid.slice(0, 6)}… ／ ${d.name}`))),
      h('span', { class: 'a-denom' }, `角色 ${p.schools.roleCopies} 張　事件 ${deck.eventCopies} 張`)),
    h('div', { class: 'a-tags' },
      p.mainSchool.type === 'single'
        ? h('span', { class: 'tag' }, `主校 ${p.mainSchool.school}　${pct(p.mainSchool.share)}`)
        : p.mainSchool.type === 'mixed'
          ? h('span', { class: 'tag' }, `混合　${p.mainSchool.schools.join('／')}`)
          : h('span', { class: 'tag' }, '學校未知'),
      p.schools.dist.map(x => h('span', { class: 'tag' }, `${x.school} ${pct(x.share)}`)),
      p.schools.unknownAttributionCopies
        ? h('span', { class: 'tag' }, `未知歸屬 ${p.schools.unknownAttributionCopies} 張`) : null,
      p.unknown.copies ? h('span', { class: 'tag a-warn' }, `查無卡片資料 ${p.unknown.copies} 張`) : null),
    h('div', { class: 'a-youth' },
      h('span', {}, `ユース ${p.schools.youth['ユース'].toFixed(1)} 張`),
      h('span', {}, `疑似ユース ${p.schools.youth['疑似ユース'].toFixed(1)} 張`),
      h('i', {}, 'ユース 與 疑似ユース 是兩個獨立標記，不能互推')),
    h('div', { class: 'a-stats' }, STAT_KEYS.map(k => {
      const s = p.stats5[k];
      return h('div', { class: 'a-stat' },
        h('b', {}, STAT_LABELS[k]),
        histogram(s),
        h('span', {}, `總和 ${s.sum}　平均 ${s.mean == null ? '—' : s.mean.toFixed(2)}`),
        h('span', {}, `四分位 ${s.quantiles.p25 ?? '—'} / ${s.quantiles.p50 ?? '—'} / ${s.quantiles.p75 ?? '—'}`),
        h('i', { class: s.unknownCopies ? 'a-warn' : '' },
          `${s.knownCopies} 張有值${s.unknownCopies ? `，${s.unknownCopies} 張缺值未計入` : ''}`));
    })),
    h('div', { class: 'a-stack' }, Object.entries(p.colorUse).map(([k, n]) => n
      ? h('span', {
        class: `a-stack-seg seg-${k}`,
        style: `width:${colorTotal ? (n / colorTotal) * 100 : 0}%`,
        title: `${COLOR_LABELS[k]} ${n} 張`,
      }, `${COLOR_LABELS[k]} ${n}`)
      : null)),
    note('攻擊與攔網分開呈現，刻意不合成「強度分數」——卡片數值加總不能代表強弱。缺值不當 0。'),
    note('用途色是玩家在牌組編輯器裡標的分類，不是實際出牌行為。'));
}

// ── 6 品質與重複 ───────────────────────────────────────────────────────
function renderQuality({ normalized, cohort, agg, pairs, index, state }, rerender) {
  const views = [
    { key: 'excluded', label: `排除清單（${cohort.excluded.length}）` },
    { key: 'issues', label: `資料問題（${normalized.filter(d => d.issues.length).length}）` },
    { key: 'versions', label: '同帳號版本群' },
    { key: 'similar', label: `跨帳號相似牌表（${pairs.length}）` },
    { key: 'cards', label: `卡庫衝突（${index.conflicts.length}）` },
  ];
  const view = views.some(v => v.key === state.qualityView) ? state.qualityView : 'excluded';
  state.qualityView = view;

  let body;
  if (view === 'excluded') {
    body = h('div', { class: 'a-list' }, cohort.excluded.slice(0, 300).map(e => h('div', { class: 'a-li' },
      h('b', {}, e.deck.name),
      h('span', {}, `帳號 ${e.deck.uid.slice(0, 6)}…　${e.deck.total} 張`),
      h('i', {}, e.reasons.map(r => EXCLUDE_LABELS[r] || r).join('、')))));
  } else if (view === 'issues') {
    const flagged = normalized.filter(d => d.issues.length);
    body = h('div', { class: 'a-list' }, flagged.slice(0, 300).map(d => h('div', { class: 'a-li' },
      h('b', {}, d.name),
      h('span', {}, `帳號 ${d.uid.slice(0, 6)}…`),
      h('i', {}, d.issues.map(i => `${ISSUE_LABELS[i.code] || i.code}${i.items.length ? `（${i.items.length}）` : ''}`).join('、')))));
  } else if (view === 'versions') {
    const multi = agg.clusters.filter(c => c.members.length > 1);
    body = h('div', { class: 'a-list' }, multi.length
      ? multi.map(c => h('div', { class: 'a-li' },
        h('b', {}, c.deck.name),
        h('span', {}, `帳號 ${c.uid.slice(0, 6)}…　${c.members.length} 副同群　權重 ${c.weight.toFixed(2)}`),
        h('i', {}, c.members.map(m => m.name).join(' / '))))
      : [h('div', { class: 'a-li' }, h('i', {}, '主樣本裡沒有同帳號的近似版本。'))]);
  } else if (view === 'similar') {
    body = h('div', { class: 'a-list' }, pairs.length
      ? pairs.slice(0, SIMILAR_PAIR_LIMIT).map(p => h('div', { class: 'a-li' },
        h('b', {}, p.identical ? '牌表相同' : `相似 ${p.similarity.toFixed(3)}`),
        h('span', {}, `${p.a.uid.slice(0, 6)}…／${p.a.name}`),
        h('span', {}, `${p.b.uid.slice(0, 6)}…／${p.b.name}`)))
      : [h('div', { class: 'a-li' }, h('i', {}, `主樣本裡沒有相似度 ≥${SIMILARITY_THRESHOLD} 的跨帳號配對。`))]);
  } else {
    body = h('div', { class: 'a-list' }, index.conflicts.length
      ? index.conflicts.map(c => h('div', { class: 'a-li' },
        h('b', {}, c.card_no),
        h('span', {}, c.fields.join('、')),
        h('i', {}, c.images.join(' / '))))
      : [h('div', { class: 'a-li' }, h('i', {}, '同一個卡號的各版本資料一致，沒有衝突。'))]);
  }

  return panel('6　品質與重複：哪些資料要處理',
    h('div', { class: 'a-switch' }, views.map(v => h('button', {
      class: 'a-tab' + (v.key === view ? ' active' : ''),
      on: { click: () => { state.qualityView = v.key; rerender(); } },
    }, v.label))),
    body,
    note('標記但不整筆排除：顏色張數不符、卡號衝突、缺數值、時間無效只會影響受影響的指標，',
      '不會讓整副牌從主樣本消失（除非踩到上面「排除清單」的硬條件）。'),
    note(h('b', { class: 'a-warn' }, '相似牌表不能證明抄襲。'),
      '這裡叫「跨帳號相似牌表」，是給人工查核用的線索，不是指控。',
      `相似度 ≥${SIMILARITY_THRESHOLD} 只是起始門檻，不保證效果等價——只換一張核心卡也可能改變玩法。`));
}

// ── 入口 ───────────────────────────────────────────────────────────────
export function renderAnalysis(box, ctx) {
  // 跨帳號相似牌表只在第一次畫的時候算，之後切換面板內的篩選不重算
  ctx.pairs ??= crossAccountSimilar(ctx.cohort.included);
  const rerender = () => renderAnalysis(box, ctx);

  box.replaceChildren(
    h('div', { class: 'a-caveat' },
      h('b', {}, '這個面板只描述「這批網站使用者存了什麼」。'),
      '推不出勝率、強度、剋制、最佳張數、實際連招或操作難度；',
      '更新時間不是組建史，也不是流行度歷史。帳號分布極不均（最多的帳號約 60 副，超過一半的帳號 5 副以下），',
      '看任何數字前先看它標的分母。'),
    renderFunnel(ctx),
    renderSchools(ctx, rerender),
    renderCoreCards(ctx, rerender),
    renderRepresentatives(ctx, rerender),
    renderProfile(ctx, rerender),
    renderQuality(ctx, rerender),
  );
}
