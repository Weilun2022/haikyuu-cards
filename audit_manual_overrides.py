# -*- coding: utf-8 -*-
"""
一次性稽核腳本：對 MANUAL_OVERRIDES 裡的每一筆，重新用目前的通用規則
（translate_skill()）翻譯一次對應卡片的 skill 原文，跟手動覆蓋的內容比對。

- 結果「完全一致」→ 列為候選：通用規則已經追上，這筆覆蓋可能已經過期，
  可以考慮移除（人工複查後再決定，這個腳本不會自動刪除任何東西）。
- 結果「不一致」→ 通用規則還沒修好這個問題，覆蓋還是必要的，不列入候選。

只讀取 all_cards.json / build_data.py，不修改任何檔案、不影響翻譯輸出。
用法：python audit_manual_overrides.py
"""
import importlib.util
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))


def load_build_data():
    spec = importlib.util.spec_from_file_location('build_data', os.path.join(BASE, 'build_data.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['build_data'] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    bd = load_build_data()

    with open(os.path.join(BASE, 'all_cards.json'), encoding='utf-8') as f:
        raw_cards = json.load(f)

    # 比照 build_data.py main() 的做法：動態事件牌名清單 + CRLF 正規化
    event_names = list({
        c['name'] for c in raw_cards
        if c.get('category') == 'EVENT' and c.get('name', '').strip()
    })

    by_image_file = {}
    for c in raw_cards:
        card_no = c.get('card_no', '')
        img_end = c.get('image_end', '')
        image_file = f'{card_no}-{img_end}.webp'
        by_image_file[image_file] = c

    stale_candidates = []
    still_needed = []
    not_found = []

    for image_file, override_zh in bd.MANUAL_OVERRIDES.items():
        card = by_image_file.get(image_file)
        if not card:
            not_found.append(image_file)
            continue
        skill_jp = card.get('skill', '') or ''
        if isinstance(skill_jp, str):
            skill_jp = skill_jp.replace('\r\n', '\n')
        fresh = bd.translate_skill(skill_jp, event_names)
        if fresh == override_zh:
            stale_candidates.append((image_file, fresh))
        else:
            still_needed.append(image_file)

    total = len(bd.MANUAL_OVERRIDES)
    print(f'總計 MANUAL_OVERRIDES 筆數：{total}')
    print(f'找不到對應卡片（image_file 對不上 all_cards.json）：{len(not_found)}')
    for img in not_found:
        print(f'  - {img}')
    print(f'通用規則仍未追上，覆蓋仍必要：{len(still_needed)}')
    print(f'通用規則已一致，候選過期（建議人工複查後再決定要不要移除）：{len(stale_candidates)}')
    print()
    if stale_candidates:
        print('========== 過期候選清單 ==========')
        for image_file, fresh in stale_candidates:
            print(f'{image_file}\n  通用規則結果 = 覆蓋內容 = {fresh!r}\n')
    else:
        print('目前沒有候選——所有 168 筆手動覆蓋，通用規則單獨執行的結果都跟覆蓋內容不同，仍然必要。')


if __name__ == '__main__':
    main()
