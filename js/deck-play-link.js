// 牌組面板「🏐 AI對練」按鈕：把目前牌組用分享連結格式（?deck=，同 index.html 的 encodeDeck）
// 帶到第三方的 BREAK 對練台。刻意不碰 DOM，讓 node:test 能把門檻與網址釘住。
//
// 門檻照對練台的匯入檢查，不是我們網站的規則：我們的牌組面板不限上限也不擋事件卡，
// 但對練台只收剛好 40 張、事件卡最多 8 張，不合格的牌組帶過去只會被它拒絕。
// 分享碼的格式約定寫在 index.html 的 encodeDeck 旁邊。

// 對方確認這是固定網址（不會再變）；全站只有這裡寫死它
const PLAY_BASE = 'https://haikyuu-playmat.web.app/break-v9.5/';
const DECK_SIZE = 40;
const EVENT_MAX = 8;

export function deckPlayStatus({ total, events }) {
  const label = total < DECK_SIZE ? `還差 ${DECK_SIZE - total} 張`
    : total > DECK_SIZE ? `多 ${total - DECK_SIZE} 張`
    : events > EVENT_MAX ? `事件卡多 ${events - EVENT_MAX} 張`
    : null;
  if (label) {
    return {
      ready: false, label,
      reason: `對練台需要剛好 ${DECK_SIZE} 張、事件卡最多 ${EVENT_MAX} 張（目前 ${total} 張，事件卡 ${events} 張）`,
    };
  }
  return {
    ready: true, label: '🏐 AI對練',
    reason: '用這副牌到 BREAK 對練台跟 AI 對練（另開外部網站 haikyuu-playmat.web.app）',
  };
}

export function deckPlayUrl(encodedDeck) {
  return `${PLAY_BASE}?deck=${encodedDeck}`;
}
