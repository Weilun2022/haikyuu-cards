from __future__ import annotations

import json
import re
from pathlib import Path

_CARDS_JS = Path(__file__).parent.parent / "cards_data.js"
_cache: list[dict] | None = None


def load_all_cards() -> list[dict]:
    global _cache
    if _cache is not None:
        return _cache

    content = _CARDS_JS.read_text(encoding="utf-8")
    # Strip leading comment lines
    content = re.sub(r"^(?://[^\n]*\n)+", "", content)
    # Strip `const CARDS_DATA = ` prefix and trailing `;`
    content = re.sub(r"^const CARDS_DATA\s*=\s*", "", content.strip())
    content = content.rstrip(";\n")

    data = json.loads(content)
    _cache = data["cards"]
    return _cache


def get_characters() -> list[dict]:
    return [c for c in load_all_cards() if c.get("category") == "CHARACTER"]


def get_by_school(school: str) -> list[dict]:
    return [c for c in load_all_cards() if c.get("school") == school]


def get_events() -> list[dict]:
    return [c for c in load_all_cards() if c.get("category") == "EVENT"]
