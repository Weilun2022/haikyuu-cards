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

from pipeline_paths import QA_JSON as QA_SRC, QA_ZH_JSON as QA_DST, ALL_CARDS_JSON

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
    # 方塊（ブロック 第 4 種誤譯，長詞先——2026-08 QA 全量重翻批次核對術語一致性
    # 時發現，跟格擋/阻擋/區塊同一類問題，只是這批機翻換了個新的錯譯詞）
    '方塊區域': '攔網區',
    '方塊角色': '攔網角色',
    '方塊': '攔網',
    # 攔網值（ブロックポイント 誤譯，長詞先）
    '攔網點數': '攔網值',
    '攔網點': '攔網值',
    # 中間攔網手（センターブロッカー 誤譯；長詞（帶「者/手」後綴）先，短詞（無後綴）
    # 才不會把長詞截斷成「中間攔網手者」這種疊字錯誤）
    '中路攔網者': '中間攔網手',
    '中路攔網手': '中間攔網手',
    '中攔網者': '中間攔網手',
    '中央攔網者': '中間攔網手',
    '中心攔網者': '中間攔網手',
    '中攔網': '中間攔網手',
    '中心攔網': '中間攔網手',
    # 側翼攔網手（サイドブロッカー 誤譯）
    '側攔網': '側翼攔網手',
    '旁路攔網者': '側翼攔網手',
    '側方攔網者': '側翼攔網手',
    '側擋': '側翼攔網手',
    # 數值（接球點 variant）
    '接球點': '接球值',
    # 接球值（レシーブポイント 誤譯，長詞先）
    '獲得點數': '接球值',
    '獲得積分': '接球值',
    '獲得點': '接球值',
    # 防禦值（ディフェンスポイント 誤譯）
    '防禦分數': '防禦值',
    # 場地（コート 誤譯，兩種變體）
    '場上': '場地',
    '場區': '場地',
    # 稻荷崎（校名誤譯——Google 偶爾把「稲荷崎」音近誤植成「稻成崎」）
    '稻成崎': '稻荷崎',
    # 舉球角色（トスキャラ 誤譯，各自獨立、彼此無包含關係）
    '投擲的角色': '舉球角色',
    '投球角色': '舉球角色',
    '折騰人物': '舉球角色',
    '拋擲角色': '舉球角色',
    # 攻擊角色（アタックキャラ 誤譯）
    '攻擊字元': '攻擊角色',
    # 後排攻擊（バックアタック 誤譯，只在技能標記內出現，bare「反擊」是常見中文詞
    # 不能整批替換，只替換標記開頭那一段）
    '[=反擊(': '[=後排攻擊(',
    # 特殊技能詞
    'Doshat': '強扣',
    # 元々の → 原本（Google 翻成「原創」是錯誤的）
    '原創': '原本',
    # ── 登場／出現／出場（必須放在同一批，順序有嚴格要求，見下方說明）──
    #
    # 技能標記「[=登場]」要保留日文原形不翻，跟散文的「登場→出場」方向相反。
    # apply_term_fix() 是單純字串替換，不管上下文，所以「登場」這個字下面第一條
    # 散文規則一律當成「散文」處理——如果標記不先「挖出來」保護，[=登場] 裡的
    # 「登場」子字串一樣會被那條規則誤改成 [=出場]。這裡先把所有代表「標記」的
    # 三種輸入形式（已經正確的 [=登場]、Google 常見的兩種誤譯 [=出現]/[=外觀]）
    # 統一收斂成同一個佔位符，讓下面的散文規則完全碰不到它，最後再統一還原成
    # 正確的 [=登場]。這麼做也讓 apply_term_fix() 對同一段文字重複呼叫是安全的
    # （冪等）——不會因為文字已經是正確的 [=登場] 而在下一輪被錯誤地改回
    # [=出場]（2026-08 QA 全量重翻後，對同一批資料重跑第二輪術語修正時才發現
    # 這個問題：沒有先保護的版本會把上一輪已經修好的 [=登場] 吃掉）。
    '[=登場]': '<<<QA_TAG_TOUBA>>>',
    '[=出現]': '<<<QA_TAG_TOUBA>>>',
    '[=外觀]': '<<<QA_TAG_TOUBA>>>',
    # 出現→出場 + 第一人稱語氣（長詞先，標記已經保護起來，這裡只會動到散文）
    '不能出現': '無法出場',
    '無法出現': '無法出場',
    '可以出現': '可以出場',
    '不，我': '不，',
    '是，我': '是，',
    # 動詞
    '登場': '出場',
    # 出現→出場（整批規則，但「出現什麼狀況」是「發生什麼狀況」的意思，跟角色
    # 出場無關，必須用佔位符保護起來，不能被下面的整批規則誤改——原理跟這個檔案
    # 已有的人名 <<<N{i}>>> 佔位符機制一樣：先佔位讓它暫時不含「出現」子字串，
    # 整批規則跑完再換回來）
    '出現什麼狀況': '<<<QA_SAFE_0>>>',
    '出現': '出場',
    '<<<QA_SAFE_0>>>': '出現什麼狀況',
    # 登場 的其他錯譯（不是「出現」這個字，是完全不同的詞——2026-08 QA 全量重翻
    # 批次核對術語一致性時發現，長詞先）
    '帶入遊戲': '出場',
    '帶入': '出場',
    '引入': '出場',
    '您介紹該角色並支付': '您使該角色出場並支付',
    # 還原技能標記佔位符（放在整批 dict 最後——上面所有散文規則都跑完了才還原，
    # 確保標記不會被任何一條散文規則誤傷）
    '<<<QA_TAG_TOUBA>>>': '[=登場]',
    # Event 牌/區（長詞先，避免短詞截斷長詞殘留「域」字；跟站內其他地方保留英文
    # 「Event」的慣例一致，不翻成中文「活動/事件」——2026-08 QA 全量重翻才發現
    # 這條規則整個沒收錄，見 docs/translation/CONTEXT.md）
    '活動區域': 'Event區',
    '事件區域': 'Event區',
    '活動區':   'Event區',
    '事件區':   'Event區',
    '活動卡':   'Event牌',
    '事件卡':   'Event牌',
}

