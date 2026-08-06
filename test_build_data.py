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


def test_apply_confirmed_name_zh_only_touches_confirmed_status():
    # _apply_confirmed_name_zh 只吃 status=confirmed 的條目，high/medium/low/draft 不透過這個機制套用
    non_confirmed_statuses = {'high', 'medium', 'low', 'draft', 'auto'}
    sample_non_confirmed = [
        e for e in bd.NAME_ZH_ENTRIES if e.get('status') in non_confirmed_statuses
    ]
    assert sample_non_confirmed, "測試前提：應該存在非 confirmed 狀態的條目"
    for entry in sample_non_confirmed[:5]:
        t = f"前綴 {entry['jp']} 後綴"
        result = bd._apply_confirmed_name_zh(t)
        assert result == t, f"非 confirmed 條目 {entry['jp']!r} 不應該被自動套用"


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
