"""Card database — loads cards_zh.json and provides lookup functions."""
import json
import random
from pathlib import Path

_DB: dict[str, dict] = {}   # card_no → card dict

# position_zh → position code
_POS_ZH_MAP: dict[str, str] = {
    "舉球手":   "SET",
    "側翼攔網手": "WS",
    "中間攔網手": "MB",
    "自由人":   "L",
}


def load_cards(path: str | None = None) -> None:
    """Load cards_zh.json into memory. Call once at startup."""
    global _DB
    if path is None:
        # Default: project root / cards_zh.json
        path = Path(__file__).parent.parent / "cards_zh.json"
    else:
        path = Path(path)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Support both {"cards": [...]} and a flat list
    if isinstance(data, dict) and "cards" in data:
        cards = data["cards"]
    elif isinstance(data, list):
        cards = data
    else:
        raise ValueError(f"Unexpected cards_zh.json structure: {type(data)}")

    _DB = {card["card_no"]: card for card in cards}


def _ensure_loaded() -> None:
    if not _DB:
        load_cards()


def get_card(card_no: str) -> dict | None:
    """Return card dict by card_no (e.g. 'HV-P02-017'). None if not found."""
    _ensure_loaded()
    return _DB.get(card_no)


def get_stat(card_no: str, stat: str) -> int:
    """Return card's stat value (srv/blk/rcv/tos/atk). 0 if not found."""
    card = get_card(card_no)
    if card is None:
        return 0
    return int(card.get(stat) or 0)


def get_cards_by_filter(
    school: str | None = None,
    position: str | None = None,
    category: str | None = None,
    name: str | None = None,
    rarity: str | None = None,
) -> list[dict]:
    """Filter cards by multiple criteria. All supplied filters are ANDed."""
    _ensure_loaded()
    results = []
    for card in _DB.values():
        if school is not None and card.get("school") != school:
            continue
        if position is not None and card.get("position") != position:
            continue
        if category is not None and card.get("category") != category:
            continue
        if name is not None and card.get("name") != name:
            continue
        if rarity is not None and card.get("rarity") != rarity:
            continue
        results.append(card)
    return results


def is_event(card_no: str) -> bool:
    card = get_card(card_no)
    return card is not None and card.get("category") == "EVENT"


def is_character(card_no: str) -> bool:
    card = get_card(card_no)
    return card is not None and card.get("category") == "CHARACTER"


def get_name(card_no: str) -> str:
    card = get_card(card_no)
    return card.get("name", "") if card else ""


def get_school(card_no: str) -> str:
    card = get_card(card_no)
    return card.get("school", "") if card else ""


def get_position(card_no: str) -> str:
    """Return position code: WS, MB, L, SET (from position_zh field).
    Returns empty string for EVENT cards or unknown positions."""
    card = get_card(card_no)
    if card is None:
        return ""
    pos_zh = card.get("position_zh", "")
    return _POS_ZH_MAP.get(pos_zh, "")


def make_deck(card_counts: dict[str, int]) -> list[str]:
    """Build a shuffled deck list from {card_no: count} dict."""
    deck: list[str] = []
    for card_no, count in card_counts.items():
        deck.extend([card_no] * count)
    random.shuffle(deck)
    return deck
