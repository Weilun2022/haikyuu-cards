# -*- coding: utf-8 -*-
"""build_data.py 核心翻譯規則的回歸測試。

只斷言 translate_skill()/clean_qa_text()(輸入) == 預期輸出這種外部行為，不斷言內部呼叫了
哪個 helper。案例來源：檔頭「翻譯問題整理」歷史踩雷記錄（問題一～問題七）、2026-08 架構
檢視時發現的候選 B 譯名 drift 修正案例，以及 clean_qa_text() 現存規則（AI 誤譯技能標記修正）。
clean_qa_text() 原本前段還有 10 個處理日文語尾/助詞殘留的 section，2026-08 確認這批規則
只可能對「先跑過 translate_skill() 殘留助詞規則」的文字命中，但這個函式唯一的輸入來源
（Google Translate 輸出）不會產生這種殘留，故直接刪除，不是保留觀察——見 build_data.py
裡 clean_qa_text() 上方的說明註解。
"""
import inspect
import re

import pytest
import build_data as bd


def test_sono_go_vs_sono_order_dependency():
    # 問題一：その後 vs その，規則順序錯了會把「その後」拆成「該後」
    assert bd.translate_skill('その後、抽1張牌', []) == '之後，抽1張牌'


def test_tojousaserarenai_vs_tojousase_order_dependency():
    # 問題二：登場させられない vs 登場させ，一般規則先吃掉前半會拆壞成「使其出場，不能」
    result = bd.translate_skill('このキャラは登場させられない', [])
    assert '不能出場' in result
    assert '使其出場，不能' not in result


def test_tabi_does_not_add_redundant_every_time():
    # 問題三：たび 不該翻成「每次/每當」，只要「…時」
    result = bd.translate_skill('このキャラが登場するたび、抽1張牌', [])
    assert '每次' not in result
    assert '每當' not in result


def test_jibun_no_word_order_after_verb():
    # 問題四：自己的 + 動詞 + 受詞，不能讓「自己的」卡在動詞和受詞中間
    result = bd.translate_skill('自分のデッキの上から1枚を公開し', [])
    assert '自己的公開' not in result


def test_kono_kyara_ga_baai_inserts_shi():
    # 問題五：このキャラが〜キャラの場合，要補「是」字
    result = bd.translate_skill('このキャラがアタックキャラの場合', [])
    assert '此角色是' in result


def test_donpishari_confirmed_name_zh_applied():
    # 候選 B：どんぴしゃり／どん ぴしゃり 都要吃到 name_zh_data.py 的 confirmed 版本「分毫不差！」
    assert bd.translate_skill('どんぴしゃりだ', []) == '分毫不差！だ'
    assert bd.translate_skill('どん ぴしゃりだ', []) == '分毫不差！だ'


def test_hinagarasu_corrected_to_match_name_zh_data():
    # 候選 B：ヒナガラス 過去硬編成「雛烏鴉」，跟 name_zh_data.py 的「雛烏」drift，已修正
    assert bd.translate_skill('ヒナガラス', []) == '雛烏'


def test_kyou_nani_wo_suru_corrected_to_match_name_zh_data():
    # 候選 B：今日 何をする？ 過去硬編成「今天做什麼？」，跟 name_zh_data.py 的
    # 「今天，你要做什麼？」drift，已修正
    assert bd.translate_skill('今日 何をする？', []) == '今天，你要做什麼？'


def test_apply_confirmed_name_zh_only_touches_confirmed_and_auto_status():
    # _apply_confirmed_name_zh 吃 status=confirmed（使用者拍板）跟 status=auto（機械去空格/
    # 繁體正字，高信心）的條目；high/medium/low/draft 這些還在研究中的猜測不透過這個機制套用。
    # auto 曾經被排除在外，是這次「全站人名統一無空格」重構要修正的閘門過嚴問題——auto 不是
    # 未定案的猜測，是已經高信心機械正規化過的值，不該跟 high/medium/low/draft 同一個待遇。
    still_excluded_statuses = {'high', 'medium', 'low', 'draft'}
    sample_excluded = [
        e for e in bd.NAME_ZH_ENTRIES if e.get('status') in still_excluded_statuses
    ]
    assert sample_excluded, "測試前提：應該存在 high/medium/low/draft 狀態的條目"
    for entry in sample_excluded[:5]:
        t = f"前綴 {entry['jp']} 後綴"
        result = bd._apply_confirmed_name_zh(t)
        assert result == t, f"{entry.get('status')} 狀態條目 {entry['jp']!r} 不應該被自動套用"


