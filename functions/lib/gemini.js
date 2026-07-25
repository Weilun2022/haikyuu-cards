// Gemini Vision API 包裝：Pass 1（讀照片列出每組卡片）+ Pass 2（用資料庫卡圖比對確認版本）。
// 兩次呼叫都用免費額度內的 Flash 模型，一次牌組照片掃描固定只打 2 次 API，不會因為卡片數量暴增。

const MODEL = 'gemini-3.5-flash';
const API_BASE = 'https://generativelanguage.googleapis.com/v1beta/models';

async function callGemini(apiKey, parts, responseSchema) {
  const url = `${API_BASE}/${MODEL}:generateContent?key=${apiKey}`;
  const body = {
    contents: [{ role: 'user', parts }],
    generationConfig: {
      responseMimeType: 'application/json',
      responseSchema,
    },
  };
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const json = await res.json();
  if (!res.ok) {
    const msg = json?.error?.message || res.statusText;
    throw new Error(`Gemini API 錯誤 (${res.status}): ${msg}`);
  }
  const text = json.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) throw new Error('Gemini 沒有回傳內容（可能被安全過濾擋掉）');
  return JSON.parse(text);
}

const PASS1_PROMPT = `這是日本卡牌遊戲「ハイキュー!! バボカ!! BREAK」（排球少年 BREAK）的牌組實體卡照片。
照片中卡片通常是插好透明卡套、平放在桌上，同一張卡的多張複本會疊在一起或呈扇形排列。

請仔細看過照片中「每一疊/每一組」卡片，針對每一組輸出：
- name_jp: 卡片上印的角色名（日文原文，例如「及川 徹」），如果是事件卡/非角色卡就填卡片標題文字
- card_no: 卡片左下角印的卡號（格式類似 "HV-P01-035" 或 "HV-D02-010"），如果反光/太小看不清楚就填 null，不要用猜的
- count: 這一組實際疊了幾張（數卡套的邊緣/厚度，不確定就給你最佳估計）
- art_hint: 簡短描述這張卡的插畫特徵（例如「灰階素描風格，跳躍扣球」、「彩色，微笑拿著手機」），這是為了之後跟資料庫圖片比對用的
- confidence: 你對這組辨識結果的信心，"high" / "medium" / "low"（完全看不清楚角色是誰就用 "low" 並在 name_jp 填「不明」，不要瞎猜名字）

只輸出照片裡實際看得到的卡片，不要漏看任何一組，也不要重複列同一組。`;

const PASS1_SCHEMA = {
  type: 'object',
  properties: {
    cards: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name_jp: { type: 'string' },
          card_no: { type: 'string', nullable: true },
          count: { type: 'integer' },
          art_hint: { type: 'string' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
        required: ['name_jp', 'count', 'art_hint', 'confidence'],
      },
    },
  },
  required: ['cards'],
};

export async function detectCardsInPhoto(apiKey, imageBase64, mimeType) {
  const parts = [
    { text: PASS1_PROMPT },
    { inline_data: { mime_type: mimeType, data: imageBase64 } },
  ];
  const result = await callGemini(apiKey, parts, PASS1_SCHEMA);
  return result.cards;
}

const PASS2_SCHEMA = {
  type: 'object',
  properties: {
    matches: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          group_index: { type: 'integer' },
          best_candidate_id: { type: 'string', nullable: true },
          count: { type: 'integer' },
        },
        required: ['group_index', 'count'],
      },
    },
  },
  required: ['matches'],
};

// groups: pass1 輸出的每一組（附上 index）
// candidatesByGroup: Map<group_index, [{id, card_no, image_file, name_zh, base64}]>
export async function verifyCardVariants(apiKey, imageBase64, mimeType, groups, candidatesByGroup) {
  const parts = [
    {
      text: `這是同一張排球少年卡牌照片。以下針對照片中每一組卡片，列出從資料庫查到的候選版本圖片
（同一個角色可能有好幾種不同插畫/稀有度）。請比對照片中該組卡片的實際畫面，
從候選中選出畫面最相符的那一個（用候選的 id），如果所有候選都對不上就把 best_candidate_id 設成 null。
同時請重新確認一次這組卡片的實際張數（count），你可以修正 Pass 1 猜錯的張數。

照片中第 0 組到第 ${groups.length - 1} 組分別是：\n` +
        groups.map((g, i) => `  第${i}組: ${g.name_jp}（${g.art_hint}，Pass1猜張數=${g.count}）`).join('\n'),
    },
    { inline_data: { mime_type: mimeType, data: imageBase64 } },
  ];

  for (const [groupIndex, candidates] of candidatesByGroup.entries()) {
    if (candidates.length === 0) continue;
    parts.push({ text: `\n第${groupIndex}組（${groups[groupIndex].name_jp}）的候選版本：` });
    for (const c of candidates) {
      parts.push({ text: `候選 id=${c.id}（card_no=${c.card_no}）：` });
      parts.push({ inline_data: { mime_type: 'image/webp', data: c.base64 } });
    }
  }
  parts.push({ text: '\n請針對每一組（group_index）給出 best_candidate_id 和修正後的 count。' });

  const result = await callGemini(apiKey, parts, PASS2_SCHEMA);
  return result.matches;
}
