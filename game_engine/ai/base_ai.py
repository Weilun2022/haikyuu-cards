"""game_engine/ai/base_ai.py — AI 決策抽象介面"""
from __future__ import annotations
from abc import ABC, abstractmethod
from game_engine.schema import GameState, PlayerState


class BaseAI(ABC):
    def __init__(self, player_num: int, name: str = "AI"):
        self.player_num = player_num
        self.name = name

    # ── 舊 API（保留相容性）────────────────────────────────────────────────────

    def decide_main_phase(self, state: GameState, actor: PlayerState) -> dict:
        return {"deploy": [], "guts": [], "event_activate": []}

    def decide_action(self, state: GameState, actor: PlayerState) -> str:
        return "attack"

    # ── 新 phase-based API ────────────────────────────────────────────────────

    def decide_serve_char(self, actor: PlayerState, state: GameState) -> str | None:
        """SERVE PHASE: 選擇要出場的發球角色 card_no。None = 不換（沿用現有）。"""
        from game_engine.card_db import get_stat, is_character
        chars = [c for c in actor.hand if is_character(c)]
        if not chars:
            return None
        existing_srv = get_stat(actor.serve_zone.card, "srv") if actor.serve_zone.card else -1
        best = max(chars, key=lambda c: get_stat(c, "srv"))
        if get_stat(best, "srv") > existing_srv:
            return best
        return None

    def decide_start_phase(
        self, actor: PlayerState, state: GameState, pending_op: int
    ) -> str:
        """START PHASE: 選擇 'block' 或 'receive'。"""
        return "receive"  # 預設：接球路線

    def decide_block_chars(
        self, actor: PlayerState, state: GameState, pending_op: int
    ) -> list[str]:
        """BLOCK PHASE: 選擇要出場的攔網角色（最多3張）。"""
        from game_engine.card_db import get_stat, is_character
        chars = [c for c in actor.hand if is_character(c)]
        chars.sort(key=lambda c: get_stat(c, "blk"), reverse=True)
        return chars[:3]

    def decide_receive_char(
        self, actor: PlayerState, state: GameState, pending_op: int
    ) -> str | None:
        """RECEIVE PHASE: 選擇接球角色。None = 使用現有。"""
        from game_engine.card_db import get_stat, is_character
        chars = [c for c in actor.hand if is_character(c)]
        if not chars:
            return None
        existing = get_stat(actor.receive_zone.card, "rcv") if actor.receive_zone.card else -1
        best = max(chars, key=lambda c: get_stat(c, "rcv"))
        if get_stat(best, "rcv") > existing:
            return best
        return None

    def decide_toss_char(self, actor: PlayerState, state: GameState) -> str | None:
        """TOSS PHASE: 選擇舉球角色。"""
        from game_engine.card_db import get_stat, is_character
        chars = [c for c in actor.hand if is_character(c)]
        if not chars:
            return None
        existing = get_stat(actor.toss_zone.card, "tos") if actor.toss_zone.card else -1
        best = max(chars, key=lambda c: get_stat(c, "tos"))
        if get_stat(best, "tos") > existing:
            return best
        return None

    def decide_attack_char(self, actor: PlayerState, state: GameState) -> str | None:
        """ATTACK PHASE: 選擇攻擊角色。"""
        from game_engine.card_db import get_stat, is_character
        chars = [c for c in actor.hand if is_character(c)]
        if not chars:
            return None
        existing = get_stat(actor.attack_zone.card, "atk") if actor.attack_zone.card else -1
        best = max(chars, key=lambda c: get_stat(c, "atk"))
        if get_stat(best, "atk") > existing:
            return best
        return None

    def decide_discard(
        self, hand: list[str], state: GameState, actor: PlayerState, count: int = 1
    ) -> list[str]:
        """
        選擇要棄置的手牌（費用或強制棄牌時）。
        預設策略：優先棄同名複本 > 無技能低值卡 > 第一張。
        """
        from game_engine.card_db import get_card, is_event
        if not hand:
            return []
        scored: list[tuple[int, str]] = []
        name_count: dict[str, int] = {}
        for c in hand:
            n = (get_card(c) or {}).get("name", c)
            name_count[n] = name_count.get(n, 0) + 1
        for c in hand:
            card = get_card(c) or {}
            n = card.get("name", c)
            score = 0
            if name_count.get(n, 0) > 1:
                score -= 10  # 有複本，優先棄
            if is_event(c):
                score += 5   # 保留 Event
            skill = (card.get("skill_zh") or "").strip()
            if not skill:
                score -= 3   # 無技能卡優先棄
            # 數值越低越先棄
            total_stat = sum(int(card.get(s) or 0) for s in ("atk", "rcv", "blk", "tos", "srv"))
            score += total_stat
            scored.append((score, c))
        scored.sort()
        return [c for _, c in scored[:count]]

    def decide_recover_target(
        self, candidates: list[str], state: GameState, actor: PlayerState
    ) -> str | None:
        """選擇從棄牌區取回的卡。預設取第一張。"""
        return candidates[0] if candidates else None

    def decide_skill_choice(
        self, choices: list, state: GameState, actor: PlayerState
    ) -> int:
        """▶ 分支技能的選擇。預設選第 0 項。"""
        return 0

    def decide_guts_card(
        self, hand: list[str], zone: str,
        state: GameState, actor: PlayerState
    ) -> str | None:
        """決定放哪張牌到指定 Guts 池。預設：最低值的無技能角色卡。"""
        from game_engine.card_db import get_card, is_event, is_character
        chars = [c for c in hand if is_character(c)]
        if not chars:
            return None
        stat_map = {"toss": "tos", "attack": "atk", "receive": "rcv",
                    "block": "blk", "serve": "srv"}
        s = stat_map.get(zone, "atk")

        def _sort_key(c: str) -> tuple[int, int]:
            card = get_card(c) or {}
            has_skill = bool((card.get("skill_zh") or "").strip())
            val = int(card.get(s) or 0)
            return (0 if not has_skill else 1, -val)  # 無技能 + 低值優先

        return sorted(chars, key=_sort_key)[0]
