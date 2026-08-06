"""翻譯尚未加入 qa_data_zh.json 的新增 QA（增量，不動已翻譯過的卡）"""
import json
import socket
import sys
import time

socket.setdefaulttimeout(15)

sys.path.insert(0, '.')
from translate_qa import (
    load_character_names, build_placeholder_map, preprocess,
    postprocess_names, apply_term_fix, translate_text, CARDS_JS, DELAY,
)
from deep_translator import GoogleTranslator

QA_SRC = r'haikyuu_output/qa_data_FRESH.json'
QA_DST = r'haikyuu_output/qa_data_zh.json'

NEW_CARD_NOS = [
    "HV-P03-001","HV-P03-003","HV-P03-005","HV-P03-006","HV-P03-007","HV-P03-009",
    "HV-P03-011","HV-P03-013","HV-P03-014","HV-P03-016","HV-P03-020","HV-P03-021",
    "HV-P03-023","HV-P03-026","HV-P03-028","HV-P03-030","HV-P03-031","HV-P03-033",
    "HV-P03-038","HV-P03-039","HV-P03-044","HV-P03-051","HV-P03-054","HV-P03-056",
    "HV-P03-057","HV-P03-061","HV-P03-063","HV-P03-064","HV-P03-071","HV-P03-078",
    "HV-P03-079","HV-P03-080","HV-P03-081","HV-P03-082","HV-P03-083","HV-P03-084",
    "HV-P03-085","HV-P03-087","HV-P03-094","HV-P03-095","HV-P03-097","HV-P03-098",
    "HV-PR-044","HV-PR-045","HV-PR-048","HV-PR-049","HV-PR-050","HV-PR-051",
]


def main():
    sys.stdout.reconfigure(encoding='utf-8')

    names = load_character_names(CARDS_JS)
    name_to_ph = build_placeholder_map(names)
    ph_to_name = {v: k for k, v in name_to_ph.items()}

    with open(QA_SRC, encoding='utf-8') as f:
        fresh_qa = json.load(f)

    with open(QA_DST, encoding='utf-8') as f:
        qa_zh = json.load(f)

    translator = GoogleTranslator(source='ja', target='zh-TW')

    total = 0
    failed = 0

    for card_no in NEW_CARD_NOS:
        entries = fresh_qa.get(card_no, [])
        if not entries:
            print(f'  [WARN] {card_no}: 無資料，略過', flush=True)
            continue
        if card_no in qa_zh:
            print(f'  [SKIP] {card_no}: 已存在於 qa_data_zh.json，略過避免覆蓋', flush=True)
            continue

        out_entries = []
        for entry in entries:
            total += 1
            q_pre = preprocess(entry['question'], name_to_ph)
            a_pre = preprocess(entry['answer'], name_to_ph)

            q_translated = translate_text(q_pre, translator)
            time.sleep(DELAY)
            a_translated = translate_text(a_pre, translator)
            time.sleep(DELAY)

            if '翻譯失敗' in q_translated or '翻譯失敗' in a_translated:
                failed += 1

            q_zh = apply_term_fix(postprocess_names(q_translated, ph_to_name))
            a_zh = apply_term_fix(postprocess_names(a_translated, ph_to_name))

            out_entries.append({
                'id': entry['id'],
                'date': entry['date'],
                'question': entry['question'],
                'answer': entry['answer'],
                'question_zh': q_zh,
                'answer_zh': a_zh,
            })

        qa_zh[card_no] = out_entries
        with open(QA_DST, 'w', encoding='utf-8') as f:
            json.dump(qa_zh, f, ensure_ascii=False, indent=2)
        print(f'  {card_no}：{len(out_entries)} 筆完成', flush=True)

    print(flush=True)
    print(f'[完成] 新增卡數：{len(NEW_CARD_NOS)}  QA 總件數：{total}  失敗：{failed}', flush=True)
    print(f'qa_data_zh.json 現含 {len(qa_zh)} 張卡', flush=True)


if __name__ == '__main__':
    main()
