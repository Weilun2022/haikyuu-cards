# -*- coding: utf-8 -*-
"""Apply reported QA translation fixes (GitHub issues #43-#50) to qa_data_zh.json.

比對方式改成內容比對，不用位置索引（arr[idx-1]）——原因見
docs/translation/docs/adr/0004（官方 QA API 的 id 欄位不穩定，位置索引一樣脆弱：
若 qa_data_zh.json 是從頭重新產生，陣列裡的順序不保證跟當初套用這些修正時一樣）。
找不到目標、或找到超過一筆，一律直接報錯，不能靜默跳過或誤改到別筆。
"""
import json

from pipeline_paths import QA_ZH_JSON as path


def find_fix_target(qa_array, target_fields, anchor_fields=None):
    """在單一卡片的 QA 陣列裡定位要套用修正的那一筆。

    優先比對「目標欄位是否已經跟 target_fields 一致」——若剛好命中唯一一筆，
    代表這筆修正已經套用過，回傳 None（no-op，不是錯誤）。
    找不到已套用的痕跡時，退回用 anchor_fields（修正前內容的片段，子字串比對）定位。
    兩種方式都沒有命中、或命中超過一筆，直接丟例外，不能用猜的。
    """
    already = [
        i for i, e in enumerate(qa_array)
        if all(e.get(k) == v for k, v in target_fields.items())
    ]
    if len(already) == 1:
        return None
    if len(already) > 1:
        raise ValueError(f"目標欄位命中超過一筆（{len(already)} 筆），無法判斷唯一目標：{target_fields}")

    if not anchor_fields:
        raise ValueError(f"找不到已套用的目標，且沒有提供 anchor 可比對修正前內容：{target_fields}")

    matches = [
        i for i, e in enumerate(qa_array)
        if all(v in (e.get(k) or '') for k, v in anchor_fields.items())
    ]
    if len(matches) == 0:
        raise ValueError(f"anchor 沒有命中任何一筆，無法定位：{anchor_fields}")
    if len(matches) > 1:
        raise ValueError(f"anchor 命中超過一筆（{len(matches)} 筆），無法判斷唯一目標：{anchor_fields}")
    return matches[0]


# card_no -> [ {anchor: {修正前內容片段，子字串比對}, set: {field: 新值}} ]
# anchor 是從對應 GitHub issue 回報時附的「修正前」QA 內容重建的片段，用來定位「還沒套用這筆修正」
# 的那一列；哪一筆已經套用過，靠 target_fields（set）本身比對即可，不需要 anchor 也能判斷。
FIXES = {
    # #43 — "Miyaji" 應為 "宮 治"
    'HV-D03-013': [
        {
            'anchor': {'answer_zh': 'Miyaji'},
            'set': {'answer_zh': '不，你不能。如果卡片名稱「宮兄弟」更改為「宮 侑」或「宮 治」，則可以使用。'},
        },
    ],
    # #44 — 「不可以」應為「不需要」
    'HV-P02-024': [
        {
            'anchor': {'answer_zh': '不可以，您可以將Event區內所有卡片'},
            'set': {'answer_zh': '不需要，您可以將Event區內所有卡片中的一張卡片加入手牌。'},
        },
    ],
    # #45 Q&A4 + #46 Q&A5
    'HV-P02-027': [
        {
            'anchor': {'question_zh': '3個攔網值的角色添加1個攔網值'},
            'set': {
                'question_zh': '在對手使用該角色技能後的下一回合中，對手可以對伊達工業的中央攔網手使用HV-P02-090「追分 拓朗」的「為自己的伊達工業角色中的一個具有3攔網值的角色添加1攔網值」嗎？',
                'answer_zh': '不能。',
            },
        },
        {
            'anchor': {'answer_zh': '是的，自己可以。'},
            'set': {'answer_zh': '可以使用。'},
        },
    ],
    # #47 — 問答方向譯反，整段重寫
    'HV-P02-088': [
        {
            'anchor': {'answer_zh': '阻止你做的是打出Event牌'},
            'set': {
                'question_zh': '如果自己的舉球角色是「宮 治」並且自己的攻擊角色是「宮 侑」，在使用這張Event牌後，對手在下一個回合是否可以將一張Event牌放置在Event區中，來使用HV-P02-003「月島 蛍」的技能？',
                'answer_zh': '是的，對手可以。這張卡的技能可以阻止對手做的是使用Event牌，而不是阻止對手將Event牌放置在Event區中。',
            },
        },
    ],
    # #48 — 「畫」應為「抽」
    'HV-P02-086': [
        {
            'anchor': {'answer_zh': '畫一張卡片'},
            'set': {'answer_zh': '抽一張卡片。'},
        },
    ],
    # #49 Q&A3 + #50 Q&A4
    'HV-P02-087': [
        {
            'anchor': {'answer_zh': '不，事實並非如此'},
            'set': {
                'question_zh': '能夠登場的Guts中的「宮 侑」或「宮 治」，是專指位於舉球區下方Guts中的「宮 侑」，以及位於攻擊區下方Guts中的「宮 治」嗎？',
                'answer_zh': '不，並不以此為限。若Guts所屬的區域沒有特別指定時，不論是發球區、攔網區、接球區、舉球區或攻擊區的任何一個區域，都可以將其中的Guts「宮 侑」與「宮 治」登場。',
            },
        },
        {
            'anchor': {'answer_zh': '不適用於與第二個技能一起出場'},
            'set': {
                'question_zh': '我使用這張卡片的技能，使攻擊區的「宮 治」攻擊值+1。之後，我使用第二張這張卡片的技能，在攻擊區登場另一張「宮 治」，並使該角色的攻擊值+1。此時，攻擊區的「宮 治」其攻擊值會被+2嗎？',
                'answer_zh': '不會，只會有+1。第一張技能所給予的攻擊值+1是針對「當時」作為攻擊角色的「宮 治」；它並不會套用在因第二張技能所登場的另一張「宮 治」上。最終，只會套用第二張技能所給予的攻擊值+1。',
            },
        },
    ],
}


def apply_fixes(data, fixes):
    """純邏輯：套用 fixes 到 data（in-place），回傳實際更新的欄位數。呼叫端負責讀檔/寫檔。"""
    changed = 0
    for card_no, entries in fixes.items():
        arr = data.get(card_no)
        if not arr:
            print(f'[WARN] {card_no} 不存在')
            continue
        for fix in entries:
            idx = find_fix_target(arr, fix['set'], fix.get('anchor'))
            if idx is None:
                print(f'[SKIP] {card_no} 已套用過此修正，略過')
                continue
            e = arr[idx]
            for f, v in fix['set'].items():
                if e.get(f) != v:
                    e[f] = v
                    changed += 1
                    print(f'[OK] {card_no}（第 {idx + 1} 筆）{f} 已更新')
    return changed


if __name__ == '__main__':
    d = json.load(open(path, encoding='utf-8'))
    changed = apply_fixes(d, FIXES)
    json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n完成，共更新 {changed} 個欄位。')
