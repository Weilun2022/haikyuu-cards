// 熱門學校標籤／卡名搜尋建議共用的卡片測試 fixture，供各自的自動化測試直接
// import 使用，不需要各自重新定義一份。欄位形狀對齊真實 cards_data.js
// （card_no/image_file 為「HV-{產品}-{序號}」+「-{稀有度代碼}.webp」，
// 同一個 card_no 可能對應多個 image_file 版本；name/name_zh/school/
// school_tags 沿用既有卡片資料格式）。每一筆都在下面註解說明對應要測的
// 邊界情況。
export const CARD_FIXTURES = [
  // 單一學校卡：只掛一個學校標籤，測「單校 +1」的基本情況。
  {
    image_file: 'HV-FIX-001-H.webp',
    card_no: 'HV-FIX-001',
    name: '日向 翔陽',
    name_zh: '日向翔陽',
    school: '烏野',
    school_tags: ['烏野'],
  },
  // 雙掛學校標籤卡：測雙掛卡的兩個學校要各自 +1，不是只算第一個。
  {
    image_file: 'HV-FIX-002-H.webp',
    card_no: 'HV-FIX-002',
    name: '風真 陸',
    name_zh: '風真陸',
    school: '烏野',
    school_tags: ['烏野', '音駒'],
  },
  // ユース 標籤卡：測白名單內的特殊分類（非固定校隊）也能正常被計入/顯示，
  // 不會被誤判成「不合法 key」。
  {
    image_file: 'HV-FIX-003-H.webp',
    card_no: 'HV-FIX-003',
    name: '及川 徹',
    name_zh: '及川徹',
    school: 'ユース',
    school_tags: ['ユース'],
  },
  // 疑似ユース 標籤卡：測另一個特殊分類跟 ユース 是各自獨立的 key，
  // 不會被合併計數或互相覆蓋。
  {
    image_file: 'HV-FIX-004-H.webp',
    card_no: 'HV-FIX-004',
    name: '影山 飛雄',
    name_zh: '影山飛雄',
    school: '疑似ユース',
    school_tags: ['疑似ユース'],
  },
  // 同名不同版本卡 + 全形/半形空格差異（三筆都是同一個角色「宮侑」，
  // card_no 各自不同，name_zh 分別用「無空格」「半形空格」「全形空格」
  // 三種寫法）：測卡名建議去重邏輯要在「去除空白後比對」時把這三筆合併成
  // 同一筆建議，而不是各自列出三筆。
  {
    image_file: 'HV-FIX-005-H.webp',
    card_no: 'HV-FIX-005A',
    name: '宮 侑',
    name_zh: '宮侑',
    school: '稲荷崎',
    school_tags: ['稲荷崎'],
  },
  {
    image_file: 'HV-FIX-006-I.webp',
    card_no: 'HV-FIX-005B',
    name: '宮 侑',
    name_zh: '宮 侑',
    school: '稲荷崎',
    school_tags: ['稲荷崎'],
  },
  {
    image_file: 'HV-FIX-007-IP.webp',
    card_no: 'HV-FIX-005C',
    name: '宮 侑',
    name_zh: '宮　侑',
    school: '稲荷崎',
    school_tags: ['稲荷崎'],
  },
];
