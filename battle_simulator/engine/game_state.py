from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from battle_simulator.engine.card import Card

_ZONES = ("srv", "blk", "rcv", "tos", "atk")


@dataclass
class PlayerState:
    name: str
    deck: list[Card]
    hand: list[Card]
    field: dict  # {'srv': Card|None, 'blk': Card|None, 'rcv': Card|None,
                 #  'tos': Card|None, 'atk': Card|None, 'evt': list[Card]}
    guts: int
    score: int
    discard: list[Card]

    # Per-turn stat bonuses (reset each turn end)
    atk_bonus: int = 0
    blk_bonus: int = 0
    rcv_bonus: int = 0
    srv_bonus: int = 0
    tos_bonus: int = 0

    # Restrictions set by opponent skills
    rcv_lock: int = 0   # opponent cannot deploy rcv chars with base rcv >= this value (0 = no lock)
    blk_lock: int = 0   # max blk cards opponent may deploy this turn (0 = no limit)

    @classmethod
    def new(cls, name: str, deck: list[Card], shuffle: bool = True) -> "PlayerState":
        cards = list(deck)
        if shuffle:
            random.shuffle(cards)
        return cls(
            name=name,
            deck=cards,
            hand=[],
            field={"srv": None, "blk": None, "rcv": None, "tos": None, "atk": None, "evt": []},
            guts=3,
            score=0,
            discard=[],
        )

    def draw_card(self) -> Card | None:
        if not self.deck:
            return None
        card = self.deck.pop(0)
        self.hand.append(card)
        return card

    def effective_stat(self, zone: str) -> int:
        if zone == "evt":
            return 0
        card = self.field.get(zone)
        base = getattr(card, zone, 0) if card else 0
        bonus = getattr(self, f"{zone}_bonus", 0)
        return base + bonus

    def total_field_stat(self, stat: str) -> int:
        total = 0
        for zone in _ZONES:
            card = self.field.get(zone)
            if card is not None:
                total += getattr(card, stat, 0)
        for card in self.field.get("evt", []):
            total += getattr(card, stat, 0)
        return total

    def reset_turn_bonuses(self) -> None:
        self.atk_bonus = 0
        self.blk_bonus = 0
        self.rcv_bonus = 0
        self.srv_bonus = 0
        self.tos_bonus = 0

    def reset_restrictions(self) -> None:
        self.rcv_lock = 0
        self.blk_lock = 0


@dataclass
class GameState:
    p1: PlayerState
    p2: PlayerState
    turn: int = 1
    current_player: int = 1   # 1 or 2
    phase: str = "draw"       # 'draw','play','action','end'
    game_log: list[str] = field(default_factory=list)

    def active(self) -> PlayerState:
        return self.p1 if self.current_player == 1 else self.p2

    def passive(self) -> PlayerState:
        return self.p2 if self.current_player == 1 else self.p1

    def is_terminal(self) -> bool:
        return (
            self.p1.score >= 7
            or self.p2.score >= 7
            or not self.p1.deck
            or not self.p2.deck
        )

    def winner(self) -> int | None:
        if self.p1.score >= 7:
            return 1
        if self.p2.score >= 7:
            return 2
        if not self.p1.deck and not self.p2.deck:
            return 1 if self.p1.score > self.p2.score else 2
        if not self.p1.deck:
            return 2
        if not self.p2.deck:
            return 1
        return None

    def log(self, msg: str) -> None:
        self.game_log.append(f"[T{self.turn}P{self.current_player}] {msg}")
