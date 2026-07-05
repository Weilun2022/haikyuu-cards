"""game_engine/engine/conditions.py — 所有 ConditionType 評估器"""
from __future__ import annotations
from game_engine.schema import Condition, ConditionType, GameState, PlayerState, ZoneQualifier
from game_engine.card_db import get_card, get_name, get_school, get_position, is_event


def evaluate_condition(
    cond: Condition,
    state: GameState,
    actor: PlayerState,
    card_no: str = "",
    deploy_zone: str | None = None,
    deploy_via_skill: bool = False,
) -> bool:
    t = cond.type
    p = cond.param

    match t:
        case ConditionType.ALWAYS:
            return True

        # ── 棄牌區 ─────────────────────────────────────────────
        case ConditionType.SIX_UNIQUE:
            return actor.unique_names_in_grave() >= 6

        case ConditionType.GRAVE_UNIQUE_GE:
            return actor.unique_names_in_grave() >= int(p or 0)

        case ConditionType.CARD_IN_GRAVE:
            # param: 角色名稱
            for cno in actor.grave:
                if get_name(cno) == p:
                    return True
            return False

        # ── 手牌 ───────────────────────────────────────────────
        case ConditionType.HAND_LE:
            return len(actor.hand) <= int(p or 0)

        case ConditionType.HAND_GE:
            return len(actor.hand) >= int(p or 0)

        case ConditionType.HAND_HAS:
            return any(get_name(c) == p for c in actor.hand)

        # ── 自己場地 ───────────────────────────────────────────
        case ConditionType.ALL_SAME_SCHOOL:
            deployed = _all_deployed(actor)
            if not deployed:
                return False
            schools = {get_school(c) for c in deployed}
            if p:  # 指定學校
                return schools == {p}
            return len(schools) == 1

        case ConditionType.MULTI_SCHOOL_GE:
            deployed = _all_deployed(actor)
            schools = {get_school(c) for c in deployed if get_school(c)}
            return len(schools) >= int(p or 2)

        case ConditionType.ZONE_OCCUPIED:
            zone = _zone_card(actor, str(p))
            return zone is not None

        case ConditionType.ZONE_EMPTY:
            zone = _zone_card(actor, str(p))
            return zone is None

        case ConditionType.SETTER_IS:
            # toss_zone 角色名稱 == p
            c = actor.toss_zone.card
            return c is not None and get_name(c) == str(p)

        case ConditionType.ATTACKER_IS:
            c = actor.attack_zone.card
            return c is not None and get_name(c) == str(p)

        case ConditionType.LIBERO_IN_RECEIVE:
            c = actor.receive_zone.card
            return c is not None and get_position(c) == "L"

        case ConditionType.SELF_IS_RECEIVER:
            return actor.receive_zone.card == card_no

        # ── 出場方式 ───────────────────────────────────────────
        case ConditionType.SKILL_DEPLOY:
            return deploy_via_skill

        case ConditionType.NAMED_SKILL_DEPLOY:
            # param: 觸發技能的卡名（由外部標記傳入）
            return deploy_via_skill  # 簡化：只檢查是否技能出場

        case ConditionType.DEPLOY_AS_POSITION:
            return deploy_zone == str(p) if p else False

        case ConditionType.FROM_HAND:
            return not deploy_via_skill

        # ── 對手條件 ───────────────────────────────────────────
        case ConditionType.OPP_ATK_GE:
            opp = state.passive()
            c = opp.attack_zone.card
            if c is None:
                return False
            from game_engine.card_db import get_stat
            base = get_stat(c, "atk")
            total = base + opp.atk_bonus
            return total >= int(p or 0)

        case ConditionType.OPP_SRV_LE:
            opp = state.passive()
            c = opp.serve_zone.card
            if c is None:
                return True  # 無發球角色視為 SRV=0
            from game_engine.card_db import get_stat
            base = get_stat(c, "srv")
            return base + opp.srv_bonus <= int(p or 999)

        case ConditionType.OPP_EVENT_ZONE_LE:
            return len(state.passive().event_zone) <= int(p or 0)

        case ConditionType.OPP_HAS_CARD:
            opp = state.passive()
            for c in _all_deployed(opp):
                if get_name(c) == str(p):
                    return True
            return False

        # ── Guts 條件 ──────────────────────────────────────────
        case ConditionType.GUTS_ALL_RARITY:
            # 檢查本回合消費的 Guts 是否全為指定稀有度
            spent = actor.counters.get("guts_spent_this_turn", [])
            if not spent:
                return False
            target_rarity = str(p)
            return all(
                (get_card(c) or {}).get("rarity") == target_rarity
                for c in spent
            )

        case ConditionType.GUTS_HAS_NAMED:
            # Guts 區有特定名稱角色（只看 g_* 計數，簡化）
            return actor.counters.get(f"guts_named_{p}", 0) > 0

        # ── 特殊 ───────────────────────────────────────────────
        case ConditionType.IS_YOSU:
            card = get_card(card_no) or {}
            return "ユース" in (card.get("skill_jp") or "")

        case ConditionType.PILE_TOP_MATCHES:
            if not actor.pile:
                return False
            top = actor.pile[-1]
            card = get_card(top) or {}
            if isinstance(p, dict):
                if "school" in p and card.get("school") != p["school"]:
                    return False
                if "name" in p and card.get("name") != p["name"]:
                    return False
            return True

        case ConditionType.COUNTER_GE:
            key, n = (str(p).split(":", 1) if isinstance(p, str) and ":" in str(p)
                      else (str(p), 1))
            return actor.counters.get(key, 0) >= int(n)

        case ConditionType.AFTER_DISCARD:
            return True  # 由 cost handler 設置，此處視為已滿足

        case _:
            return True  # 未知條件預設不阻擋


def evaluate_all_conditions(
    conditions: list[Condition],
    state: GameState,
    actor: PlayerState,
    card_no: str = "",
    deploy_zone: str | None = None,
    deploy_via_skill: bool = False,
) -> bool:
    return all(
        evaluate_condition(c, state, actor, card_no, deploy_zone, deploy_via_skill)
        for c in conditions
    )


# ── helpers ──────────────────────────────────────────────────────────────────

def _all_deployed(actor: PlayerState) -> list[str]:
    result = []
    for attr in ("serve_zone", "toss_zone", "attack_zone", "receive_zone"):
        z = getattr(actor, attr)
        if z.card:
            result.append(z.card)
    for bz in actor.block_zones:
        if bz.card:
            result.append(bz.card)
    return result


def _zone_card(actor: PlayerState, zone_name: str) -> str | None:
    mapping = {
        "攻擊區": actor.attack_zone,
        "接球區": actor.receive_zone,
        "舉球區": actor.toss_zone,
        "發球區": actor.serve_zone,
        "攔網區": None,  # 特殊：取第一個佔用 slot
    }
    if zone_name in mapping:
        z = mapping[zone_name]
        if z is None:
            for bz in actor.block_zones:
                if bz.card:
                    return bz.card
            return None
        return z.card
    return None
