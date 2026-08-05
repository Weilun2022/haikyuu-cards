"""補抓新卡的 Q&A 資料並合併到 qa_data.json —— 只抓 qa_data.json 裡還沒有的 card_no。
底層抓取邏輯改呼叫 haikyuu_downloader.fetch_qa_data(only_missing=...)，不再自己複製一份。
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from haikyuu_downloader import fetch_qa_data, JSON_PATH, QA_PATH

with open(JSON_PATH, encoding="utf-8") as f:
    all_cards = json.load(f)

with open(QA_PATH, encoding="utf-8") as f:
    qa_data = json.load(f)

# 找出尚未有 QA 資料的 card_no（包含新卡和空資料卡）——不重抓已存在的 card_no 這個不變量維持不變
all_nos = sorted(set(c["card_no"] for c in all_cards if c.get("card_no")))
missing = [no for no in all_nos if no not in qa_data]
print(f"全部 card_no: {len(all_nos)}  已有: {len(qa_data)}  待抓: {len(missing)}")

if missing:
    new_qa = fetch_qa_data(all_cards, only_missing=missing)
    qa_data.update(new_qa)

with open(QA_PATH, "w", encoding="utf-8") as f:
    json.dump(qa_data, f, ensure_ascii=False, indent=2)

total_qa = sum(len(v) for v in qa_data.values())
cards_with_qa = sum(1 for v in qa_data.values() if v)
print(f"\n完成！共 {len(qa_data)} 張卡  有 Q&A: {cards_with_qa} 張 / {total_qa} 條")
print(f"已儲存: {QA_PATH}")
