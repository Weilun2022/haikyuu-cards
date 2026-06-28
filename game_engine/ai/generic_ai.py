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


def _deployable(hand: list[str], stat: str) -> list[str]:
    """手牌中可部署到指定 stat 區域的角色卡（stat 不為 None）。"""
    result = []
    for c in hand:
        if not is_character(c):
            continue
        card = get_card(c)
        if card and card.get(stat) is not None:
            result.append(c)
    return result


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
        - 手牌無可攔網卡（blk stat is None） → 只能 RECEIVE
        - 若手牌攔網值 + center BLK ≥ pending_op 且手牌少 → BLOCK 省資源
        - 否則 RECEIVE（嘗試反攻）
        """
        if pending_op == 0:
            return "receive"

        blk_hand = _deployable(actor.hand, "blk")
        if not blk_hand:
            return "receive"  # 手牌無可攔網卡，強制 RECEIVE

        center_blk = get_stat(actor.block_zones[0].card, "blk") if actor.block_zones[0].card else 0
        # center 卡會保留（側翼才在 block 後退場），新卡填側翼
        top_blk = sorted(blk_hand, key=lambda c: get_stat(c, "blk"), reverse=True)[:2]
        potential_blk = center_blk + sum(get_stat(c, "blk") for c in top_blk)

        hand_size = len(actor.hand)

        if potential_blk >= pending_op:
            if hand_size <= 3:
                return "block"
            best_tos = max((_deployable(actor.hand, "tos") or [""]), key=lambda c: get_stat(c, "tos"))
            best_atk = max((_deployable(actor.hand, "atk") or [""]), key=lambda c: get_stat(c, "atk"))
            potential_atk = get_stat(best_tos, "tos") + get_stat(best_atk, "atk")
            if potential_atk >= 5:
                return "receive"
            return "block"

        return "receive"

    def decide_block_chars(
        self, actor: PlayerState, state: GameState, pending_op: int
    ) -> list[str]:
        """從手牌選 blk stat 不為 None 的角色，最多 3 張（BLK 高優先）。"""
        eligible = _deployable(actor.hand, "blk")
        return sorted(eligible, key=lambda c: get_stat(c, "blk"), reverse=True)[:3]

    def decide_receive_char(
        self, actor: PlayerState, state: GameState, pending_op: int
    ) -> str | None:
        """強制部署：選手牌中 RCV 最高的可接球角色（stat 不為 None）。"""
        eligible = _deployable(actor.hand, "rcv")
        if not eligible:
            return None
        return max(eligible, key=lambda c: get_stat(c, "rcv"))

    def decide_toss_char(self, actor: PlayerState, state: GameState) -> str | None:
        """強制部署：選手牌中 TOS 最高的可舉球角色（stat 不為 None）。"""
        eligible = _deployable(actor.hand, "tos")
        if not eligible:
            return None
        return max(eligible, key=lambda c: get_stat(c, "tos"))

    def decide_attack_char(self, actor: PlayerState, state: GameState) -> str | None:
        """強制部署：選手牌中 ATK 最高的可攻擊角色（stat 不為 None）。"""
        eligible = _deployable(actor.hand, "atk")
        if not eligible:
            return None
        return max(eligible, key=lambda c: get_stat(c, "atk"))

    def decide_discard(
        self, hand: list[str], state: GameState, actor: PlayerState, count: int = 1
    ) -> list[str]:
        """棄牌選擇：優先棄事件牌，再棄各 stat 加總最低的角色。"""
        events = [c for c in hand if is_event(c)]
        chars  = [c for c in hand if not is_event(c)]
        chars_sorted = sorted(chars, key=lambda c: sum(
            get_stat(c, s) or 0 for s in ("srv", "blk", "rcv", "tos", "atk")
        ))
        candidates = events + chars_sorted
        return candidates[:count]

    def decide_skill_choice(self, choices, state: GameState, actor: PlayerState) -> int:
        """技能分支選擇：預設選第 0 項。"""
        return 0

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
        if not _deployable(actor.hand, "blk"):
            return "receive"
        center_blk = get_stat(actor.block_zones[0].card, "blk") if actor.block_zones[0].card else 0
        top2 = sorted(_deployable(actor.hand, "blk"), key=lambda c: get_stat(c, "blk"), reverse=True)[:2]
        total_blk = center_blk + sum(get_stat(c, "blk") for c in top2)
        if total_blk >= pending_op * 0.7:
            return "block"
        return "receive"

    def decide_action(self, state: GameState, actor: PlayerState) -> str:
        return "attack"