def test_apply_confirmed_name_zh_now_applies_auto_status_person_names():
    # 根因修正：name_zh_data.py 裡所有人名條目的 status 其實是 auto，不是 confirmed，過去
    # 被 _apply_confirmed_name_zh() 的閘門一併擋下，導致通用規則鏈翻出來的技能文字裡，角色
    # 全名一直維持著日文原文的帶空格格式沒被轉換（例如「影山 飛雄」「及川 徹」）。
    auto_person_entries = [e for e in bd.NAME_ZH_ENTRIES if e.get('status') == 'auto']
    assert auto_person_entries, "測試前提：應該存在 status=auto 的人名條目"
    for entry in auto_person_entries[:5]:
        t = f"自己的角色是「{entry['jp']}」時"
        result = bd._apply_confirmed_name_zh(t)
        assert entry['zh'] in result, f"auto 條目 {entry['jp']!r} 應該被套用成 {entry['zh']!r}"
        assert entry['jp'] not in result, f"auto 條目 {entry['jp']!r} 不應該原樣殘留"


def test_translate_skill_outputs_no_space_person_name_via_general_pipeline():
    # 端到端驗證：通用規則鏈（不是個別窄規則）翻出來的技能文字，引用其他角色全名時輸出
    # 無空格版本，跟卡片標題慣例一致——這是這次重構要解決的原始問題（搜尋「日向翔陽」
    # 找不到技能文字裡「日向 翔陽」這種帶空格引用）的資料層根本修正。
    result = bd.translate_skill('自己的舉球角色是「影山 飛雄」時', [])
    assert '影山飛雄' in result
    assert '影山 飛雄' not in result


def test_point_terms_use_official_terms_single_source():
    # 候選 A：攔網值/接球值/發球值 改用 OFFICIAL_TERMS 單一來源，不再是硬編字面量
    assert bd.OFFICIAL_TERMS['ブロックポイント'] == '攔網值'
    assert bd.OFFICIAL_TERMS['レシーブポイント'] == '接球值'
    assert bd.OFFICIAL_TERMS['サーブポイント'] == '發球值'
    assert bd.translate_skill('ブロックポイント', []) == '攔網值'
    assert bd.translate_skill('レシーブポイント', []) == '接球值'
    assert bd.translate_skill('サーブポイント', []) == '發球值'


def test_manual_overrides_no_longer_uses_stale_hinagarasu_wording():
    stale = 'HV-PR-037-P.webp'
    assert stale in bd.MANUAL_OVERRIDES
    assert '雛烏鴉' not in bd.MANUAL_OVERRIDES[stale]
    assert '雛烏' in bd.MANUAL_OVERRIDES[stale]


def test_name_zh_value_tracks_name_zh_data_instead_of_hardcoded_copy():
    # ヒナガラス／今日 何をする？ 改用 _name_zh_value() 直接查 name_zh_data.py 的目前值，
    # 不是各自硬編一份翻譯字面量——用一個明顯不合理的 fallback 證明真的有查到表、沒有落到 fallback。
    assert bd._name_zh_value('ヒナガラス', fallback='FALLBACK_不應該出現') == '雛烏'
    assert bd._name_zh_value('今日 何をする？', fallback='FALLBACK_不應該出現') == '今天，你要做什麼？'


def test_name_zh_value_uses_fallback_when_entry_missing():
    assert bd._name_zh_value('這個字串在表裡不存在_xyz', fallback='用預設值') == '用預設值'


