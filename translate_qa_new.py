"""翻譯尚未加入 qa_data_zh.json 的新增 QA（增量，不動已翻譯過的卡）。
動態計算「qa_data.json 裡有非空 QA、但 qa_data_zh.json 還沒有」的 card_no 清單，
不用每次手動編輯卡號清單——跟 fetch_new_qa.py 用同一套邏輯形狀，可以直接接在它後面跑。
"""
import json
import socket
import sys
import time
from pathlib import Path

socket.setdefaulttimeout(15)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from translate_qa import (
    load_character_names, build_placeholder_map, preprocess,
    postprocess_names, apply_term_fix, translate_text, CARDS_JS, DELAY,
)
from haikyuu_downloader import QA_PATH
from deep_translator import GoogleTranslator

QA_DST = r'haikyuu_output/qa_data_zh.json'


def main():
    sys.stdout.reconfigure(encoding='utf-8')

    names = load_character_names(CARDS_JS)
    name_to_ph = build_placeholder_map(names)
    ph_to_name = {v: k for k, v in name_to_ph.items()}

    with open(QA_PATH, encoding='utf-8') as f:
        qa_data = json.load(f)

    with open(QA_DST, encoding='utf-8') as f:
        qa_zh = json.load(f)

    new_card_nos = sorted(no for no, qa in qa_data.items() if qa and no not in qa_zh)
    print(f'待翻譯新卡數：{len(new_card_nos)}', flush=True)

    translator = GoogleTranslator(source='ja', target='zh-TW')

    total = 0
    failed = 0

    for card_no in new_card_nos:
        entries = qa_data.get(card_no, [])
        if not entries:
            print(f'  [WARN] {card_no}: 無資料，略過', flush=True)
            continue
        if card_no in qa_zh:
            # new_card_nos 已經排除這個情況，這裡是雙重防呆，避免任何邊界情況誤覆蓋
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
    print(f'[完成] 新增卡數：{len(new_card_nos)}  QA 總件數：{total}  失敗：{failed}', flush=True)
    print(f'qa_data_zh.json 現含 {len(qa_zh)} 張卡', flush=True)


if __name__ == '__main__':
    main()
