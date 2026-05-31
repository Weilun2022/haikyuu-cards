from __future__ import annotations

from battle_simulator.engine.action_resolver import ActionResolver
from battle_simulator.engine.card import Card
from battle_simulator.engine.game_state import GameState, PlayerState
from battle_simulator.engine.skill_engine import SkillEngine

_GUTS_PER_TURN = 2
_MAX_GUTS = 10
_HAND_LIMIT = 5
_ZONES = ("srv", "blk", "rcv", "tos", "atk")


class TurnController:
    def __init__(self, resolver: ActionResolver, skill_engine: SkillEngine) -> None:
        self.resolver = resolver
        self.skill_engine = skill_engine

    def run_draw_phase(self, gs: GameState, player: PlayerState) -> None:
        gs.phase = "draw"
        card = player.draw_card()
        if card is None:
            gs.log(f"{player.name} 牌庫已空，無法抽牌")
        else:
            gs.log(f"{player.name} 抽牌: {card.name}")

    def run_play_phase(
        self,
        gs: GameState,
        player: PlayerState,
        ai_decisions: dict,
    ) -> None:
        gs.phase = "play"

        placements: dict[str, Card] = ai_decisions.get("place", {})
        for zone, card in placements.items():
            if card not in player.hand:
                continue

            if zone in _ZONES:
                if not self._can_place(card, zone, player):
                    gs.log(f"{player.name} 無法出場 {card.name} 至 {zone} (受限)")
                    continue
                # Move existing occupant to discard
                displaced = player.field.get(zone)
                if displaced is not None:
                    player.discard.append(displaced)
                player.field[zone] = card
                player.hand.remove(card)
                gs.log(f"{player.name} 出場 [{zone}] {card.name}")

            elif zone == "evt" and card.category == "EVENT":
                player.field["evt"].append(card)
                player.hand.remove(card)
                gs.log(f"{player.name} 部署事件牌 {card.name}")

            # Trigger [=登場] skill on deploy
            self.skill_engine.apply_skill(
                card, "登場", player, gs.passive(), gs.game_log
            )

        # Activate any additionally requested skills
        for card in ai_decisions.get("skills_to_activate", []):
            self.skill_engine.apply_skill(
                card, "登場", player, gs.passive(), gs.game_log
            )

    def run_action_phase(self, gs: GameState) -> dict:
        gs.phase = "action"
        result = self.resolver.resolve_full_rally(gs)
        return result

    def run_end_phase(self, gs: GameState, player: PlayerState) -> None:
        gs.phase = "end"

        # Reset per-turn bonuses for the active player
        player.reset_turn_bonuses()
        # Clear restrictions that were imposed on the opponent last turn
        gs.passive().reset_restrictions()

        # Replenish guts
        player.guts = min(_MAX_GUTS, player.guts + _GUTS_PER_TURN)
        gs.log(f"{player.name} 回合結束 — Guts: {player.guts}, 得分: {player.score}")

        # Advance turn counter and swap active player
        if gs.current_player == 2:
            gs.turn += 1
        gs.current_player = 2 if gs.current_player == 1 else 1

    def run_full_turn(self, gs: GameState, ai_decisions: dict) -> dict:
        player = gs.active()

        self.run_draw_phase(gs, player)
        if gs.is_terminal():
            return {"terminated_early": True, "reason": "deck_empty_after_draw"}

        self.run_play_phase(gs, player, ai_decisions)

        action_result = self.run_action_phase(gs)

        self.run_end_phase(gs, player)

        return {
            "terminated_early": False,
            "action_result": action_result,
            "p1_score": gs.p1.score,
            "p2_score": gs.p2.score,
            "turn": gs.turn,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _can_place(self, card: Card, zone: str, player: PlayerState) -> bool:
        if zone == "rcv" and player.rcv_lock > 0:
            if card.rcv >= player.rcv_lock:
                return False
        if zone == "blk" and player.blk_lock > 0:
            # Count existing blk cards already on field
            existing_blk = 1 if player.field.get("blk") is not None else 0
            if existing_blk >= player.blk_lock:
                return False
        return True
