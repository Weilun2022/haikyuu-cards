"""
deck_evo/genome.py — 牌組基因組
封裝一副牌組及其評估結果。
"""
from __future__ import annotations
import copy
import random
from dataclasses import dataclass, field


@dataclass
class DeckGenome:
    cards: dict[str, int]           # card_no → count
    name: str = ""
    generation: int = 0
    win_rate: float = 0.0
    games_played: int = 0
    card_scores: dict[str, float] = field(default_factory=dict)  # contribution [0,1]
    is_elite: bool = False

    # 關鍵對局紀錄（winner=自, turns, p1_sets, p2_sets, replay_path）
    key_replays: list[dict] = field(default_factory=list)

    def total(self) -> int:
        return sum(self.cards.values())

    def clone(self) -> "DeckGenome":
        g = copy.deepcopy(self)
        g.win_rate = 0.0
        g.games_played = 0
        g.card_scores = {}
        g.is_elite = False
        g.key_replays = []
        return g

    def low_score_cards(self, n: int = 5) -> list[str]:
        """傳回貢獻分最低的 n 張牌（用於突變時優先替換）。"""
        if not self.card_scores:
            return []
        return sorted(self.card_scores, key=self.card_scores.get)[:n]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "generation": self.generation,
            "win_rate": round(self.win_rate, 4),
            "games_played": self.games_played,
            "cards": self.cards,
            "card_scores": {k: round(v, 4) for k, v in self.card_scores.items()},
            "is_elite": self.is_elite,
        }
