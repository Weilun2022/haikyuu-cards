"""game_engine/ai/greedy_ai.py — 帶難度設定的 Greedy AI（練習模式用）。"""
from __future__ import annotations

import random
from game_engine.ai.generic_ai import GenericAI
from game_engine.schema import GameState, PlayerState


class GreedyAI(GenericAI):
    """
    Greedy AI with configurable difficulty for human vs AI practice mode.

    difficulty:
      "easy"   — 決策加入隨機錯誤，模擬初學者
      "normal" — 標準 GenericAI greedy 策略（預設）
      "hard"   — aggressive：更積極替換區域角色，提前佈局
    """

    def __init__(self, player_num: int, difficulty: str = "normal", name: str | None = None):
        super().__init__(player_num, name=name or f"AI({difficulty})")
        self.difficulty = difficulty
        self._rng = random.Random()  # 獨立 RNG，不影響主遊戲隨機性

    # ── 難度分層 ─────────────────────────────────────────────────────────────

    def decide_start_phase(
        self, actor: PlayerState, state: GameState, pending_op: int
    ) -> str:
        base = super().decide_start_phase(actor, state, pending_op)
        if self.difficulty == "easy" and self._rng.random() < 0.25:
            return "block" if base == "receive" else "receive"  # 25% 機率選錯
        return base

    def decide_attack_char(self, actor: PlayerState, state: GameState) -> str | None:
        if self.difficulty == "easy":
            # easy: 隨機選一張角色（不一定是最高 atk）
            from game_engine.card_db import is_character
            chars = [c for c in actor.hand if is_character(c)]
            return self._rng.choice(chars) if chars else None
        return super().decide_attack_char(actor, state)

    def decide_receive_char(
        self, actor: PlayerState, state: GameState, pending_op: int
    ) -> str | None:
        if self.difficulty == "hard":
            # hard: 只要手牌有更好的就換（原來 base_ai 預設只在超過現有才換）
            from game_engine.card_db import get_stat, is_character
            chars = [c for c in actor.hand if is_character(c)]
            if not chars:
                return None
            best = max(chars, key=lambda c: get_stat(c, "rcv"))
            # 即使現有也 OK，hard 仍嘗試升級
            return best
        return super().decide_receive_char(actor, state, pending_op)

    def seed(self, value: int) -> None:
        """允許外部固定 RNG 種子，方便重現性測試。"""
        self._rng.seed(value)