def test_riefu_confirmed_name_zh_applied():
    # 灰羽リエーフ 全名完整出現時，透過 _apply_confirmed_name_zh()（status=confirmed）
    # 套用拍板譯名，不再因為 status 是 high 而被 gate 擋下
    result = bd.translate_skill('自己的攔網角色是「灰羽 リエーフ」時', [])
    assert '灰羽利耶夫' in result
    assert 'リエーフ' not in result


def test_riefu_bare_katakana_residual_uses_name_zh_value():
    # 只殘留片假名姓氏（沒有「灰羽」前綴）時，窄規則改接 _name_zh_value() 查表，不是硬編
    # 字面量——跟 test_name_zh_value_tracks_name_zh_data_instead_of_hardcoded_copy 同一種
    # 驗證精神。
    assert bd.translate_skill('リエーフ', []) == '灰羽利耶夫'


def test_tadashi_quote_uses_name_zh_data_instead_of_hardcoded_copy():
    # 山口忠的招牌喊叫「ただーし！」——值目前剛好跟表格一致，但一樣是寫死繞過查表，
    # 改接 _name_zh_value() 確保表值一改這裡自動跟著變。
    result = bd.translate_skill('ただーし！', [])
    assert result == '忠——！'


def test_inner_cross_quote_corrected_to_match_name_zh_data():
    # build_data.py 曾經寫死「超內側穿越」，但 name_zh_data.py 拍板值其實是
    # 「超銳角斜線扣球！！！」，兩邊從沒同步過。
    result_full = bd.translate_skill('超インナークロス', [])
    assert result_full == '超銳角斜線扣球！！！'
    assert '超內側穿越' not in result_full

    # 只殘留「インナークロス」（沒有「超」前綴）的窄規則安全網，也要接同一份查表值
    result_bare = bd.translate_skill('インナークロス', [])
    assert result_bare == '超銳角斜線扣球！！！'
    assert '內側穿越' not in result_bare


def test_tasukete_quote_corrected_to_match_name_zh_data():
    # build_data.py 曾經寫死「接受幫助」，但 name_zh_data.py 拍板值其實是
    # 「我要找人幫忙！！！」，兩邊從沒同步過。
    result = bd.translate_skill('助けてもらう', [])
    assert result == '我要找人幫忙！！！'


def test_manual_overrides_riefu_entries_use_confirmed_translation():
    # MANUAL_OVERRIDES 裡提到灰羽リエーフ的 3 筆，改成拍板譯名——2026-08 全站人名統一無空格
    # 重構後，跟卡片標題／通用規則鏈輸出一致改成無空格「灰羽利耶夫」（先前版本要求帶空格
    # 「灰羽 利耶夫」，是尚未確認全站慣例前的舊決策，已被這次重構取代），維持純靜態字串、
    # 不接查表機制。
    affected = ['HV-P01-028-N.webp', 'HV-D02-004-D.webp', 'HV-PR-023-P.webp']
    for key in affected:
        assert key in bd.MANUAL_OVERRIDES, f'{key} 應該存在於 MANUAL_OVERRIDES'
        text = bd.MANUAL_OVERRIDES[key]
        assert '灰羽利耶夫' in text, f'{key} 應該含拍板譯名「灰羽利耶夫」（無空格）'
        assert '灰羽 利耶夫' not in text, f'{key} 不應該再含舊版帶空格寫法「灰羽 利耶夫」'
        assert '里耶夫' not in text, f'{key} 不應該再含舊錯誤寫法「里耶夫」'
        assert '列夫' not in text, f'{key} 不應該含另一種舊錯誤寫法「列夫」'