# ── Step 1：從 all_cards.json 建立人名清單 ─────────────────────────────────
def load_character_names(all_cards_path) -> list[str]:
    """回傳所有 CHARACTER 卡的 name，按長度降序排列（長名先替換）。

    讀原始 all_cards.json（下載 pipeline 步驟1的輸出），不是 build_data.py
    建置出的 cards_data.js——後者只在 SOP 步驟6才會重新產生，若這裡讀 cards_data.js
    會拿到上一輪舊資料，新卡的角色名在這次 QA 翻譯時就不會被佔位符保護
    （2026-08 架構檢視發現的隱性步驟順序依賴）。"""
    with open(all_cards_path, encoding='utf-8') as f:
        raw = json.load(f)
    seen = {}
    for card in raw:
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


# ── 有些日文術語 Google 翻譯後會跟「另一個不同日文術語的正確譯文」撞名——
# 例如 オフェンスポイント（官方值「進攻值」）常被 Google 翻成跟 アタックポイント
# （官方值「攻擊值」）一樣的「攻擊值」。TERM_FIX 的簡單字串替換完全沒辦法分辨
# 「這個攻擊值原本是哪個日文詞」，兩個術語又常常出現在同一句裡，無法用 TERM_FIX
# 修正（2026-08 QA 全量重翻批次核對術語一致性時發現，39 筆受影響）。
# 用跟人名一樣的佔位符機制：翻譯前先佔位，翻譯後直接還原成官方值，不讓 Google
# 有機會誤譯——只收錄「確認會跟另一個術語撞名」的項目，不是所有術語都要佔位。
PINNED_TERMS = {
    'オフェンスポイント': '進攻值',
}


def pin_ambiguous_terms(text: str) -> tuple[str, dict[str, str]]:
    """回傳 (置換後文字, {佔位符: 正確譯文})，翻譯前呼叫。"""
    ph_to_correct = {}
    for i, (jp, correct) in enumerate(PINNED_TERMS.items()):
        if jp in text:
            ph = f'<<<P{i}>>>'
            text = text.replace(jp, ph)
            ph_to_correct[ph] = correct
    return text, ph_to_correct


def restore_pinned_terms(text: str, ph_to_correct: dict[str, str]) -> str:
    for ph, correct in ph_to_correct.items():
        text = text.replace(ph, correct)
    return text


# ── Step 4：術語覆寫 ──────────────────────────────────────────────────────
def _normalize_bracket_parens(text: str) -> str:
    """[=X（N）] 技能標記語法裡的括號偶爾被 Google 吐成全形，害下面逐一設計的
    標記修正規則字串對不上（2026-08 核對術語一致性時發現：ワンタッチ/ツーアタック/
    Aパス 都中過）。統一把 [=...] 標記內的全形括號正規化成半形，只動標記內部，
    不影響標記外的一般文字。"""
    return re.sub(r'\[=([^\]]*)\]', lambda m: '[=' + m.group(1).replace('（', '(').replace('）', ')') + ']', text)


def apply_term_fix(text: str) -> str:
    text = _normalize_bracket_parens(text)
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
    names = load_character_names(ALL_CARDS_JSON)
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

            # Step 2：Pre-process（人名 + 容易撞名的術語都先佔位）
            q_pre, q_pins = pin_ambiguous_terms(entry['question'])
            a_pre, a_pins = pin_ambiguous_terms(entry['answer'])
            q_pre = preprocess(q_pre, name_to_ph)
            a_pre = preprocess(a_pre, name_to_ph)

            # Step 3：Google 翻譯
            q_translated = translate_text(q_pre, translator)
            time.sleep(DELAY)
            a_translated = translate_text(a_pre, translator)
            time.sleep(DELAY)

            if '翻譯失敗' in q_translated or '翻譯失敗' in a_translated:
                failed += 1

            # 還原人名佔位符 + 撞名術語佔位符
            q_zh = postprocess_names(q_translated, ph_to_name)
            a_zh = postprocess_names(a_translated, ph_to_name)
            q_zh = restore_pinned_terms(q_zh, q_pins)
            a_zh = restore_pinned_terms(a_zh, a_pins)

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
