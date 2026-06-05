/**
 * AI 審圖助手 — OpenRouter 多模型連接器
 *
 * 使用方式:
 *   const reviewer = require('./review_ai');
 *   const result   = await reviewer.reviewCard(imageBase64OrUrl, contextText);
 *
 * 環境變數:
 *   OPENROUTER_KEY  — 必填
 *   REVIEW_MODEL    — 可選，預設 deepseek/deepseek-v4-flash
 *   REVIEW_MODEL_VISION — 可選，Vision 專用模型（預設與 REVIEW_MODEL 相同）
 */

"use strict";

const BASE_URL = "https://openrouter.ai/api/v1";

// ── 設定 ────────────────────────────────────────────────────────────────────

const CONFIG = {
  apiKey:       process.env.OPENROUTER_KEY ?? "",
  model:        process.env.REVIEW_MODEL ?? "deepseek/deepseek-v4-flash",
  visionModel:  process.env.REVIEW_MODEL_VISION ?? (process.env.REVIEW_MODEL ?? "deepseek/deepseek-v4-flash"),
  siteUrl:      process.env.SITE_URL ?? "https://github.com/weilun2022/haikyuu-cards",
  maxTokens:    512,
};

// ── 低階 API 呼叫 ────────────────────────────────────────────────────────────

async function _call(model, messages, maxTokens = CONFIG.maxTokens) {
  if (!CONFIG.apiKey) throw new Error("OPENROUTER_KEY 環境變數未設定");

  const res = await fetch(`${BASE_URL}/chat/completions`, {
    method:  "POST",
    headers: {
      "Authorization": `Bearer ${CONFIG.apiKey}`,
      "Content-Type":  "application/json",
      "HTTP-Referer":  CONFIG.siteUrl,
      "X-Title":       "Haikyuu Cards Reviewer",
    },
    body: JSON.stringify({ model, messages, max_tokens: maxTokens }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`OpenRouter ${res.status}: ${body}`);
  }

  const data = await res.json();
  if (data.error) throw new Error(`OpenRouter error: ${JSON.stringify(data.error)}`);
  return data.choices?.[0]?.message?.content ?? "";
}

// ── 公開 API ─────────────────────────────────────────────────────────────────

/**
 * testText() — 測試文字連線
 * @returns {{ ok: boolean, reply: string, model: string }}
 */
async function testText() {
  const reply = await _call(CONFIG.model, [
    { role: "user", content: "Reply with exactly: TEXT_OK" },
  ], 16);
  return { ok: reply.includes("TEXT_OK"), reply: reply.trim(), model: CONFIG.model };
}

/**
 * testVision() — 測試 Vision 圖像輸入
 * @param {string} [imageB64] base64 PNG；省略則使用內建 1×1 白色測試圖
 * @returns {{ ok: boolean, reply: string, model: string }}
 */
async function testVision(imageB64) {
  const TINY_PNG =
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";
  const b64 = imageB64 ?? TINY_PNG;
  const url = b64.startsWith("http") ? b64 : `data:image/png;base64,${b64}`;

  const reply = await _call(CONFIG.visionModel, [{
    role: "user",
    content: [
      { type: "image_url", image_url: { url } },
      { type: "text",      text: "Describe this image in one sentence." },
    ],
  }]);
  return { ok: reply.length > 0, reply: reply.trim(), model: CONFIG.visionModel };
}

/**
 * reviewCard() — 主要審圖函式
 *
 * @param {string}  imageInput  — base64 字串 或 https:// 圖片網址
 * @param {string}  [context]   — 可選：提供卡片名稱 / 學校 / 技能文字供參考
 * @returns {Promise<ReviewResult>}
 */
async function reviewCard(imageInput, context = "") {
  const url = imageInput.startsWith("http")
    ? imageInput
    : `data:image/png;base64,${imageInput}`;

  const systemPrompt = [
    "You are a trading card game (TCG) card reviewer for the volleyball anime TCG 'バボカ!! BREAK'.",
    "Analyze the card image and provide structured feedback.",
    "Always respond in Traditional Chinese (繁體中文).",
  ].join(" ");

  const userContent = [
    {
      type: "image_url",
      image_url: { url },
    },
    {
      type: "text",
      text: [
        context ? `卡片資訊：${context}\n` : "",
        "請審查這張卡片並回傳以下 JSON 格式（不要有 markdown 包裝）：",
        "{",
        '  "card_name": "卡片名稱",',
        '  "category": "CHARACTER | EVENT",',
        '  "stats_read": { "atk": 0, "blk": 0, "rcv": 0, "srv": 0, "tos": 0 },',
        '  "skill_summary": "技能效果摘要（1-2句）",',
        '  "synergy_notes": "連動建議（可能的搭配角色或事件）",',
        '  "rating": 1~5,',
        '  "rating_reason": "評分理由"',
        "}",
      ].join("\n"),
    },
  ];

  const raw = await _call(CONFIG.visionModel, [
    { role: "system", content: systemPrompt },
    { role: "user",   content: userContent },
  ]);

  // Try to parse JSON; fall back to raw text if model returns prose
  let parsed = null;
  try {
    const jsonStr = raw.replace(/^```json\s*/i, "").replace(/```\s*$/, "");
    parsed = JSON.parse(jsonStr);
  } catch {
    // model doesn't support vision or returned non-JSON
    parsed = { raw_response: raw };
  }

  return {
    model:    CONFIG.visionModel,
    success:  parsed && !parsed.raw_response,
    result:   parsed,
  };
}

// ── CLI 快速測試 ─────────────────────────────────────────────────────────────

if (require.main === module) {
  (async () => {
    const key = process.env.OPENROUTER_KEY;
    if (!key) {
      console.error("❌ 請設定環境變數 OPENROUTER_KEY");
      process.exit(1);
    }

    console.log("=== review_ai.js 自我測試 ===");
    console.log(`模型（文字）: ${CONFIG.model}`);
    console.log(`模型（視覺）: ${CONFIG.visionModel}`);

    let textOk = false, visionOk = false;

    try {
      const t = await testText();
      textOk = t.ok;
      console.log(`\n[1] 文字測試: ${t.ok ? "✅ PASS" : "⚠️  回應異常"}`);
      console.log(`    回應: ${t.reply}`);
    } catch (e) {
      console.log(`\n[1] 文字測試: ❌ FAIL — ${e.message}`);
    }

    try {
      const v = await testVision();
      visionOk = v.ok;
      console.log(`\n[2] Vision 測試: ${v.ok ? "✅ PASS" : "❌ FAIL"}`);
      console.log(`    回應: ${v.reply}`);
    } catch (e) {
      console.log(`\n[2] Vision 測試: ❌ FAIL — ${e.message}`);
      console.log(`    → 此模型可能不支援圖像輸入，請改用 REVIEW_MODEL_VISION 指定 Vision 模型`);
    }

    console.log("\n=== 測試結果 ===");
    console.log(`  文字: ${textOk   ? "✅ 通過" : "❌ 失敗"}`);
    console.log(`  圖像: ${visionOk ? "✅ 通過" : "❌ 失敗（或不支援）"}`);
    console.log(textOk
      ? "\n✅ 模型可用，review_ai.js 可接入三方協作系統。"
      : "\n❌ 請確認 OPENROUTER_KEY 及 Allowed Origins 設定後重試。"
    );

    process.exit(textOk ? 0 : 1);
  })();
}

module.exports = { testText, testVision, reviewCard, CONFIG };
