"""game_engine/ai/generic_ai.py — 通用 Greedy AI（適用所有學校）"""
from __future__ import annotations
from game_engine.ai.base_ai import BaseAI
from game_engine.schema import GameState, PlayerState
from game_engine.card_db import get_stat, get_card, is_event, is_character


def _best_char(hand: list[str], stat: str) -> tuple[str | None, int]:
    chars = [c for c in hand if is_character(c)]
    if not chars:
        return None, 0
    best = max(chars, key=lambda c: get_stat(c, stat))
    return best, get_stat(best, stat)


def _top_n_chars(hand: list[str], stat: str, n: int) -> list[str]:
    chars = [c for c in hand if is_character(c)]
    return sorted(chars, key=lambda c: get_stat(c, stat), reverse=True)[:n]


class GenericAI(BaseAI):
    """
    Greedy AI：依最大化當前階段數值的貪婪策略決策。
    BLOCK vs RECEIVE 選擇：比較「最佳攔網值」與「對手 OP」。
    """

    def decide_serve_char(self, actor: PlayerState, state: GameState) -> str | None:
        existing_val = get_stat(actor.serve_zone.card, "srv") if actor.serve_zone.card else -1
        best, val = _best_char(actor.hand, "srv")
        # 有能發球的卡且比現有更好才換
        if best and val > existing_val and get_card(best).get("srv") is not None:
            return best
        return None  # 沿用現有 serve zone 卡

    def decide_start_phase(
        self, actor: PlayerState, state: GameState, pending_op: int
    ) -> str:
        """
        策略：
        - OP=0 → 一定 RECEIVE（免費球，反攻！攔網 OP=0 毫無意義）
        - 若手牌攔網值 + center BLK ≥ pending_op 且手牌少 → BLOCK 省資源
        - 否則 RECEIVE（嘗試反攻）
        """
        # OP=0 是「免費球」，一律接球反攻；否則死循環
        if pending_op == 0:
            return "receive"

        center_blk = get_stat(actor.block_zones[0].card, "blk") if actor.block_zones[0].card else 0
        hand_blk_cards = _top_n_chars(actor.hand, "blk", 3)
        potential_blk = center_blk + sum(get_stat(c, "blk") for c in hand_blk_cards)

        hand_size = len(actor.hand)

        if potential_blk >= pending_op:
            # 攔網值夠 → 若手牌少就 BLOCK 省資源
            if hand_size <= 3:
                return "block"
            # 計算若 RECEIVE → ATTACK 能打出多少
            best_tos = _best_char(actor.hand, "tos")[1]
            best_atk = _best_char(actor.hand, "atk")[1]
            potential_atk = best_tos + best_atk
            if potential_atk >= 5:
                return "receive"
            return "block"

        # 攔不住 → 只能 RECEIVE
        return "receive"

    def decide_block_chars(
        self, actor: PlayerState, state: GameState, pending_op: int
    ) -> list[str]:
        """選最多 3 張 BLK 最高的角色，優先補 center 空位。"""
        return _top_n_chars(actor.hand, "blk", 3)

    def decide_receive_char(
        self, actor: PlayerState, state: GameState, pending_op: int
    ) -> str | None:
        existing = get_stat(actor.receive_zone.card, "rcv") if actor.receive_zone.card else -1
        best, val = _best_char(actor.hand, "rcv")
        if best and get_card(best).get("rcv") is not None and val > existing:
            return best
        return None

    def decide_toss_char(self, actor: PlayerState, state: GameState) -> str | None:
        existing = get_stat(actor.toss_zone.card, "tos") if actor.toss_zone.card else -1
        best, val = _best_char(actor.hand, "tos")
        if best and get_card(best).get("tos") is not None and val > existing:
            return best
        return None

    def decide_attack_char(self, actor: PlayerState, state: GameState) -> str | None:
        existing = get_stat(actor.attack_zone.card, "atk") if actor.attack_zone.card else -1
        best, val = _best_char(actor.hand, "atk")
        if best and get_card(best).get("atk") is not None and val > existing:
            return best
        return None

    # ── 舊 API 相容 ───────────────────────────────────────────────────────────

    def decide_main_phase(self, state: GameState, actor: PlayerState) -> dict:
        return {"deploy": [], "guts": [], "event_activate": []}

    def decide_action(self, state: GameState, actor: PlayerState) -> str:
        return "attack"


class AggressiveAI(GenericAI):
    """激進 AI：永遠選 RECEIVE（優先進攻）。"""

    def decide_start_phase(
        self, actor: PlayerState, state: GameState, pending_op: int
    ) -> str:
        return "receive"

    def decide_action(self, state: GameState, actor: PlayerState) -> str:
        return "attack"


class DefensiveAI(GenericAI):
    """守備 AI：盡可能 BLOCK。"""

    def decide_start_phase(
        self, actor: PlayerState, state: GameState, pending_op: int
    ) -> str:
        center_blk = get_stat(actor.block_zones[0].card, "blk") if actor.block_zones[0].card else 0
        hand_blk = sum(get_stat(c, "blk") for c in _top_n_chars(actor.hand, "blk", 2))
        total_blk = center_blk + hand_blk
        # 只要有一點攔截可能就 BLOCK
        if total_blk >= pending_op * 0.7:
            return "block"
        return "receive"

    def decide_action(self, state: GameState, actor: PlayerState) -> str:
        return "attack"
