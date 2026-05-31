from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Card:
    id: str
    card_no: str
    name: str
    category: str       # CHARACTER or EVENT
    school: str
    rarity: str
    position: str       # MB, WS, S, Li, OP, -, etc.
    srv: int
    blk: int
    rcv: int
    tos: int
    atk: int
    skill_zh: str
    skill_tags: list[str] = field(default_factory=list)   # e.g. ['登場','攻擊區']
    guts_cost: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "Card":
        skill_zh = d.get("skill_zh") or ""

        tags = re.findall(r"\[=([^\]]+)\]", skill_zh)
        # Filter to trigger/zone tags, excluding special effect tags that contain numbers/brackets
        trigger_tags = [t for t in tags if not re.search(r"\d", t)]

        guts_match = re.search(r"支付\s*(\d+)\s*Guts", skill_zh)
        guts_cost = int(guts_match.group(1)) if guts_match else 0

        def _int(val: object) -> int:
            try:
                return int(val)
            except (TypeError, ValueError):
                return 0

        return cls(
            id=str(d.get("id", "")),
            card_no=str(d.get("card_no", "")),
            name=str(d.get("name", "")),
            category=str(d.get("category", "")),
            school=str(d.get("school", "")),
            rarity=str(d.get("rarity", "")),
            position=str(d.get("position", "-")),
            srv=_int(d.get("srv")),
            blk=_int(d.get("blk")),
            rcv=_int(d.get("rcv")),
            tos=_int(d.get("tos")),
            atk=_int(d.get("atk")),
            skill_zh=skill_zh,
            skill_tags=trigger_tags,
            guts_cost=guts_cost,
        )

    def has_tag(self, tag: str) -> bool:
        return tag in self.skill_tags

    def zone_type(self) -> str:
        if self.category == "EVENT":
            return "evt"

        # Map each zone stat to its name
        stats = {
            "srv": self.srv,
            "blk": self.blk,
            "rcv": self.rcv,
            "tos": self.tos,
            "atk": self.atk,
        }

        # Use skill tags to break ties / guide placement
        tag_zone_map = {
            "攻擊區": "atk",
            "攔網區": "blk",
            "接球區": "rcv",
            "舉球區": "tos",
            "發球區": "srv",
        }
        for tag, zone in tag_zone_map.items():
            if self.has_tag(tag):
                return zone

        # Position hints
        position_zone_map = {
            "MB": "atk",
            "WS": "atk",
            "S": "tos",
            "Li": "rcv",
            "OP": "srv",
        }
        # position may be composite like "MB,WS" — take first token
        primary_pos = self.position.split(",")[0].strip()
        if primary_pos in position_zone_map:
            return position_zone_map[primary_pos]

        # Fallback: highest non-zero stat wins
        best_zone = max((z for z, v in stats.items() if v > 0), key=lambda z: stats[z], default="atk")
        return best_zone
