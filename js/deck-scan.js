// 牌組照片辨識（半自動）：使用者上傳任意來源的牌組照片，後端 Cloud Function 呼叫
// Gemini Vision API 辨識卡片名稱/卡號/張數，這裡負責畫確認畫面讓使用者逐組核對/修正，
// 確認後才真的組成牌組。所有辨識結果在使用者按下「建立牌組」前都不會動到 localStorage。
//
// 依賴 window.hvCloudSync 的 Firebase app（見 cloud-sync.js），共用同一個已登入的使用者。

import { app } from './cloud-sync.js';
import { getFunctions, httpsCallable } from 'https://www.gstatic.com/firebasejs/10.12.4/firebase-functions.js';

const functions = getFunctions(app);
const scanDeckPhotoFn = httpsCallable(functions, 'scanDeckPhoto');

let _state = null;

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      resolve(result.slice(result.indexOf(',') + 1));
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function el(id) { return document.getElementById(id); }

async function open(file, { onImportDeck, allCards } = {}) {
  if (!window.hvCloudSync?.currentUser) {
    window.showToast?.('請先登入 Google 帳號才能使用照片辨識');
    return;
  }

  const overlay = el('deck-scan-overlay');
  const status = el('deck-scan-status');
  overlay.classList.add('open');
  el('deck-scan-body').innerHTML = '';
  status.textContent = '辨識中，請稍候…（約需 20-60 秒，視照片卡片數量而定）';
  el('deck-scan-confirm-btn').disabled = true;

  try {
    const base64 = await fileToBase64(file);
    const mimeType = file.type || 'image/jpeg';
    const res = await scanDeckPhotoFn({ imageBase64: base64, mimeType });
    const groups = res.data?.groups || [];

    if (!groups.length) {
      status.textContent = '沒有在照片中辨識到任何卡片，請確認照片或改用手動建立牌組';
      return;
    }

    _state = {
      onImportDeck,
      allCards: allCards || [],
      items: groups.map((g, i) => ({
        id: `g${i}`,
        excluded: g.confidence === 'low' && !g.image_file,
        card_no: g.card_no,
        image_file: g.image_file,
        name_zh: g.name_zh,
        name_jp: g.name_jp,
        confidence: g.confidence,
        count: Math.max(1, g.count || 1),
        alternatives: g.alternatives || [],
      })),
    };
    render();
    status.textContent = `辨識到 ${_state.items.length} 組卡片，請核對名稱/版本/張數後再建立牌組（不確定的已用淺色標出）`;
    el('deck-scan-confirm-btn').disabled = false;
  } catch (e) {
    console.error('[deck-scan] scan failed', e);
    status.textContent = `辨識失敗：${e.message || e}${e.code === 'functions/unauthenticated' ? '（請先登入）' : ''}`;
  }
}

function close() {
  el('deck-scan-overlay').classList.remove('open');
  _state = null;
}

function render() {
  const body = el('deck-scan-body');
  body.innerHTML = '';

  for (const item of _state.items) {
    const row = document.createElement('div');
    row.className = 'scan-row' + (item.excluded ? ' excluded' : '');

    const thumbHtml = item.image_file
      ? `<img class="scan-thumb" src="images/${item.image_file}" alt="">`
      : `<div class="scan-thumb-placeholder">未確認<br>版本</div>`;

    const confBadge = item.confidence === 'low'
      ? '<span class="scan-confidence-low">（信心度低）</span>'
      : '';

    row.innerHTML = `
      ${thumbHtml}
      <div class="scan-info">
        <div class="scan-name">${item.name_zh || item.name_jp}</div>
        <div class="scan-meta">${item.card_no || item.name_jp}${confBadge}</div>
        <div class="scan-alts" style="${item.alternatives.length ? '' : 'display:none'}"></div>
      </div>
      <div class="scan-controls">
        <button class="scan-remove-btn" title="移除這組">✕</button>
        <input type="number" class="scan-count-input" min="0" max="40" value="${item.count}">
      </div>
    `;

    const altsWrap = row.querySelector('.scan-alts');
    for (const alt of item.alternatives) {
      const img = document.createElement('img');
      img.className = 'scan-alt-thumb';
      img.src = `images/${alt.image_file}`;
      img.title = alt.card_no;
      img.addEventListener('click', () => {
        item.card_no = alt.card_no;
        item.image_file = alt.image_file;
        item.excluded = false;
        render();
      });
      altsWrap.appendChild(img);
    }

    row.querySelector('.scan-remove-btn').addEventListener('click', () => {
      item.excluded = !item.excluded;
      render();
    });
    row.querySelector('.scan-count-input').addEventListener('input', (e) => {
      item.count = Math.max(0, parseInt(e.target.value, 10) || 0);
    });

    body.appendChild(row);
  }

  renderManualAdd(body);
}

function renderManualAdd(body) {
  const wrap = document.createElement('div');
  wrap.className = 'scan-manual-add';
  wrap.innerHTML = `<input type="text" placeholder="漏抓的卡？輸入卡名手動加入…">`;
  const resultsBox = document.createElement('div');
  resultsBox.className = 'scan-manual-results';

  const input = wrap.querySelector('input');
  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    resultsBox.innerHTML = '';
    if (!q) return;
    const matches = (_state.allCards || [])
      .filter(c => (c.name_zh || '').toLowerCase().includes(q) || (c.card_no || '').toLowerCase().includes(q))
      .slice(0, 15);
    for (const c of matches) {
      const item = document.createElement('div');
      item.className = 'scan-manual-result-item';
      item.innerHTML = `<img class="scan-alt-thumb" src="images/${c.image_file}"><span>${c.name_zh}（${c.card_no}）</span>`;
      item.addEventListener('click', () => {
        _state.items.push({
          id: `manual${Date.now()}`,
          excluded: false,
          card_no: c.card_no,
          image_file: c.image_file,
          name_zh: c.name_zh,
          name_jp: c.name,
          confidence: 'manual',
          count: 1,
          alternatives: [],
        });
        input.value = '';
        render();
      });
      resultsBox.appendChild(item);
    }
  });

  body.appendChild(wrap);
  body.appendChild(resultsBox);
}

function confirmImport() {
  if (!_state) return;
  const cards = _state.items
    .filter(it => !it.excluded && it.count > 0 && it.image_file)
    .map(it => ({ image_file: it.image_file, card_no: it.card_no, count: it.count }));

  if (!cards.length) {
    window.showToast?.('沒有可匯入的卡片（至少要有一組確認過版本）');
    return;
  }
  const onImportDeck = _state.onImportDeck;
  close();
  onImportDeck?.(cards);
}

el('deck-scan-cancel-btn').addEventListener('click', close);
el('deck-scan-confirm-btn').addEventListener('click', confirmImport);

window.hvDeckScan = { open };
