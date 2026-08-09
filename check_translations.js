// Translation checker for Haikyuu cards_data.js
const fs = require('fs');

// Load the file and extract CARDS_DATA
const content = fs.readFileSync(__dirname + '/cards_data.js', 'utf8');
const modified = content.replace('const CARDS_DATA =', 'global.CARDS_DATA =');
eval(modified);

// 官方術語單一事實來源：跟 build_data.py 共用同一份 official_terms.json，
// 不再各自硬編同一批術語——避免像 ドシャット 那次一樣，這裡的預期值
// 本身寫錯卻沒人發現（check_translations.js 曾經預期錯的中文術語，
// 長期誤報直到 2026-07-25 才修正）。
const _officialTermsData = JSON.parse(fs.readFileSync(__dirname + '/official_terms.json', 'utf8'));
const OFFICIAL_TERMS = _officialTermsData.terms;
// 這幾個是 [=X(N)] 遊戲引擎標記語法，不是一般散文詞彙，提示文字要分開處理
const BRACKET_TAG_TERMS = new Set(_officialTermsData.bracket_tag_terms || []);

const cards = global.CARDS_DATA.cards;
console.log('Total cards: ' + cards.length);

const issues = [];
const stats = {
  'Rule01_其後': 0,
  'Rule02_使其出場': 0,
  'Rule03_每次出場': 0,
  'Rule04_自己的從X區': 0,
  'Rule05_對手的從X區': 0,
  'Rule06_自己的在X區': 0,
  'Rule07_再N值語序': 0,
  'Rule08_防守點數': 0,
  'Rule09_選擇發動': 0,
  'Rule10_時可使用': 0,
  'Rule11_值等於': 0,
  'Rule12_登場出場': 0,
  '術語錯誤': 0,
  '語法問題': 0,
};

// ── 共用檢查：跟輸入來源無關（skill 文字／QA 文字都適用），2026-08 從 checkCard()
// 抽出來，讓 QA 掃描可以重用同一套邏輯，不用另外複製一份 ──────────────────

// 引號內是引用其他卡片/技能的日文原名（刻意保留不翻，跟 ユース 同一類政策），
// 假名/片假名殘留檢查、單字漢字檢查都不該把這些算進去——2026-07-25 逐筆核對 44 筆誤判
// 後發現 「...」 這個引號形式；2026-08 QA 全量重翻批次核對術語一致性時發現 QA 文字
// 引用 EVENT 卡名時常用 “...” 全形彎引號而不是 「...」，同一個 EVENT 卡名在不同筆
// QA 裡兩種引號都會出現，只排除 「...」 會讓一半誤判成殘留——兩種引號都要排除。
function stripQuotedNames(zh) {
  return zh.replace(/「[^」]*」/g, '').replace(/“[^”]*”/g, '');
}

// Japanese hiragana/katakana remaining in zh
function checkKanaResidue(zh) {
  const issues = [];
  const zhWithoutQuotedNames = stripQuotedNames(zh);

  // hiragana
  if (/[ぁ-ん]/.test(zhWithoutQuotedNames)) {
    const m = zhWithoutQuotedNames.match(/[ぁ-ん]+/g);
    issues.push({ type: '語法問題', fragment: '日文假名殘留: ' + m.join(','), suggestion: '移除日文假名' });
  }

  // katakana（排除 [=X] 標注跟「...」引用的原名，只留下真正可能漏翻的部分）
  // 片假名範圍務必含長音符「ー」（U+30FC）；ユース／疑似ユース 依 ADR-0001 刻意保留不翻，明確排除
  const YUUSU_TERMS = ['疑似ユース', 'ユース'];
  let zhForKatakanaCheck = zhWithoutQuotedNames.replace(/\[=[^\]]+\]/g, '');
  for (const term of YUUSU_TERMS) zhForKatakanaCheck = zhForKatakanaCheck.replaceAll(term, '');
  const kataInZh = zhForKatakanaCheck.match(/[ァ-ンー]{2,}/g);
  if (kataInZh) {
    issues.push({ type: '語法問題', fragment: '日文片假名殘留: ' + kataInZh.join(','), suggestion: '確認是否需翻譯' });
  }

  return issues;
}

