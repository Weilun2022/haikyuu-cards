# -*- coding: utf-8 -*-
"""translate_qa.py 的 apply_term_fix()/pin_ambiguous_terms() 回歸測試。

2026-08 QA 全量重翻後核對術語一致性，發現這條規則鏈上有兩類容易復發的錯誤：
1. 「登場」在站內有兩種正確形式看語境（散文「出場」vs 技能標記保留原文「[=登場]」），
   最早的版本沒有把兩者分開保護，導致 apply_term_fix() 對同一段文字重複呼叫時
   會把已經正確的 [=登場] 錯改回 [=出場]（非冪等）。
2. オフェンスポイント／アタックポイント 兩個不同日文術語的官方值剛好互相衝突
   （オフェンスポイント正確值「進攻值」同時是 アタックポイント 常見的錯譯字串），
   TERM_FIX 的字串替換完全沒辦法分辨，改用翻譯前佔位、翻譯後直接還原的機制。
"""
from translate_qa import apply_term_fix, pin_ambiguous_terms, restore_pinned_terms, postprocess_names


def test_event_variants_become_official_english_term():
    assert apply_term_fix('活動區域最上面的卡牌') == 'Event區最上面的卡牌'
    assert apply_term_fix('活動區有卡牌') == 'Event區有卡牌'
    assert apply_term_fix('事件區域中') == 'Event區中'
    assert apply_term_fix('事件區有卡牌') == 'Event區有卡牌'
    assert apply_term_fix('打出事件卡') == '打出Event牌'
    assert apply_term_fix('活動卡片') == 'Event牌片'


def test_appearance_prose_becomes_chuchang():
    assert apply_term_fix('角色出現在攻擊區') == '角色出場在攻擊區'
    assert apply_term_fix('登場') == '出場'


def test_appearance_exception_phrase_is_protected():
    # 「出現什麼狀況」是「發生什麼狀況」的意思，跟角色出場無關，不能被整批規則誤改
    assert apply_term_fix('會出現什麼狀況？') == '會出現什麼狀況？'


def test_appearance_bracket_tag_becomes_touba_not_chuchang():
    # 技能標記要保留日文原形「[=登場]」，跟散文方向相反，不能翻成「[=出場]」
    assert apply_term_fix('[=出現][=攻擊區]') == '[=登場][=攻擊區]'
    assert apply_term_fix('[=外觀][=舉球區]') == '[=登場][=舉球區]'


def test_apply_term_fix_is_idempotent_for_appearance_family():
    # 迴歸測試：曾經的 bug——對同一段文字重複呼叫 apply_term_fix()，
    # 已經正確的 [=登場] 會被後面的散文規則「登場→出場」誤吃成 [=出場]
    samples = [
        '[=出現][=攻擊區]',
        '[=外觀][=舉球區]',
        '角色出現在攻擊區',
        '會出現什麼狀況？',
        '[=登場][=攻擊區]',  # 已經正確的形式也要能安全重跑
    ]
    for text in samples:
        once = apply_term_fix(text)
        twice = apply_term_fix(once)
        assert twice == once, f'apply_term_fix 不是冪等的：{text!r} -> {once!r} -> {twice!r}'


def test_full_width_bracket_parens_normalized_to_half_width():
    assert apply_term_fix('[=一鍵（N）]') == '[=一鍵(N)]'
    assert apply_term_fix('[=反擊（3）]計算') == '[=後排攻擊(3)]計算'


def test_postprocess_names_restores_confirmed_zh_value_not_raw_jp():
    # 2026-08「全站人名統一無空格」重構：postprocess_names() 過去把佔位符還原成未經處理的
    # 原始日文姓名字串（帶空格），跟網站其他地方（卡片標題、技能文字）的無空格慣例不一致。
    # 改成優先查 name_zh_data.py 的無空格 zh 值還原。
    ph_to_name = {'<<<N0>>>': '影山 飛雄'}
    result = postprocess_names('自己的舉球角色是<<<N0>>>', ph_to_name)
    assert result == '自己的舉球角色是影山飛雄'
    assert '影山 飛雄' not in result


def test_postprocess_names_falls_back_to_raw_jp_when_no_table_entry():
    # 查無 name_zh_data.py 對應條目時（例如還沒建表的角色），fallback 回原始日文姓名，
    # 不能讓查無條目變成佔位符沒被還原、或還原成空字串。
    ph_to_name = {'<<<N0>>>': '這個名字在表裡不存在_xyz'}
    result = postprocess_names('提到<<<N0>>>這個人', ph_to_name)
    assert result == '提到這個名字在表裡不存在_xyz這個人'


def test_backattack_bracket_scoped_not_bare_word():
    # 「反擊」是常見中文詞，只有技能標記內的用法才需要改
    assert apply_term_fix('[=反擊(3)]計算') == '[=後排攻擊(3)]計算'
    assert apply_term_fix('這是一次漂亮的反擊') == '這是一次漂亮的反擊'


def test_center_blocker_suffixed_forms_processed_before_bare_forms():
    # 長詞（帶「者/手」後綴）要先處理，短詞（無後綴）規則才不會把長詞截斷成疊字錯誤
    assert apply_term_fix('中心攔網者') == '中間攔網手'
    assert apply_term_fix('中攔網者') == '中間攔網手'
    assert apply_term_fix('中攔網') == '中間攔網手'
    assert apply_term_fix('中心攔網') == '中間攔網手'


def test_pin_ambiguous_terms_protects_offense_point_from_translation():
    text = 'オフェンスポイントはどのカードのアタックポイントで決定しますか'
    pre, pins = pin_ambiguous_terms(text)
    assert 'オフェンスポイント' not in pre
    assert pre.startswith('<<<P0>>>')
    assert pins == {'<<<P0>>>': '進攻值'}


def test_restore_pinned_terms_inserts_official_value():
    fake_translated = '<<<P0>>>是由哪張卡的攻擊值決定？'
    restored = restore_pinned_terms(fake_translated, {'<<<P0>>>': '進攻值'})
    assert restored == '進攻值是由哪張卡的攻擊值決定？'
