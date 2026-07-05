"""
game_engine/effects/handlers/stat.py
Handles all stat-related effects:
  - STAT_BONUS      : add amount to a player's aggregate bonus field
  - STAT_SET        : set a specific zone-card's stat to a fixed value
  - STAT_IMMUNITY   : mark the acting card as immune to stat reduction this turn
"""
from __future__ import annotations

from game_engine.schema import Effect, GameState, PlayerState, Stat, ZoneQualifier


# ── internal helpers ──────────────────────────────────────────────────────────

_STAT_BONUS_FIELD: dict[str, str] = {
    Stat.ATK: "atk_bonus",
    Stat.RCV: "rcv_bonus",
    Stat.BLK: "blk_bonus",
    Stat.TOS: "tos_bonus",
    Stat.SRV: "srv_bonus",
}

_ZONE_CARD_ATTR: dict[str, str] = {
    "攻擊區": "attack_zone",
    ZoneQualifier.ATTACK: "attack_zone",
    "接球區": "receive_zone",
    ZoneQualifier.RECEIVE: "receive_zone",
    "舉球區": "toss_zone",
    ZoneQualifier.TOSS: "toss_zone",
    "攔網區": "block_zones",       # list — handled specially
    ZoneQualifier.BLOCK: "block_zones",
    "發球區": "serve_zone",
    ZoneQualifier.SERVE: "serve_zone",
}


def _zone_for(player: PlayerState, zone_key: str | ZoneQualifier | None):
    """Return the ZoneState (or list of ZoneState for block) for a player zone key."""
    if zone_key is None:
        return None
    attr = _ZONE_CARD_ATTR.get(zone_key)
    if attr is None:
        return None
    return getattr(player, attr)


# ── public handlers ───────────────────────────────────────────────────────────

def apply_stat_bonus(
    effect: Effect,
    state: GameState,
    actor: PlayerState,
    card_no: str | None = None,
) -> None:
    """Add a stat bonus to the player's aggregate bonus field for this turn.

    If effect.zone is set, the bonus is conceptually scoped to cards in that zone,
    but the simplest correct implementation (used here) accumulates into the player-
    level bonus — the engine resolves zone stats at roll time.

    effect.stat  : which stat (ATK / RCV / BLK / TOS / SRV / ANY)
    effect.amount: delta to add (can be negative to represent a reduction by self)
    """
    stat = effect.stat
    amount = effect.amount

    if stat == Stat.ANY:
        # "任意數值 +N" — engine will ask player to choose a stat; here we
        # apply to atk_bonus as the default simulation choice.
        state.log(
            f"{actor.name} 任意數值+{amount}（模擬預設套用攻擊）"
        )
        actor.atk_bonus += amount
        return

    field_name = _STAT_BONUS_FIELD.get(stat)
    if field_name is None:
        state.log(f"[WARN] apply_stat_bonus: 未知 stat={stat}")
        return

    old_val = getattr(actor, field_name)
    setattr(actor, field_name, old_val + amount)
    state.log(
        f"{actor.name} {stat.value.upper()} 加成 +{amount}"
        f"（{field_name}: {old_val} → {old_val + amount}）"
    )


def apply_stat_set(
    effect: Effect,
    state: GameState,
    actor: PlayerState,
    target: PlayerState,
    card_no: str | None = None,
) -> None:
    """Set a zone card's base stat to a fixed value.

    Primarily used for effects like "對手MB攔網設為0".

    effect.stat   : which stat to override
    effect.amount : the fixed value to set
    effect.zone   : which zone the target card is in (on target's field)
    effect.duration: if "next_turn" → set target.next_turn_blk_zero and defer
    """
    stat = effect.stat
    amount = effect.amount
    duration = effect.duration

    # Special-cased deferred effect: opponent BLK→0 on their next turn
    if stat == Stat.BLK and amount == 0 and duration == "next_turn":
        target.next_turn_blk_zero = True
        state.log(
            f"{target.name} 下回合 MB攔網值 設為 0 （標記 next_turn_blk_zero）"
        )
        return

    # Immediate zone-card stat override
    zone_key = effect.zone
    zone_obj = _zone_for(target, zone_key)
    if zone_obj is None:
        state.log(
            f"[WARN] apply_stat_set: 找不到區域 zone={zone_key}，無法執行"
        )
        return

    # block_zones is a list; target the first occupied slot
    if isinstance(zone_obj, list):
        targets = [z for z in zone_obj if z.card is not None]
        if not targets:
            state.log(
                f"[WARN] apply_stat_set: {target.name} {zone_key} 無卡片"
            )
            return
        for z in targets:
            state.log(
                f"{target.name} {zone_key} [{z.card}] {stat.value.upper()} 設為 {amount}"
            )
        # In real engine the card's stat would be overridden in CardRuntime;
        # here we record in the player's bonus such that net = base_stat + bonus
        # We compute: bonus adjustment = amount - (card base stat)
        # Since we don't have base stat here, we store it in a runtime override dict.
        # Use PlayerState.counters keyed by "<card_no>:<stat>" as an override marker.
        for z in targets:
            if z.card:
                override_key = f"stat_override:{z.card}:{stat.value}"
                target.counters[override_key] = amount
        return

    if zone_obj.card is None:
        state.log(
            f"[WARN] apply_stat_set: {target.name} {zone_key} 無卡片"
        )
        return

    override_key = f"stat_override:{zone_obj.card}:{stat.value}"
    target.counters[override_key] = amount
    state.log(
        f"{target.name} {zone_key} [{zone_obj.card}] {stat.value.upper()} 即時設為 {amount}"
    )


def apply_stat_immunity(
    effect: Effect,
    state: GameState,
    actor: PlayerState,
    card_no: str | None = None,
) -> None:
    """Mark a card as immune to stat reduction this turn.

    Stores an immunity flag in PlayerState.counters keyed by card_no so the
    damage-resolution step can check it before applying reductions.

    If card_no is None, immunity applies to all of actor's zone cards this turn.
    """
    if card_no:
        key = f"stat_immune:{card_no}"
        actor.counters[key] = True
        state.log(
            f"{actor.name} 卡片 [{card_no}] 本回合數值免疫（無法被降低）"
        )
    else:
        # Apply to every card currently in any zone
        zone_cards: list[str] = []
        for zone_attr in ("serve_zone", "toss_zone", "attack_zone", "receive_zone"):
            z = getattr(actor, zone_attr)
            if z.card:
                zone_cards.append(z.card)
        for z in actor.block_zones:
            if z.card:
                zone_cards.append(z.card)

        if not zone_cards:
            state.log(f"[WARN] apply_stat_immunity: {actor.name} 場上無卡片可免疫")
            return

        for cn in zone_cards:
            actor.counters[f"stat_immune:{cn}"] = True
        state.log(
            f"{actor.name} 場上所有卡片本回合數值免疫：{zone_cards}"
        )
