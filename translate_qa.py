"""
translate_qa.py
翻譯 qa_data.json → qa_data_zh.json
流程：Pre-process（人名保護）→ Google 翻譯 → 術語覆寫 → 輸出
本地工具，不進 git。

════════════════════════════════════════════════════════════════
  TERM_FIX 問題記錄（已修正，供未來維護參考）
════════════════════════════════════════════════════════════════

Google Translate (ja→zh-TW) 對以下術語有系統性誤譯，
需在翻譯後套用 TERM_FIX 覆寫。新增覆寫前請先閱讀【一般維護原則】。

【問題 A】區域名稱：Google 附加多餘「域」字
  症狀：「アタックエリア」→「攻擊區域」（應為「攻擊區」）
  根因：Google 把 エリア→「區域」，本站統一用「區」（不含「域」）
  覆寫：攻擊/舉球/攔網/接球/發球/棄牌 共 6 條「X區域」→「X區」
  ─────────────────────────────────────────────────────────────

【問題 B】Guts 多種誤譯
  症狀：「ガッツ」→「膽量」/「勇氣」/「鬥志」（應保留英文 Guts）
  根因：Google 將「ガッツ」按語意翻成情感詞，忽略其遊戲術語身份
  覆寫：膽量→Guts、勇氣→Guts、鬥志→Guts（共 3 條）
  ─────────────────────────────────────────────────────────────

【問題 C】數值詞尾：「點」vs「值」
  症狀：「アタックポイント」→「攻擊點」（應為「攻擊值」）
  根因：Google 將 ポイント→「點」，本站統一用「值」
  覆寫：攻擊點/接收值/接收點/進攻點/發球點/舉球點/防守點 共 9 條
  ─────────────────────────────────────────────────────────────

【問題 D】攔網系列：ブロック 多種誤譯
  症狀：「ブロック」→「格擋」/「阻擋」/「區塊」（應為「攔網」）
  根因：ブロック 在不同上下文中 Google 給出不同中文對應詞
  覆寫：格擋/阻擋/區塊 三系列各含「-階段/-點/-區域/-成功」共 11 條
  注意：長詞必須寫在短詞之前（「格擋階段」→「格擋」才能正確匹配）
        順序錯誤會導致「格擋階段」先被「格擋」→「攔網」吃掉，
        變成「攔網階段」無法再被修正（雖然結果剛好一樣，但邏輯應正確）
  ─────────────────────────────────────────────────────────────

【問題 E】登場 vs 出場
  症狀：「登場」被保留（應翻為「出場」）
  根因：Google 有時直接保留漢字「登場」不作翻譯
  覆寫：登場→出場
  附帶：「出現」系列也需覆寫（不能出現→無法出場 等 3 條）
  ─────────────────────────────────────────────────────────────

【問題 F】元々の → 原本（2026-04 發現）
  症狀：「"元々の"とはどういう意味ですか？」→「「原創」是什麼意思？」
  根因：「元々の」語意為「卡片上印刷的原始數值」，Google 翻成「原創」
        （原創作品義）；技能敘述中同一概念用「原本」，術語不一致
  影響：6 筆 Q&A（HV-P01-002/019、HV-P02-060/061/081/096）
  處理：qa_data_zh.json 直接修正 6 筆；TERM_FIX 防未來重跑再出錯
  覆寫：原創→原本
  ─────────────────────────────────────────────────────────────

【問題 G】第一人稱語氣殘留
  症狀：日文 Q&A 文體帶主詞「私は」，Google 翻成「我」殘留在答案中
  根因：規則裁定文本不該有主詞，但 Google 忠實還原日文句型
  覆寫：不，我→不，；是，我→是，（共 2 條）
  ─────────────────────────────────────────────────────────────

【一般維護原則】
  1. TERM_FIX 每個類別內，長詞（組合詞）必須寫在短詞之前，
     避免短詞先匹配截斷長詞（特殊 > 一般）
  2. 判斷新問題該加哪裡：
     - Google 系統性誤譯（多張卡重複出現）→ 加 TERM_FIX
     - 個別 Q&A 翻錯（邏輯或語境問題）→ 直接改 qa_data_zh.json
  3. 修改 qa_data_zh.json 後只需重跑 build_data.py（不用重跑 Google 翻譯）
  4. 重跑 Google 翻譯（translate_qa.py）前，確認 TERM_FIX 已涵蓋所有已知問題，
     否則修正過的 qa_data_zh.json 條目會被新的錯誤翻譯覆蓋
  5. 人名保護使用 <<<N0>>> 格式佔位符，還原後再套 TERM_FIX；
     若人名含術語字（如「登場」）不會被 TERM_FIX 污染，因為還原在 TERM_FIX 之前
════════════════════════════════════════════════════════════════
"""

