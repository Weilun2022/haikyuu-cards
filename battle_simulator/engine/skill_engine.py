from __future__ import annotations

import re

from battle_simulator.engine.card import Card
from battle_simulator.engine.game_state import PlayerState

# (pattern, effect_key)
_EFFECT_PATTERNS: list[tuple[str, str]] = [
    (r"攻擊值\s*\+(\d+)", "atk_bonus"),
    (r"攔網值\s*\+(\d+)", "blk_bonus"),
    (r"接球值\s*\+(\d+)", "rcv_bonus"),
    (r"發球值\s*\+(\d+)", "srv_bonus"),
    (r"舉球值\s*\+(\d+)", "tos_bonus"),
    (r"抽(\d+)張牌", "draw"),
    (r"接球值(\d+)或以上的接球角色不能出場", "rcv_lock"),
    (r"最多只能出場(\d+)名攔網角色", "blk_lock"),
]


class SkillEngine:
    def parse_guts_cost(self, skill_zh: str) -> int:
        m = re.search(r"支付\s*(\d+)\s*Guts", skill_zh)
        return int(m.group(1)) if m else 0

    def parse_tags(self, skill_zh: str) -> list[str]:
        return re.findall(r"\[=([^\]]+)\]", skill_zh)

    def can_activate(self, card: Card, trigger: str, player: PlayerState) -> bool:
        if trigger not in card.skill_tags:
            return False
        if card.guts_cost > 0 and player.guts < card.guts_cost:
            return False
        return True

    def apply_skill(
        self,
        card: Card,
        trigger: str,
        player: PlayerState,
        opponent: PlayerState,
        log: list[str],
    ) -> None:
        if not self.can_activate(card, trigger, player):
            return

        if card.guts_cost > 0:
            player.guts -= card.guts_cost
            log.append(f"{card.name} 支付 {card.guts_cost} Guts (剩餘 {player.guts})")

        skill = card.skill_zh

        for pattern, effect_key in _EFFECT_PATTERNS:
            m = re.search(pattern, skill)
            if not m:
                continue
            value = int(m.group(1))

            if effect_key == "draw":
                drawn = 0
                for _ in range(value):
                    c = player.draw_card()
                    if c is not None:
                        drawn += 1
                log.append(f"{card.name} 抽 {drawn} 張牌")

            elif effect_key == "rcv_lock":
                # Applied to opponent — they cannot deploy rcv >= value
                opponent.rcv_lock = value
                log.append(f"{card.name} 封鎖: 對手接球值 {value}+ 角色不能出場")

            elif effect_key == "blk_lock":
                # Applied to opponent — limit blk card count
                opponent.blk_lock = value
                log.append(f"{card.name} 封鎖: 對手攔網角色至多 {value} 名")

            else:
                # atk_bonus / blk_bonus / rcv_bonus / srv_bonus / tos_bonus
                current = getattr(player, effect_key, 0)
                setattr(player, effect_key, current + value)
                log.append(f"{card.name} {effect_key} +{value}")

        # Peek top N cards (公開自己的牌庫頂部N張)
        peek_m = re.search(r"公開自己的牌庫頂部(\d+)張", skill)
        if peek_m:
            n = int(peek_m.group(1))
            peeked = player.deck[:n]
            names = [c.name for c in peeked]
            log.append(f"{card.name} 公開牌庫頂部 {n} 張: {names}")
            # Cards matching named targets or 「オープン攻撃」 go to hand (up to 1)
            # This is a simplified heuristic: move the first peeked card to hand
            if peeked:
                taken = player.deck.pop(0)
                player.hand.append(taken)
                log.append(f"{card.name} 牌庫頂部 {taken.name} 加入手牌")
