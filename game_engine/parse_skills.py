"""
game_engine/parse_skills.py — 用 claude-haiku-4-5 解析所有卡片技能
將 skill_zh 文字轉為結構化 JSON (CardSkill 格式)，儲存至 cards_skills.json

用法:
  # 設定 OpenRouter Key
  set OPENROUTER_KEY=sk-or-v1-...

  python game_engine/parse_skills.py                  # 全部 518 張
  python game_engine/parse_skills.py --batch 5        # 只處理 5 張（測試用）
  python game_engine/parse_skills.py --resume         # 跳過已解析的卡片
  python game_engine/parse_skills.py --card HV-P02-017  # 只解析指定卡
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import requests

# ── 路徑設定 ──────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
CARDS_JSON   = ROOT / "cards_zh.json"
OUTPUT_JSON  = Path(__file__).parent / "cards_skills.json"

# ── OpenRouter 設定 ────────────────────────────────────────
OR_URL   = "https://openrouter.ai/api/v1/chat/completions"
OR_MODEL = "anthropic/claude-haiku-4-5"

SYSTEM_PROMPT = """\
你是排球少年!! TCG（集換式卡牌遊戲）規則專家。
請將提供的卡片技能文字（繁體中文）解析為結構化 JSON。
只輸出合法的 JSON，不要加任何說明或 markdown 標記。"""

# 可用的 EffectType 值
EFFECT_TYPES = [
    "stat_bonus","stat_set","stat_immunity",
    "draw","discard_from_hand","recover_char","recover_event",
    "recover_from_event_zone","add_to_hand_from_pile",
    "deploy_from_grave","deploy_from_guts","return_to_hand","return_to_pile",
    "move_to_zone","move_guts_to_zone","tap_deploy","swap_zone",
    "pile_peek","pile_peek_and_keep","shuffle_pile","event_zone_place",
    "opp_discard_from_event","opp_stat_reduce","opp_stat_set",
    "opp_blk_zero","opp_zone_lock","opp_skill_nullify","opp_phase_modify",
    "phase_control","guts_bonus","counter_add",
]

# 可用的 ConditionType 值
CONDITION_TYPES = [
    "always","six_unique","grave_unique_ge","card_in_grave",
    "hand_le","hand_ge","hand_has",
    "all_same_school","multi_school_ge",
    "zone_occupied","zone_empty",
    "setter_is","attacker_is","libero_in_receive","self_is_receiver",
    "skill_deploy","named_skill_deploy","deploy_as_position","from_hand",
    "opp_atk_ge","opp_srv_le","opp_event_zone_le","opp_has_card",
    "guts_all_rarity","guts_has_named","is_yosu","pile_top_matches","counter_ge",
]

USER_PROMPT_TEMPLATE = """\
請解析以下卡片技能：

卡號: {card_no}
名稱: {name}
學校: {school}
位置: {position_zh}
數值: SRV={srv} BLK={blk} RCV={rcv} TOS={tos} ATK={atk}
技能文字: {skill_zh}

輸出 JSON 格式（嚴格對應此結構）：
{{
  "triggers": [],
  "zone_qualifiers": [],
  "conditions": [{{"type": "...", "param": null}}],
  "costs": {{"guts": 0, "discard": 0, "discard_filter": {{}}, "place_to_event": false}},
  "effects": [{{
    "effect_type": "...",
    "target": "self",
    "stat": null,
    "amount": 0,
    "duration": "permanent",
    "zone": null,
    "from_zone": null,
    "to_zone": null,
    "pile_position": "top",
    "card_filter": {{"school": null, "position": null, "name": null, "max_count": 1}}
  }}],
  "choices": [],
  "once_per_turn": false,
  "volleyball_threshold": null,
  "notes": ""
}}

規則：
- triggers: 從 [=...] 標籤中提取，例如 ["登場","攻擊區"]
- zone_qualifiers: 部署目標區域，例如 ["攻擊區"]
- conditions: 技能發動條件清單（AND 邏輯）
  - 六種類 → {{"type":"six_unique"}}
  - 手牌≤N → {{"type":"hand_le","param":N}}
  - 舉球角色是「X」 → {{"type":"setter_is","param":"X"}}
  - 自己角色全是同一學校 → {{"type":"all_same_school","param":null}}
  - 技能出場 → {{"type":"skill_deploy"}}
  - 對手進攻值≥N → {{"type":"opp_atk_ge","param":N}}
  - 無特殊條件 → [{{"type":"always"}}]
- costs.guts: 支付 Guts 數量
- costs.discard: 棄置手牌數量作為費用
- effects: 技能效果清單
  - 數值+N → {{"effect_type":"stat_bonus","stat":"atk/rcv/blk/tos/srv/any","amount":N}}
  - 抽N張 → {{"effect_type":"draw","amount":N}}
  - 從棄牌區取角色→手牌 → {{"effect_type":"recover_char","card_filter":{{...}}}}
  - 對手下回合MB攔網無效 → {{"effect_type":"opp_blk_zero","duration":"next_turn"}}
  - 數值設為N → {{"effect_type":"stat_set","stat":"blk","amount":0,"target":"opponent"}}
  - 立即結束某階段 → {{"effect_type":"phase_control","phase":"block"}}
- choices: ▶ 選一格式 → [{{"choices":[[effect1],[effect2]],"must_choose":1}}]
- volleyball_threshold: [封殺攔網(N)] 中的 N 值
- duration: "permanent","this_turn","next_turn"

