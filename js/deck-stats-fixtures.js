// A 線統計（deck-stats-model.js）測試用的卡片 fixture。
// 跟 card-fixtures.js 分開：那份是給熱門學校／卡名建議用的，沒有 category 與五維數值，
// 而這裡每一條規格（只算角色卡、未知值不當零、同卡號多版本）都需要那些欄位。
// 欄位形狀對齊真實 cards_data.js（category 是 'CHARACTER' / 'EVENT'，五維可能是 null）。
export const STATS_CARDS = [
  // 單校角色卡，五維齊全
  { image_file: 'K1-H.webp', card_no: 'HV-T01-001', name: '甲一', name_zh: '甲一', category: 'CHARACTER',
    category_zh: '角色', school: '烏野', school_tags: ['烏野'], srv: 2, blk: 3, rcv: 4, tos: 0, atk: 2 },
  // 同一個 card_no 的第二個稀有度版本：指紋與向量都要併成同一張卡
  { image_file: 'K1-I.webp', card_no: 'HV-T01-001', name: '甲一', name_zh: '甲一', category: 'CHARACTER',
    category_zh: '角色', school: '烏野', school_tags: ['烏野'], srv: 2, blk: 3, rcv: 4, tos: 0, atk: 2 },
  { image_file: 'K2-H.webp', card_no: 'HV-T01-002', name: '甲二', name_zh: '甲二', category: 'CHARACTER',
    category_zh: '角色', school: '烏野', school_tags: ['烏野'], srv: 1, blk: 1, rcv: 6, tos: 0, atk: 1 },
  { image_file: 'K3-H.webp', card_no: 'HV-T01-003', name: '甲三', name_zh: '甲三', category: 'CHARACTER',
    category_zh: '角色', school: '烏野', school_tags: ['烏野'], srv: 3, blk: 2, rcv: 2, tos: 5, atk: 1 },
  // 雙掛學校的角色卡：每校各得 n/2 分
  { image_file: 'M1-H.webp', card_no: 'HV-T01-011', name: '乙一', name_zh: '乙一', category: 'CHARACTER',
    category_zh: '角色', school: '音駒', school_tags: ['烏野', '音駒'], srv: 2, blk: 2, rcv: 3, tos: 0, atk: 3 },
  { image_file: 'N1-H.webp', card_no: 'HV-T01-021', name: '丙一', name_zh: '丙一', category: 'CHARACTER',
    category_zh: '角色', school: '音駒', school_tags: ['音駒'], srv: 1, blk: 4, rcv: 2, tos: 0, atk: 4 },
  { image_file: 'N2-H.webp', card_no: 'HV-T01-022', name: '丙二', name_zh: '丙二', category: 'CHARACTER',
    category_zh: '角色', school: '音駒', school_tags: ['音駒'], srv: 1, blk: 5, rcv: 1, tos: 0, atk: 5 },
  // ユース 與 疑似ユース 是兩個獨立標記，不可合併
  { image_file: 'Y1-H.webp', card_no: 'HV-T01-031', name: '丁一', name_zh: '丁一', category: 'CHARACTER',
    category_zh: '角色', school: 'ユース', school_tags: ['ユース'], srv: 4, blk: 4, rcv: 4, tos: 4, atk: 4 },
  { image_file: 'Y2-H.webp', card_no: 'HV-T01-032', name: '丁二', name_zh: '丁二', category: 'CHARACTER',
    category_zh: '角色', school: '疑似ユース', school_tags: ['疑似ユース'], srv: 3, blk: 3, rcv: 3, tos: 3, atk: 3 },
  // 網站側卡表才有的 町内会 標記（計算側卡表還沒有，見計畫 §3.3）
  { image_file: 'C1-H.webp', card_no: 'HV-T01-041', name: '戊一', name_zh: '戊一', category: 'CHARACTER',
    category_zh: '角色', school: '町内会', school_tags: ['町内会'], srv: 1, blk: 1, rcv: 1, tos: 1, atk: 1 },
  // 五維是 null 的角色卡（真實資料有 57 張）：不可當 0
  { image_file: 'X1-H.webp', card_no: 'HV-T01-051', name: '己一', name_zh: '己一', category: 'CHARACTER',
    category_zh: '角色', school: '烏野', school_tags: ['烏野'], srv: null, blk: null, rcv: null, tos: null, atk: null },
  // 完全沒有學校標記的角色卡：算「未知歸屬」，不重分配到其他學校
  { image_file: 'U1-H.webp', card_no: 'HV-T01-061', name: '庚一', name_zh: '庚一', category: 'CHARACTER',
    category_zh: '角色', school: '', school_tags: [], srv: 2, blk: 2, rcv: 2, tos: 2, atk: 2 },
  // 事件卡：學校不計、五維是 null
  { image_file: 'E1-H.webp', card_no: 'HV-T01-071', name: '事件一', name_zh: '事件一', category: 'EVENT',
    category_zh: '事件', school: '烏野', school_tags: ['烏野'], srv: null, blk: null, rcv: null, tos: null, atk: null },
  { image_file: 'E2-H.webp', card_no: 'HV-T01-072', name: '事件二', name_zh: '事件二', category: 'EVENT',
    category_zh: '事件', school: '音駒', school_tags: ['音駒'], srv: null, blk: null, rcv: null, tos: null, atk: null },
];
