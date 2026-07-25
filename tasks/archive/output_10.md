# output_10 — 庫存分析：缺牌排序 + 分段顯示

## CSS 新增

加在 `.an-need-badge` 區塊後面（約第 1144 行之後）：

```css
.analysis-section-header {
  grid-column: 1 / -1;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-dim);
  padding: 8px 4px 4px;
  border-bottom: 1px solid var(--border);
  margin-top: 4px;
}
```

---

## renderAnalysis() 完整替換

從 `function renderAnalysis() {` 到最後的 `}` 替換為：

```js
function renderAnalysis() {
  const deck = getCurrentDeck();
  if (!deck) return;
  document.getElementById('analysis-title').textContent = `庫存分析 — ${deck.name}`;

  // 缺牌數 = Σ max(0, 牌組需要 − 此牌組的持有數)
  const total = getTotalCount(deck);
  const owned = getDeckOwned();   // 此牌組專屬持有資料（以 image_file 為 key）
  let missing = 0;
  deck.cards.forEach(e => {
    missing += Math.max(0, e.count - (owned[e.image_file] || 0));
  });
  document.getElementById('analysis-total').textContent   = total;
  document.getElementById('analysis-missing').textContent = missing;

  const body = document.getElementById('analysis-body');
  body.innerHTML = '';

  // 先算出每張卡的 deficit，再排序
  const entries = deck.cards.map(entry => {
    const card = cards.find(c => c.image_file === entry.image_file);
    if (!card) return null;
    const have    = owned[entry.image_file] || 0;
    const need    = entry.count;
    const deficit = Math.max(0, need - have);
    return { entry, card, have, need, deficit };
  }).filter(Boolean);

  // deficit > 0 排前面（降冪），deficit = 0 排後面
  const incomplete = entries.filter(e => e.deficit > 0).sort((a, b) => b.deficit - a.deficit);
  const complete   = entries.filter(e => e.deficit === 0);

  const renderSection = (list, label) => {
    if (list.length === 0) return;

    // Section header
    const header = document.createElement('div');
    header.className = 'analysis-section-header';
    header.textContent = `${label}（${list.length}張）`;
    body.appendChild(header);

    list.forEach(({ entry, card, have, need, deficit }) => {
      const state  = have >= need ? 'owned' : have > 0 ? 'partial' : 'not-owned';
      const imgSrc = card.image_file ? `images/${card.image_file}` : '';
      const variant = getVariantCode(entry.image_file);
      const displayName = (card.card_no || '') + (variant ? `-${variant}` : '');
      const badgeText = deficit > 0 ? `缺${deficit}` : '✓';

      const div = document.createElement('div');
      div.className = `an-card ${state}`;
      div.innerHTML = `
        <img class="an-card-img" src="${imgSrc}" alt="" onerror="this.style.background='var(--surface2)'">
        <div class="an-own-counter">
          <input type="number" class="an-count-input" data-img="${entry.image_file}" data-need="${need}" value="${have}" min="0" title="持有數（需要 ${need} 張）">
        </div>
        <div class="an-need-badge">${badgeText}</div>
        <div class="an-card-name">${displayName}</div>`;

      div.querySelector('.an-count-input').addEventListener('click', e => e.stopPropagation());
      div.querySelector('.an-count-input').addEventListener('focus', e => { e.stopPropagation(); e.target.value = ''; });

      // 共用的儲存邏輯：change（含 Enter）或 blur（離開欄位）都觸發
      const saveAnCount = e => {
        e.stopPropagation();
        const img = e.target.dataset.img;
        const valStr = e.target.value.trim();
        if (valStr === '') {
          // focus 清空後未輸入就離開，還原原本持有數，不存 0
          e.target.value = deck.owned[img] || 0;
          return;
        }
        const val = parseInt(valStr, 10);
        deck.owned[img] = isNaN(val) || val < 0 ? 0 : val;
        e.target.value = deck.owned[img];   // 修正顯示（如輸入負數）
        saveDecks();
        // 更新此卡的 state class（不 re-render 整頁，避免失焦）
        const have2 = deck.owned[img] || 0;
        const need2 = parseInt(e.target.dataset.need, 10);
        div.className = `an-card ${have2 >= need2 ? 'owned' : have2 > 0 ? 'partial' : 'not-owned'}`;
        // 更新此卡的 badge 顯示
        const deficit2 = Math.max(0, need2 - have2);
        div.querySelector('.an-need-badge').textContent = deficit2 > 0 ? `缺${deficit2}` : '✓';
        // 更新標頭統計
        let missing2 = 0;
        deck.cards.forEach(en => { missing2 += Math.max(0, en.count - (deck.owned[en.image_file] || 0)); });
        document.getElementById('analysis-missing').textContent = missing2;
      };
      div.querySelector('.an-count-input').addEventListener('change', saveAnCount);
      div.querySelector('.an-count-input').addEventListener('blur',   saveAnCount);
      div.querySelector('.an-count-input').addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); saveAnCount(e); e.target.blur(); }
      });
      div.addEventListener('click', () => openModal(card));
      body.appendChild(div);
    });
  };

  renderSection(incomplete, '未完成');
  renderSection(complete,   '已完成');
}
```