// 官方術語一致性檢查：迴圈跑 official_terms.json 裡的每一筆，跟 build_data.py
// 共用同一份期望值——不再像過去那樣，這裡的期望值自己寫錯（ドシャット 那次）
// 卻沒有任何東西能發現，因為兩邊各自硬編、互不參照。
function checkOfficialTerms(zh, jp) {
  const issues = [];
  for (const [jpTerm, zhTerm] of Object.entries(OFFICIAL_TERMS)) {
    if (jp.includes(jpTerm) && !zh.includes(zhTerm)) {
      const isBracketTag = BRACKET_TAG_TERMS.has(jpTerm);
      issues.push({
        type: '術語錯誤',
        fragment: isBracketTag ? `(${jpTerm}未標注${zhTerm})` : `(${jpTerm}未正確譯出)`,
        suggestion: isBracketTag ? `應標注「[=${zhTerm}]」` : `應譯為「${zhTerm}」`,
      });
    }
  }
  return issues;
}

// 登場／出場／[=登場] 雙形式語境檢查：不能放進 OFFICIAL_TERMS 直接跑上面那個迴圈——
// 「登場」有兩種正確形式看語境（一般散文「出場」vs 技能標記保留原文「[=登場]」），
// 用同一把 zh.includes(zhTerm) 尺量會讓其中一種形式必然誤判（2026-08 QA 全量重翻
// 才發現這個問題：bracket 標記被機翻成 [=出現]/[=外觀]，散文被機翻成「出現」，
// 兩種都不是「出場」，需要各自比對來源是不是 bracket 標記）。
function checkAppearanceTerm(zh, jp) {
  const issues = [];
  if (!jp) return issues;
  const jpWithoutBracketTags = jp.replace(/\[=[^\]]+\]/g, '');
  const hasBareTouba = jpWithoutBracketTags.includes('登場');
  const hasBracketTouba = jp.includes('[=登場]');

  if (hasBareTouba && !zh.includes('出場')) {
    issues.push({ type: 'Rule12_登場出場', fragment: '(登場未正確譯出)', suggestion: '應譯為「出場」' });
  }
  if (hasBracketTouba && !zh.includes('[=登場]')) {
    issues.push({ type: 'Rule12_登場出場', fragment: '(登場未標注[=登場])', suggestion: '應標注「[=登場]」（保留原文，不是出場）' });
  }
  return issues;
}