可用 effect_type 值: {effect_types}
可用 condition type 值: {condition_types}
""".format(
    card_no="{card_no}", name="{name}", school="{school}",
    position_zh="{position_zh}", srv="{srv}", blk="{blk}",
    rcv="{rcv}", tos="{tos}", atk="{atk}", skill_zh="{skill_zh}",
    effect_types=", ".join(EFFECT_TYPES),
    condition_types=", ".join(CONDITION_TYPES),
)


def get_api_key() -> str:
    key = os.environ.get("OPENROUTER_KEY", "")
    if not key:
        raise RuntimeError(
            "請設定環境變數 OPENROUTER_KEY\n"
            "  Windows: set OPENROUTER_KEY=sk-or-v1-...\n"
            "  Linux/Mac: export OPENROUTER_KEY=sk-or-v1-..."
        )
    return key


def call_haiku(prompt_text: str, api_key: str) -> str:
    resp = requests.post(
        OR_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": OR_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt_text},
            ],
            "max_tokens": 1200,
            "temperature": 0.1,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def parse_one_card(card: dict, api_key: str) -> dict:
    """呼叫 haiku 解析一張卡，回傳 CardSkill dict（含 card_no + raw_text）。"""
    # 用 replace() 而非 .format()，避免 JSON 範例中的 {} 被誤判為格式化佔位符
    prompt = USER_PROMPT_TEMPLATE
    for placeholder, value in [
        ("{card_no}",     card.get("card_no", "")),
        ("{name}",        card.get("name", "")),
        ("{school}",      card.get("school", "")),
        ("{position_zh}", card.get("position_zh", "")),
        ("{srv}",         str(card.get("srv") or 0)),
        ("{blk}",         str(card.get("blk") or 0)),
        ("{rcv}",         str(card.get("rcv") or 0)),
        ("{tos}",         str(card.get("tos") or 0)),
        ("{atk}",         str(card.get("atk") or 0)),
        ("{skill_zh}",    card.get("skill_zh", "")),
    ]:
        prompt = prompt.replace(placeholder, str(value))

    raw = call_haiku(prompt, api_key)

    # 嘗試解析 JSON
    text = raw.strip()

    # 去掉 ```json ... ``` 包裝
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            s = p.strip()
            if s.startswith("json"):
                s = s[4:].strip()
            if s.startswith("{"):
                text = s
                break

    # 若 haiku 只輸出 key-value 而沒有外層 {}
    if text and not text.startswith("{"):
        text = "{" + text
    if text and not text.rstrip().endswith("}"):
        text = text.rstrip().rstrip(",") + "\n}"

    result = json.loads(text)
    result["card_no"]   = card["card_no"]
    result["raw_text"]  = card.get("skill_zh", "")
    return result


def main():
    ap = argparse.ArgumentParser(description="解析 cards_zh.json 技能 → cards_skills.json")
    ap.add_argument("--batch", type=int, default=0,    help="只處理前 N 張（0=全部）")
    ap.add_argument("--resume", action="store_true",   help="跳過已解析的卡片")
    ap.add_argument("--card",   default="",            help="只解析單張卡 (card_no)")
    ap.add_argument("--delay",  type=float, default=0.6, help="API 呼叫間隔秒數")
    ap.add_argument("--model",  default=OR_MODEL,      help="覆蓋 OpenRouter 模型")
    args = ap.parse_args()

    api_key = get_api_key()

    # 讀入卡片資料
    with open(CARDS_JSON, encoding="utf-8") as f:
        all_cards: list[dict] = json.load(f)["cards"]

    # 讀入已有結果
    existing: dict[str, dict] = {}
    if OUTPUT_JSON.exists():
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            existing = json.load(f)

    # 篩選要處理的卡片
    if args.card:
        targets = [c for c in all_cards if c.get("card_no") == args.card]
    else:
        targets = [c for c in all_cards if (c.get("skill_zh") or "").strip()]
        if args.resume:
            targets = [c for c in targets if c["card_no"] not in existing]
        if args.batch:
            targets = targets[: args.batch]

    print(f"待解析: {len(targets)} 張 | 已有: {len(existing)} 張")
    print(f"輸出: {OUTPUT_JSON}\n")

    ok = err = skip = 0
    for i, card in enumerate(targets, 1):
        cno = card.get("card_no", "?")
        print(f"[{i:>3}/{len(targets)}] {cno} {card.get('name','')[:12]}", end=" ... ", flush=True)

        try:
            result = parse_one_card(card, api_key)
            existing[cno] = result
            ok += 1
            print("OK")
        except json.JSONDecodeError as e:
            existing[cno] = {
                "card_no": cno,
                "raw_text": card.get("skill_zh", ""),
                "parse_error": str(e),
                "triggers": [], "zone_qualifiers": [], "conditions": [],
                "costs": {"guts":0,"discard":0,"discard_filter":{},"place_to_event":False},
                "effects": [], "choices": [], "once_per_turn": False,
                "volleyball_threshold": None, "notes": "JSON parse failed",
            }
            err += 1
            print(f"JSON ERR: {e}")
        except Exception as e:
            err += 1
            print(f"ERR: {e}")

        # 每 10 張自動存檔
        if i % 10 == 0:
            _save(existing)

        if i < len(targets):
            time.sleep(args.delay)

    _save(existing)
    print(f"\n完成 ✓ OK={ok} ERR={err} SKIP={skip} | 總計 {len(existing)} 張")


def _save(data: dict) -> None:
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