def test_manual_overrides_no_space_person_names_from_batch_migration():
    # 2026-08「全站人名統一無空格」重構：MANUAL_OVERRIDES 裡 33 個角色、107 筆帶空格的
    # 全名引用（例如「日向 翔陽」），批次收斂成跟 name_zh_data.py 一致的無空格版本。
    assert 'HV-P01-003-S.webp' in bd.MANUAL_OVERRIDES
    assert '影山飛雄' in bd.MANUAL_OVERRIDES['HV-P01-003-S.webp']
    assert '影山 飛雄' not in bd.MANUAL_OVERRIDES['HV-P01-003-S.webp']

    assert 'HV-P01-006-I.webp' in bd.MANUAL_OVERRIDES
    assert '日向翔陽' in bd.MANUAL_OVERRIDES['HV-P01-006-I.webp']
    assert '日向 翔陽' not in bd.MANUAL_OVERRIDES['HV-P01-006-I.webp']

    # 沒有空格可去、單純字型差異（黒→黑）的「・」複合名稱標籤，不在這次範圍內，維持原樣
    assert 'HV-PR-014-P.webp' in bd.MANUAL_OVERRIDES
    assert '孤爪・黒尾' in bd.MANUAL_OVERRIDES['HV-PR-014-P.webp']


def test_manual_overrides_redundant_entry_removed():
    # HV-PR-047-P.webp 逐一 diff 通用規則鏈後確認完全冗餘（輸出逐字相同），2026-08 重構順便刪除
    assert 'HV-PR-047-P.webp' not in bd.MANUAL_OVERRIDES


def test_clean_qa_text_fixes_ai_mistranslated_skill_tags():
    # Google Translate 常把卡面標記音譯/意譯錯，clean_qa_text() 負責修正回正確的中文標記。
    assert bd.clean_qa_text('[=doshat(3)]') == '[=封殺攔網(3)]'
    assert bd.clean_qa_text('[=Doshat(5)]') == '[=封殺攔網(5)]'
    assert bd.clean_qa_text('[=一鍵(2)]') == '[=一觸(2)]'
    assert bd.clean_qa_text('[=一次觸摸(4)]') == '[=一觸(4)]'


def test_clean_qa_text_fixes_ai_mistranslated_terminology():
    # 另一批確認仍在運作的規則：Google Translate 常見的詞彙誤譯修正（非技能標記，是一般用詞）。
    assert bd.clean_qa_text('對手的活動卡') == '對手的Event牌'
    assert bd.clean_qa_text('自己的格斯不足') == '自己的Guts不足'
    assert bd.clean_qa_text('貓魔的角色') == '音駒的角色'


def test_clean_qa_text_no_longer_touches_removed_particle_residue_patterns():
    # 2026-08 刪掉的 10 個 section 曾經處理這類日文語尾/助詞殘留字串——這些輸入現在應該
    # 原樣通過，不會被誤觸發任何規則（confirm 真的刪乾淨了，不是還留著某條漏網之魚）。
    assert bd.clean_qa_text('することができる') == 'することができる'
    assert bd.clean_qa_text('使えません') == '使えません'
    assert bd.clean_qa_text('和どういう意味，す或？') == '和どういう意味，す或？'


def test_clean_qa_text_passes_through_ordinary_google_translated_sentence_unchanged():
    # Google Translate 輸出的一般完整中文句子（沒有誤譯詞彙）應該原樣通過。
    sentence = '這張卡的技能可以在對手回合結束時發動一次。'
    assert bd.clean_qa_text(sentence) == sentence


