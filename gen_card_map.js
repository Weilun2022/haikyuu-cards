// 執行方式：node gen_card_map.js
const fs = require('fs');

// 載入 cards_data.js
const vm = require('vm');
vm.runInThisContext(fs.readFileSync('cards_data.js', 'utf8'));

const rows = [['顯示名稱', 'id', '卡號', '角色名', '稀有度', '學校', '彈']];

for (const c of CARDS_DATA.cards) {
  const id     = c.image_file.replace('.webp', '');
  const label  = `${c.name} · ${c.rarity} · ${c.product_label || c.product_type}`;
  rows.push([label, id, c.card_no, c.name, c.rarity, c.school || '', c.product_label || c.product_type]);
}

const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g,'""')}"`).join(',')).join('\n');
fs.writeFileSync('card_map.csv', '﻿' + csv, 'utf8'); // BOM for Excel
console.log(`✅ 匯出 ${rows.length - 1} 張卡片 → card_map.csv`);
