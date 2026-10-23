// ana.js 與 ana-analysis.js 共用的建 DOM 小工具。
// 牌組名稱與帳號資料都是其他使用者自訂的不可信字串，一律走 textContent（append 字串就是
// textContent），不拼 innerHTML。

export function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') el.className = v;
    else if (k === 'style') el.style.cssText = v;
    else if (k === 'on') for (const [ev, fn] of Object.entries(v)) el.addEventListener(ev, fn);
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid);
  return el;
}

export const fmtDate = ms => ms
  ? new Date(ms).toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' })
  : '—';

export const fmtTime = ms =>
  new Date(ms).toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit', hour12: false });

export const pct = x => `${(x * 100).toFixed(1)}%`;