# ── 靜態掃描 build_data.py 原始碼，防止「寫死翻譯繞過 name_zh_data.py 查表」──
#
# 這組測試刻意掃的是 build_data.py 的「原始碼文字」本身，不是任何卡片內容或函式輸出——這是
# 對「這個 repo 只測外部行為，不斷言內部呼叫了哪個 helper」這條慣例的明確例外：這裡要保護的
# 事實只存在於程式碼的靜態結構裡（某個詞的翻譯是不是真的透過查表機制取得），沒辦法用任何
# 黑箱輸入輸出測試表達——一個值「現在剛好對」跟「架構上保證對」是兩回事，只有前者的話還是
# 可能悄悄 drift。找的是 .replace(常數, 常數) 這種兩個引數都是字面量字串的呼叫，且第一個
# 引數命中官方譯名表（name_zh_data.py）裡任何一筆 jp 值（或反過來，jp 值命中它）。命中就代表
# 這個日文詞被寫死翻譯，沒有透過既有的 _apply_confirmed_name_zh()/_name_zh_value() 查表機制。
#
# 「jp 是 literal1 的子字串」這個方向的比對，只在 jp 本身夠短（<=15字，像名字/短台詞，不是
# 整句對白）時才做——避免像「この」「その」這種常見助詞剛好是某句長台詞子字串時的假陽性
# （這個門檻是實際拿現有語料測出來、逐一核對過命中結果才定案的）。
_HARDCODED_REPLACE_PATTERN = re.compile(
    r"""\.replace\(\s*(['"])((?:(?!\1).)+)\1\s*,\s*(['"])((?:(?!\3).)*)\3\s*\)"""
)


def _hardcoded_name_replacement_violations(source: str, name_entries) -> list[tuple[int, str, str]]:
    """回傳 (行號, 該行原始碼, 命中的 jp 值) 清單，空清單代表沒有寫死翻譯繞過查表的情況。"""
    violations = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        for m in _HARDCODED_REPLACE_PATTERN.finditer(line):
            literal1 = m.group(2)
            if len(literal1) < 2:
                continue
            for entry in name_entries:
                jp = entry['jp']
                jp_compact = jp.replace('　', '').replace(' ', '')
                hit = (jp in literal1) or (jp_compact in literal1)
                if len(jp_compact) <= 15:
                    hit = hit or (literal1 in jp) or (literal1 in jp_compact)
                if hit:
                    violations.append((lineno, line.strip(), jp))
    return violations


def test_hardcoded_name_replacement_scan_flags_bypassed_literal():
    fake_source = "t = t.replace('リエーフ', '里耶夫')\n"
    fake_entries = [{'jp': '灰羽 リエーフ', 'zh': '灰羽利耶夫', 'status': 'confirmed'}]
    violations = _hardcoded_name_replacement_violations(fake_source, fake_entries)
    assert violations, '應該抓到寫死翻譯繞過查表的違規'
    assert violations[0][0] == 1


def test_hardcoded_name_replacement_scan_ignores_lookup_call():
    fake_source = "t = t.replace('リエーフ', _name_zh_value('灰羽 リエーフ', fallback='灰羽利耶夫'))\n"
    fake_entries = [{'jp': '灰羽 リエーフ', 'zh': '灰羽利耶夫', 'status': 'confirmed'}]
    violations = _hardcoded_name_replacement_violations(fake_source, fake_entries)
    assert not violations, '透過查表機制的呼叫不該被誤判'


def test_hardcoded_name_replacement_scan_ignores_unrelated_short_particle_in_long_quote():
    # 假陽性回歸測試：常見助詞「この」剛好是某句長台詞（非姓名/短台詞）的子字串，不該被誤判。
    fake_source = "t = t.replace('この','此')\n"
    fake_entries = [{'jp': '俺のサーブの邪魔すんなや この喧しブタ', 'zh': '別妨礙我發球啦，你這吵死人的豬', 'status': 'high'}]
    violations = _hardcoded_name_replacement_violations(fake_source, fake_entries)
    assert not violations, '長台詞裡的常見助詞子字串不該被誤判成寫死翻譯繞過查表'


def test_build_data_source_has_no_hardcoded_name_replacements():
    # 對照目前的 build_data.py 原始碼跟官方譯名表，確認沒有任何已知詞被寫死翻譯繞過查表
    # 機制——這是這個安全網真正在保護的東西。這個測試如果紅燈，訊息裡會直接指出是哪一行、
    # 對應哪個日文詞，不用再靠人工全文審查才能發現。
    source = inspect.getsource(bd)
    violations = _hardcoded_name_replacement_violations(source, bd.NAME_ZH_ENTRIES)
    assert not violations, f'發現寫死翻譯繞過查表：{violations}'