import json
import re
import sys
import time

from deep_translator import GoogleTranslator

# ── 路徑 ──────────────────────────────────────────────────────────────────
QA_SRC   = r'haikyuu_output/qa_data.json'
QA_DST   = r'haikyuu_output/qa_data_zh.json'
CARDS_JS = r'cards_data.js'

# ── 參數 ──────────────────────────────────────────────────────────────────
DELAY        = 0.5   # 每次請求後等待秒數
RETRY        = 2     # 失敗重試次數
RETRY_DELAY  = 2.0   # 重試等待秒數

# ── 術語覆寫表（Google 譯文 → 本站術語） ──────────────────────────────────
TERM_FIX = {
    # 區域
    '攻擊區域': '攻擊區',
    '投擲區域': '舉球區',
    '街區區域': '攔網區',
    '接收區域': '接球區',
    '發球區域': '發球區',
    '放置區域': '棄牌區',
    '丟棄區域': '棄牌區',
    # Guts
    '膽量': 'Guts',
    '勇氣': 'Guts',
    '鬥志': 'Guts',
    # 數值
    '攻擊點': '攻擊值',
    '防守值': '防禦值',
    '防守點': '防禦值',
    '阻擋值': '攔網值',
    '接收值': '接球值',
    '發球點': '發球值',
    '舉球點': '舉球值',
    # 進攻／防守（長詞先）
    '進攻點數': '進攻值',
    '進攻點': '進攻值',
    '接收點': '接球值',
    # 攔網系列（長詞先）
    '格擋階段': '攔網階段',
    '格擋點': '攔網值',
    '格擋': '攔網',
    '阻擋階段': '攔網階段',
    '阻擋點': '攔網值',
    '阻擋': '攔網',
    '區塊成功': '攔網成功',
    '區塊階段': '攔網階段',
    '區塊區域': '攔網區',
    '區塊': '攔網',
    # 數值（接球點 variant）
    '接球點': '接球值',
    # 特殊技能詞
    'Doshat': '強扣',
    # 出現→出場 + 第一人稱語氣（長詞先）
    '不能出現': '無法出場',
    '無法出現': '無法出場',
    '可以出現': '可以出場',
    '不，我': '不，',
    '是，我': '是，',
    # 元々の → 原本（Google 翻成「原創」是錯誤的）
    '原創': '原本',
    # 動詞
    '登場': '出場',
}

# ── Step 1：從 cards_data.js 建立人名清單 ─────────────────────────────────
def load_character_names(js_path: str) -> list[str]:
    """回傳所有 CHARACTER 卡的 name，按長度降序排列（長名先替換）。"""
    with open(js_path, encoding='utf-8') as f:
        content = f.read()
    # 去掉首行注釋與 JS 變數宣告，取得純 JSON
    lines = content.split('\n', 1)
    json_line = lines[1] if lines[0].startswith('//') else content
    json_str = re.sub(r'^const\s+CARDS_DATA\s*=\s*', '', json_line.strip().rstrip(';'))
    data = json.loads(json_str)
    seen = {}
    for card in data['cards']:
        name = card.get('name', '').strip()
        if name and card.get('category') == 'CHARACTER':
            if name not in seen:
                seen[name] = True
    # 長名字先替換，避免短名截斷長名
    return sorted(seen.keys(), key=len, reverse=True)