function checkCard(card) {
  if (!card.skill_zh) return;
  const zh = card.skill_zh;
  const jp = card.skill_jp || '';
  const id = card.image_file || card.card_no;
  const cardIssues = [];

  const zhWithoutQuotedNames = stripQuotedNames(zh);

  // Rule 1: その後 → 之後（not 該後）
  if (zh.includes('該後')) {
    cardIssues.push({ type: 'Rule01_其後', fragment: '該後', suggestion: '改為「之後」' });
  }

  // Rule 2: 登場させられない → 不能出場（not 使其出場...不能）
  const r2match = zh.match(/使其出場[^。，「」]{0,10}(不能|無法)/);
  if (r2match) {
    cardIssues.push({ type: 'Rule02_使其出場', fragment: r2match[0], suggestion: '改為「不能出場」' });
  }
  // Also check JP: if jp has 登場させられない but zh doesn't convey the restriction at all。
  // 2026-07-25 逐筆核對發現：「しか...出場させられない」常見的正確譯法是「最多只能出場N名」
  // 或「不能從手牌出場」這種中間夾了名詞/數量詞的句型，原本只認字面「不能出場」/「無法出場」
  // 連續四個字，把這些正確翻譯全部誤判成漏翻——放寬成允許中間夾雜文字。
  const conveysRestriction = /不能[^。，]{0,10}出場|無法[^。，]{0,10}出場|只能[^。，]{0,10}出場/.test(zh);
  if (jp.includes('させられない') && !conveysRestriction) {
    if (!r2match) { // avoid double counting
      cardIssues.push({ type: 'Rule02_使其出場', fragment: '(JP:させられない未正確譯出)', suggestion: '應譯為「不能出場」' });
    }
  }

  // Rule 3: たび → 出場時（not 每次/每當出場時）
  const r3match = zh.match(/(每次出場時|每當出場時)/);
  if (r3match) {
    cardIssues.push({ type: 'Rule03_每次出場', fragment: r3match[0], suggestion: '改為「出場時」' });
  }

  // Rule 4: 自己的從X區 → 從自己的X區
  const r4match = zh.match(/自己的從[^\s，。、「」]{1,8}區/);
  if (r4match) {
    cardIssues.push({ type: 'Rule04_自己的從X區', fragment: r4match[0], suggestion: '改為「從自己的X區」' });
  }

  // Rule 5: 對手的從X區 → 從對手的X區
  const r5match = zh.match(/對手的從[^\s，。、「」]{1,8}區/);
  if (r5match) {
    cardIssues.push({ type: 'Rule05_對手的從X區', fragment: r5match[0], suggestion: '改為「從對手的X區」' });
  }

  // Rule 6: 自己的在X區中 → 自己的X區中
  const r6match = zh.match(/自己的在[^\s，。、「」]{1,8}區中/);
  if (r6match) {
    cardIssues.push({ type: 'Rule06_自己的在X區', fragment: r6match[0], suggestion: '改為「自己的X區中」' });
  }

  // Rule 7: 再+N值 → 值再 +N（語序問題: 再+2攻擊值 instead of 攻擊值再+2）
  const r7match = zh.match(/再[+＋]\d+[攻攔接舉發進防][擊網球球球攻禦]?值/);
  if (r7match) {
    cardIssues.push({ type: 'Rule07_再N值語序', fragment: r7match[0], suggestion: '改為「X值再 +N」語序' });
  }

  // Rule 8: 防守點數 → 防禦值
  if (zh.includes('防守點數') || zh.includes('防守值')) {
    const m = zh.match(/(防守點數|防守值)/);
    cardIssues.push({ type: 'Rule08_防守點數', fragment: m[0], suggestion: '改為「防禦值」' });
  }

  // Rule 9: 選擇以下其中N項可發動的 → 選擇以下其中N項使用
  const r9match = zh.match(/選擇以下其中[一二三四五\d]+項可發動的/);
  if (r9match) {
    cardIssues.push({ type: 'Rule09_選擇發動', fragment: r9match[0], suggestion: '改為「選擇以下其中N項使用」' });
  }

  // Rule 10: で使える → 後可發動（not 時可使用）- only when NOT in a selection context
  const r10match = zh.match(/時可使用/);
  if (r10match && !zh.includes('選擇')) {
    cardIssues.push({ type: 'Rule10_時可使用', fragment: r10match[0], suggestion: '改為「後可發動」' });
  }

  // Rule 11: 值=N或以上/以下 → 值N或以上/以下（不加=）
  const r11match = zh.match(/值[=＝]\d+或以[上下]/);
  if (r11match) {
    cardIssues.push({ type: 'Rule11_值等於', fragment: r11match[0], suggestion: '移除「=」符號' });
  }

  // Term checks
  // 攻撃 (wrong char) → 攻擊。引號內是引用其他卡片的日文原名（例如「オープン攻撃」這張
  // Event 卡的本名），刻意保留不翻，不算漏翻——排除引號內容再檢查。
  if (zhWithoutQuotedNames.includes('攻撃')) {
    cardIssues.push({ type: '術語錯誤', fragment: '攻撃', suggestion: '改為「攻擊」(正體字)' });
  }

  // X點數/分數 where should be X值
  const wrongPoint = zh.match(/(舉球|接球|攔網|攻擊|發球|進攻|防禦)(點數|分數|分)/);
  if (wrongPoint) {
    cardIssues.push({ type: '術語錯誤', fragment: wrongPoint[0], suggestion: '改為「' + wrongPoint[1] + '值」' });
  }

  cardIssues.push(...checkOfficialTerms(zh, jp));
  cardIssues.push(...checkKanaResidue(zh));

  // "此角色是X角色" - check for missing 是
  // Pattern: 此角色舉球角色 or 此角色接球角色 (missing 是)
  const r_missing_shi = zh.match(/此角色(?!是|的|在|從|出場)(舉球|接球|攔網|攻擊|發球)角色/);
  if (r_missing_shi) {
    cardIssues.push({ type: '語法問題', fragment: r_missing_shi[0], suggestion: '應加入「是」字：「此角色是X角色」' });
  }

  if (cardIssues.length > 0) {
    for (const iss of cardIssues) stats[iss.type] = (stats[iss.type] || 0) + 1;
    issues.push({ source: 'skill', id, zh, jp, cardIssues });
  }
}

