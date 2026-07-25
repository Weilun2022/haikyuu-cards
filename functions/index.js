// Cloud Function：牌組照片辨識。
//
// 前端把使用者上傳的牌組照片（base64）丟進來，這裡代為呼叫 Gemini Vision API
// （API key 只存在這裡，不落地到前端），跑兩段辨識：
//   Pass 1：讀照片，列出每一組卡片的角色名/卡號/張數猜測
//   Pass 2：從資料庫撈出每組角色名對應的候選卡圖版本，讓 Gemini 對照片再次比對，
//           選出實際是哪一個版本（同角色常有好幾種稀有度/插畫）
// 回傳結構化清單給前端，最終要不要採用、要怎麼修正，交給前端的確認畫面，
// 這裡不直接寫入任何使用者資料。
//
// 要求呼叫者已登入（沿用網站現有的 Google 登入），避免被匿名濫用打爆免費額度。
//
// GEMINI_API_KEY 用 functions/.env 帶入（純環境變數，不進 git），沒有用 Firebase
// Secret Manager（defineSecret）——那個功能得先把專案升級到 Blaze 付費方案才能用，
// 跟這個功能「盡量留在免費方案」的目標衝突。.env 一樣不會落地到前端，安全性對
// 個人專案這種規模來說已經足夠。

import { onCall, HttpsError } from 'firebase-functions/v2/https';
import { detectCardsInPhoto, verifyCardVariants } from './lib/gemini.js';
import { findCandidates, fetchImageBase64 } from './lib/cardLookup.js';

const MAX_IMAGE_BYTES = 8 * 1024 * 1024; // base64 前的概估上限，避免異常大檔浪費 token/流量
const MAX_CANDIDATES_PER_GROUP = 12;

export const scanDeckPhoto = onCall(
  { timeoutSeconds: 120, memory: '512MiB', cors: true },
  async (request) => {
    if (!request.auth) {
      throw new HttpsError('unauthenticated', '請先登入 Google 帳號才能使用照片辨識');
    }

    const { imageBase64, mimeType } = request.data || {};
    if (!imageBase64 || typeof imageBase64 !== 'string') {
      throw new HttpsError('invalid-argument', '缺少圖片資料');
    }
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(mimeType)) {
      throw new HttpsError('invalid-argument', '不支援的圖片格式');
    }
    if (imageBase64.length > MAX_IMAGE_BYTES * 1.4) {
      throw new HttpsError('invalid-argument', '圖片太大，請壓縮後再試（上限約 8MB）');
    }

    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      throw new HttpsError('failed-precondition', '伺服器未設定 GEMINI_API_KEY');
    }

    let groups;
    try {
      groups = await detectCardsInPhoto(apiKey, imageBase64, mimeType);
    } catch (e) {
      console.error('[scanDeckPhoto] pass1 failed', e);
      throw new HttpsError('internal', `辨識失敗：${e.message}`);
    }

    if (!groups.length) {
      return { groups: [] };
    }

    // 幫每組找候選版本、抓候選卡圖
    const candidatesByGroup = new Map();
    const candidateMetaById = new Map();
    let nextId = 0;

    for (let i = 0; i < groups.length; i++) {
      const g = groups[i];
      if (g.confidence === 'low' && (!g.name_jp || g.name_jp === '不明')) {
        candidatesByGroup.set(i, []);
        continue;
      }
      let dbCandidates = [];
      try {
        dbCandidates = await findCandidates(g.name_jp, MAX_CANDIDATES_PER_GROUP);
      } catch (e) {
        console.error('[scanDeckPhoto] cardLookup failed', e);
      }
      const withImages = [];
      for (const c of dbCandidates) {
        try {
          const base64 = await fetchImageBase64(c.image_file);
          const id = `c${nextId++}`;
          candidateMetaById.set(id, c);
          withImages.push({ id, card_no: c.card_no, image_file: c.image_file, base64 });
        } catch (e) {
          console.error('[scanDeckPhoto] fetchImage failed', c.image_file, e.message);
        }
      }
      candidatesByGroup.set(i, withImages);
    }

    const anyCandidates = [...candidatesByGroup.values()].some((c) => c.length > 0);
    let matches = [];
    if (anyCandidates) {
      try {
        matches = await verifyCardVariants(apiKey, imageBase64, mimeType, groups, candidatesByGroup);
      } catch (e) {
        console.error('[scanDeckPhoto] pass2 failed, falling back to pass1-only', e);
        matches = [];
      }
    }
    const matchByGroupIndex = new Map(matches.map((m) => [m.group_index, m]));

    const results = groups.map((g, i) => {
      const match = matchByGroupIndex.get(i);
      const candidates = candidatesByGroup.get(i) || [];
      const chosen = match?.best_candidate_id
        ? candidateMetaById.get(match.best_candidate_id)
        : null;
      return {
        name_jp: g.name_jp,
        art_hint: g.art_hint,
        confidence: g.confidence,
        count: match?.count ?? g.count,
        card_no: chosen?.card_no ?? g.card_no ?? null,
        image_file: chosen?.image_file ?? null,
        name_zh: chosen?.name_zh ?? null,
        resolved: !!chosen,
        // 沒選中任何候選時，把候選清單一起回傳，前端可以列出來讓使用者手動挑
        alternatives: chosen
          ? []
          : candidates.map((c) => ({ card_no: c.card_no, image_file: c.image_file })),
      };
    });

    return { groups: results };
  }
);