# ── Step 2：Pre-process（人名 → 佔位符） ─────────────────────────────────
def build_placeholder_map(names: list[str]) -> dict[str, str]:
    """建立 {name: placeholder} 對照表。"""
    return {name: f'<<<N{i}>>>' for i, name in enumerate(names)}


def preprocess(text: str, name_to_ph: dict[str, str]) -> str:
    for name, ph in name_to_ph.items():
        text = text.replace(name, ph)
    return text


def postprocess_names(text: str, ph_to_name: dict[str, str]) -> str:
    for ph, name in ph_to_name.items():
        text = text.replace(ph, name)
    return text


# ── Step 4：術語覆寫 ──────────────────────────────────────────────────────
def apply_term_fix(text: str) -> str:
    for wrong, correct in TERM_FIX.items():
        text = text.replace(wrong, correct)
    return text


# ── Step 3：翻譯 ─────────────────────────────────────────────────────────
def translate_text(text: str, translator: GoogleTranslator) -> str:
    if not text or not text.strip():
        return ''
    for attempt in range(RETRY + 1):
        try:
            result = translator.translate(text)
            return result or ''
        except Exception as e:
            if attempt < RETRY:
                time.sleep(RETRY_DELAY)
            else:
                return f'[翻譯失敗: {e}]'
    return ''


# ── Main ─────────────────────────────────────────────────────────────────
def main():
    sys.stdout.reconfigure(encoding='utf-8')

    # Step 1
    names = load_character_names(CARDS_JS)
    print(f'[INFO] 載入人名 {len(names)} 筆')

    name_to_ph = build_placeholder_map(names)
    ph_to_name = {v: k for k, v in name_to_ph.items()}

    # 讀取 qa_data.json
    with open(QA_SRC, encoding='utf-8') as f:
        qa_data: dict = json.load(f)

    translator = GoogleTranslator(source='ja', target='zh-TW')

    total = 0
    failed = 0
    output: dict = {}

    cards_with_qa = [k for k, v in qa_data.items() if v]
    print(f'[INFO] 有 Q&A 的卡：{len(cards_with_qa)} 張')

    for card_no in cards_with_qa:
        entries = qa_data[card_no]
        output[card_no] = []
        for entry in entries:
            total += 1

            # Step 2：Pre-process
            q_pre = preprocess(entry['question'], name_to_ph)
            a_pre = preprocess(entry['answer'],   name_to_ph)

            # Step 3：Google 翻譯
            q_translated = translate_text(q_pre, translator)
            time.sleep(DELAY)
            a_translated = translate_text(a_pre, translator)
            time.sleep(DELAY)

            if '翻譯失敗' in q_translated or '翻譯失敗' in a_translated:
                failed += 1

            # 還原人名佔位符
            q_zh = postprocess_names(q_translated, ph_to_name)
            a_zh = postprocess_names(a_translated, ph_to_name)

            # Step 4：術語覆寫
            q_zh = apply_term_fix(q_zh)
            a_zh = apply_term_fix(a_zh)

            output[card_no].append({
                'id':          entry['id'],
                'date':        entry['date'],
                'question':    entry['question'],
                'answer':      entry['answer'],
                'question_zh': q_zh,
                'answer_zh':   a_zh,
            })

        print(f'  {card_no}：{len(entries)} 筆完成')

    # Step 5：寫出
    with open(QA_DST, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Step 6：完了
    print()
    print(f'[完成] 輸出：{QA_DST}')
    print(f'  總件數：{total}')
    print(f'  成功：{total - failed}')
    print(f'  失敗：{failed}')


if __name__ == '__main__':
    main()
