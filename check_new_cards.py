"""偵測官方是否有新卡，has_new 時自動更新 all_cards.json（含完整性/下架比例安全檢查）。
見 docs/translation/CONTEXT.md「新卡／新QA偵測」。非互動、無需確認——all_cards.json
本來就是可從官方 API 完全重建的可拋棄快取，不是需要保護的資料。
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from haikyuu_downloader import (
    check_for_new_cards, is_fetch_complete, is_removal_suspicious, JSON_PATH,
)


def _format_id_list(ids, limit: int = 30) -> str:
    if not ids:
        return "（無）"
    if len(ids) <= limit:
        return ", ".join(ids)
    return ", ".join(ids[:limit]) + f" ...（共 {len(ids)} 筆，僅顯示前 {limit} 筆）"


def main() -> int:
    result = check_for_new_cards()
    official = result["official_count"]
    local = result["local_count"]
    added = result["added_ids"]
    removed = result["removed_ids"]

    print(f"官方宣告總數: {official}  本地張數: {local}")

    if not result["has_new"]:
        print("沒有新資料，不需要更新。")
        return 0

    fetched = result["fetched_cards"] or []
    print(f"偵測到差異：新增 {len(added)} 筆，下架 {len(removed)} 筆")
    print(f"  新增 ID: {_format_id_list(added)}")
    print(f"  下架 ID: {_format_id_list(removed)}")

    if not is_fetch_complete(len(fetched), official):
        print(f"[ERROR] 抓到的張數（{len(fetched)}）少於官方宣告總數（{official}），"
              f"可能是抓取中途失敗，不寫檔。")
        return 1

    if is_removal_suspicious(len(removed), local):
        print(f"[ERROR] 下架比例異常（{len(removed)}/{local}），可能是官方 API 暫時異常，不寫檔。")
        return 1

    if JSON_PATH.exists():
        backup_path = JSON_PATH.parent / (JSON_PATH.name + ".bak")
        backup_path.write_bytes(JSON_PATH.read_bytes())
        print(f"已備份舊資料至 {backup_path}")

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = JSON_PATH.parent / (JSON_PATH.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(fetched, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, JSON_PATH)
    print(f"已更新 {JSON_PATH}（{len(fetched)} 筆）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