// QA 文字掃描（2026-08 新增）：card.qa[] 之前完全沒被這支腳本掃過，QA 全量重翻批次
// 出現的簡體字殘留、Event 用詞、登場/出場混用都是靠人工事後抽查才發現——不套用上面
// 11 條 skill 專屬 Rule（那些是針對 translate_skill() regex 鏈的已知 bug 寫的，QA 走
// 完全不同的 Google Translate + TERM_FIX 管線，硬套會製造大量噪音誤報），只跑通用的
// 殘留檢查、官方術語檢查、跟這次新增的登場/出場雙形式檢查。
function checkQaField(card, qaEntry, field) {
  const zh = qaEntry[field] || '';
  const jp = qaEntry[field + '_jp'] || '';
  if (!zh) return;

  const cardIssues = [
    ...checkOfficialTerms(zh, jp),
    ...checkKanaResidue(zh),
    ...checkAppearanceTerm(zh, jp),
  ];

  if (cardIssues.length > 0) {
    for (const iss of cardIssues) stats[iss.type] = (stats[iss.type] || 0) + 1;
    const id = (card.image_file || card.card_no) + ` / QA#${qaEntry.id}.${field}`;
    issues.push({ source: 'qa', id, zh, jp, cardIssues });
  }
}

function checkQaEntries(card) {
  for (const qaEntry of (card.qa || [])) {
    checkQaField(card, qaEntry, 'question');
    checkQaField(card, qaEntry, 'answer');
  }
}

cards.forEach(checkCard);
cards.forEach(checkQaEntries);

// Output results
console.log('\n========== 翻譯問題清單 ==========\n');
console.log('image_file | 問題類型 | 目前譯文（問題片段）| 建議修正');
console.log('-----------------------------------------------------------');

issues.forEach(card => {
  card.cardIssues.forEach(issue => {
    console.log(card.id + ' | ' + issue.type + ' | ' + issue.fragment + ' | ' + issue.suggestion);
  });
  console.log('  zh: ' + card.zh);
  if (card.jp) console.log('  jp: ' + card.jp);
  console.log('');
});

console.log('\n========== 統計 ==========\n');
let total = 0;
Object.entries(stats).forEach(([k, v]) => {
  if (v > 0) {
    console.log(k + ': ' + v + ' 筆');
    total += v;
  }
});
console.log('\n總問題數: ' + total);
console.log('有問題的卡片數: ' + issues.length);

// 2026-08 新增：以前這支腳本不管抓到幾個問題永遠 exit 0，SOP 步驟 7 寫著要跑它，
// 但沒有東西真的會因為它失敗——等於是個只會印出來、沒人保證會看的關卡。改成抓到
// 問題就 exit 1，才能真的擋下不合站內慣例的資料（跟 pytest/check_new_cards.py
// 一樣用 exit code 表達成功/失敗）。
process.exit(total > 0 ? 1 : 0);
