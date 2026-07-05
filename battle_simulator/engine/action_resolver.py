from __future__ import annotations

from battle_simulator.engine.game_state import GameState
from battle_simulator.engine.skill_engine import SkillEngine


class ActionResolver:
    def __init__(self, skill_engine: SkillEngine) -> None:
        self.skill_engine = skill_engine

    # ------------------------------------------------------------------
    # Individual resolution steps
    # ------------------------------------------------------------------

    def resolve_serve(self, gs: GameState) -> dict:
        active = gs.active()
        passive = gs.passive()
        srv = active.effective_stat("srv")
        rcv = passive.effective_stat("rcv")
        scored = srv > rcv
        if scored:
            active.score += 1
            gs.game_log.append(f"發球得分! SRV {srv} > RCV {rcv}")
        else:
            gs.game_log.append(f"發球未得分 SRV {srv} vs RCV {rcv}")
        return {
            "scored": scored,
            "srv_total": srv,
            "rcv_total": rcv,
            "proceed_to_toss": not scored,
        }

    def resolve_toss(self, gs: GameState) -> dict:
        active = gs.active()
        tos = active.effective_stat("tos")
        bonus = 1 if tos >= 3 else 0
        if bonus:
            gs.game_log.append(f"精準舉球! TOS {tos} >= 3 → ATK +1")
        return {"tos_bonus": bonus}

    def resolve_attack(self, gs: GameState, tos_bonus: int = 0) -> dict:
        active = gs.active()
        passive = gs.passive()
        atk = active.effective_stat("atk") + tos_bonus
        blk = passive.effective_stat("blk")
        killshot = atk >= blk + 3
        scored = atk > blk

        if killshot:
            active.score += 2
            gs.game_log.append(f"封殺! ATK {atk} vs BLK {blk} (+2pts)")
        elif scored:
            active.score += 1
            gs.game_log.append(f"得分! ATK {atk} > BLK {blk}")
        else:
            gs.game_log.append(f"攔截! ATK {atk} <= BLK {blk}")

        return {
            "scored": scored,
            "killshot": killshot,
            "atk_total": atk,
            "blk_total": blk,
        }

    # ------------------------------------------------------------------
    # Zone skill triggers (called before the stat comparison)
    # ------------------------------------------------------------------

    def _trigger_zone_skills(self, gs: GameState, zone_tag: str) -> None:
        active = gs.active()
        passive = gs.passive()
        for zone, card in active.field.items():
            if zone == "evt":
                for evt_card in card:
                    self.skill_engine.apply_skill(
                        evt_card, zone_tag, active, passive, gs.game_log
                    )
            elif card is not None:
                self.skill_engine.apply_skill(
                    card, zone_tag, active, passive, gs.game_log
                )

    # ------------------------------------------------------------------
    # Full rally
    # ------------------------------------------------------------------

    def resolve_full_rally(self, gs: GameState) -> dict:
        result: dict = {}

        # Trigger zone skills before each resolution step
        self._trigger_zone_skills(gs, "發球區")
        serve_result = self.resolve_serve(gs)
        result.update(serve_result)

        if serve_result["proceed_to_toss"]:
            self._trigger_zone_skills(gs, "舉球區")
            toss_result = self.resolve_toss(gs)
            result.update(toss_result)

            self._trigger_zone_skills(gs, "攻擊區")
            # Also allow opponent blk zone skills
            # (swap active/passive view for passive triggers)
            _saved_cp = gs.current_player
            gs.current_player = 2 if _saved_cp == 1 else 1
            self._trigger_zone_skills(gs, "攔網區")
            gs.current_player = _saved_cp

            atk_result = self.resolve_attack(gs, tos_bonus=toss_result["tos_bonus"])
            result.update(atk_result)
        else:
            result.setdefault("tos_bonus", 0)
            result.setdefault("scored_attack", False)
            result.setdefault("killshot", False)
            result.setdefault("atk_total", 0)
            result.setdefault("blk_total", 0)

        return result
