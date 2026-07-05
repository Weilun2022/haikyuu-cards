"""game_engine/engine/combat.py — 攻防值計算與得分結算"""
from __future__ import annotations
from game_engine.schema import GameState, PlayerState
from game_engine.card_db import get_stat


def calc_attack_score(actor: PlayerState) -> int:
    """TOS + ATK + 加成 (含 stat_override 覆蓋)。"""
    tos_c = actor.toss_zone.card
    atk_c = actor.attack_zone.card

    tos_base = _effective_stat(actor, tos_c, "tos") if tos_c else 0
    atk_base = _effective_stat(actor, atk_c, "atk") if atk_c else 0

    total = tos_base + atk_base + actor.tos_bonus + actor.atk_bonus
    return max(0, total)


def calc_defense_score(defender: PlayerState) -> int:
    """RCV + BLK(全格合計) + 加成。next_turn_blk_zero → 攔網貢獻歸零。"""
    rcv_c = defender.receive_zone.card
    rcv_base = _effective_stat(defender, rcv_c, "rcv") if rcv_c else 0

    if defender.next_turn_blk_zero:
        blk_total = 0
    else:
        blk_total = 0
        for bz in defender.block_zones:
            if bz.card:
                blk_total += _effective_stat(defender, bz.card, "blk")

    total = rcv_base + blk_total + defender.rcv_bonus + defender.blk_bonus
    return max(0, total)


def calc_serve_score(actor: PlayerState) -> int:
    srv_c = actor.serve_zone.card
    srv_base = _effective_stat(actor, srv_c, "srv") if srv_c else 0
    return max(0, srv_base + actor.srv_bonus)


def calc_block_score(defender: PlayerState) -> int:
    """攔網判定 DP：Σ BLK（全格）+ 加成。next_turn_blk_zero → 全部歸零。"""
    if defender.next_turn_blk_zero:
        return max(0, defender.blk_bonus)
    total = 0
    for bz in defender.block_zones:
        if bz.card:
            total += _effective_stat(defender, bz.card, "blk")
    return max(0, total + defender.blk_bonus)


def calc_receive_score(defender: PlayerState) -> int:
    """接球階段：只計 RCV（無攔網）。"""
    rcv_c = defender.receive_zone.card
    rcv_base = _effective_stat(defender, rcv_c, "rcv") if rcv_c else 0
    return max(0, rcv_base + defender.rcv_bonus)


def resolve_rally(state: GameState) -> dict:
    """
    結算一次 rally（一個攻防交換）。
    回傳:
      {"winner": 1|2|0,    # 0 = 平局
       "p1_atk": int, "p1_def": int,
       "p2_atk": int, "p2_def": int,
       "action": str}      # "attack" 或 "serve"
    """
    actor = state.active()
    passive = state.passive()
    actor_num = state.current_player
    passive_num = 2 if actor_num == 1 else 1

    # 決定行動類型：有發球角色且攻擊角色空 → 發球階段
    has_serve = actor.serve_zone.card is not None
    has_attack = actor.attack_zone.card is not None

    if has_serve and not has_attack:
        action = "serve"
        atk_score = calc_serve_score(actor)
        def_score = calc_receive_score(passive)
    else:
        action = "attack"
        atk_score = calc_attack_score(actor)
        def_score = calc_defense_score(passive)

    if atk_score > def_score:
        winner = actor_num
    elif def_score > atk_score:
        winner = passive_num
    else:
        winner = 0  # 平局（重新發球，不計分）

    return {
        "winner": winner,
        "action": action,
        "actor_atk": atk_score,
        "passive_def": def_score,
        "p1_atk": atk_score if actor_num == 1 else def_score,
        "p1_def": def_score if actor_num == 1 else atk_score,
        "p2_atk": atk_score if actor_num == 2 else def_score,
        "p2_def": def_score if actor_num == 2 else atk_score,
    }


def check_volleyball_threshold(action_type: str, threshold: int,
                                actor: PlayerState) -> bool:
    """
    判斷特殊排球動作是否成功觸發。
    [封殺攔網(N)]: 自己攔網值 >= N → 成功
    [一觸(N)]: 自己接球值 >= N → 成功
    [後排攻擊(N)]: 自己攻擊值 >= N → 成功
    [佯攻(N)]: 自己發球值 >= N → 成功（簡化）
    """
    if action_type in ("封殺攔網", "spike"):
        blk = sum(
            _effective_stat(actor, bz.card, "blk")
            for bz in actor.block_zones if bz.card
        ) + actor.blk_bonus
        return blk >= threshold
    if action_type in ("一觸", "dig"):
        rcv_c = actor.receive_zone.card
        rcv = (_effective_stat(actor, rcv_c, "rcv") if rcv_c else 0) + actor.rcv_bonus
        return rcv >= threshold
    if action_type in ("後排攻擊", "back_attack"):
        atk_c = actor.attack_zone.card
        atk = (_effective_stat(actor, atk_c, "atk") if atk_c else 0) + actor.atk_bonus
        return atk >= threshold
    if action_type in ("佯攻", "feint"):
        srv_c = actor.serve_zone.card
        srv = (_effective_stat(actor, srv_c, "srv") if srv_c else 0) + actor.srv_bonus
        return srv >= threshold
    return False


def apply_next_turn_cleanup(player: PlayerState) -> None:
    """回合開始時：套用跨回合效果 → 清除旗標。"""
    # next_turn_blk_zero 已在 calc_defense_score 中使用，這裡清除
    player.next_turn_blk_zero = False
    player.next_turn_skill_nullify.clear()
    player.next_turn_zone_lock.clear()
    # 清除本回合 stat overrides（這一回合已結算）
    keys_to_delete = [k for k in player.counters if k.startswith("stat_override:")]
    for k in keys_to_delete:
        del player.counters[k]
    # 清除本回合 stat_immune
    keys_to_delete = [k for k in player.counters if k.startswith("stat_immune:")]
    for k in keys_to_delete:
        del player.counters[k]
    # 清除 Guts 消費記錄
    player.counters.pop("guts_spent_this_turn", None)


# ── 私有 helper ───────────────────────────────────────────────────────────────

def _effective_stat(player: PlayerState, card_no: str, stat: str) -> int:
    """取角色數值，若有 stat_override 則以覆蓋值計算。"""
    override_key = f"stat_override:{card_no}:{stat}"
    if override_key in player.counters:
        return max(0, int(player.counters[override_key]))
    base = get_stat(card_no, stat)
    # 卡片本身的暫時加值（CardInstance.stat_modifiers）
    # 這裡簡化：從 counters 查 card-level modifier
    mod_key = f"card_mod:{card_no}:{stat}"
    mod = player.counters.get(mod_key, 0)
    return max(0, base + mod)
