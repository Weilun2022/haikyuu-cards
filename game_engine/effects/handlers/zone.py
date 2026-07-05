"""game_engine/effects/handlers/zone.py — 區域移動/出場效果 handler"""
from __future__ import annotations
import random
from game_engine.schema import Effect, GameState, PlayerState, ZoneState
from game_engine.card_db import get_card, get_name, is_event, is_character


def _matches_filter(card_no: str, cf) -> bool:
    if cf is None:
        return True
    card = get_card(card_no) or {}
    if cf.school and card.get("school") != cf.school:
        return False
    if cf.name and card.get("name") != cf.name:
        return False
    if cf.category and card.get("category") != cf.category:
        return False
    if cf.position:
        from game_engine.card_db import get_position
        pos = get_position(card_no)
        if pos not in cf.position:
            return False
    if cf.rarity and card.get("rarity") != cf.rarity:
        return False
    return True


def _place_to_zone(actor: PlayerState, card_no: str, zone_name: str) -> None:
    zn = zone_name.lower()
    if zn == "toss":
        actor.toss_zone = ZoneState(card=card_no)
    elif zn == "attack":
        actor.attack_zone = ZoneState(card=card_no)
    elif zn == "receive":
        actor.receive_zone = ZoneState(card=card_no)
    elif zn == "serve":
        actor.serve_zone = ZoneState(card=card_no)
    elif zn == "block":
        for i, bz in enumerate(actor.block_zones):
            if bz.card is None:
                actor.block_zones[i] = ZoneState(card=card_no)
                return
        actor.block_zones[0] = ZoneState(card=card_no)


def _zone_card(actor: PlayerState, zone_name: str) -> str | None:
    zn = (zone_name or "").lower()
    mapping = {"toss": actor.toss_zone, "attack": actor.attack_zone,
               "receive": actor.receive_zone, "serve": actor.serve_zone}
    if zn in mapping:
        return mapping[zn].card
    if zn == "block":
        for bz in actor.block_zones:
            if bz.card:
                return bz.card
    return None


def apply_deploy_from_grave(effect: Effect, state: GameState, actor: PlayerState,
                            ai=None) -> None:
    cf = effect.card_filter
    zone = str(effect.to_zone or effect.zone or "attack")
    candidates = [c for c in actor.grave if _matches_filter(c, cf) and is_character(c)]
    if not candidates:
        state.log("deploy_from_grave: 棄牌無符合卡")
        return
    chosen = (ai.decide_recover_target(candidates, state, actor)
              if ai else candidates[0])
    if chosen and chosen in actor.grave:
        actor.grave.remove(chosen)
        char_id = get_name(chosen) or chosen
        cnt = actor._grave_char_counter.get(char_id, 0)
        if cnt > 0:
            actor._grave_char_counter[char_id] = cnt - 1
            if cnt - 1 == 0:
                actor._grave_unique_count -= 1
        _place_to_zone(actor, chosen, zone)
        state.log(f"deploy_from_grave: {get_name(chosen)} → {zone}")


def apply_deploy_from_guts(effect: Effect, state: GameState, actor: PlayerState,
                           ai=None) -> None:
    zone = str(effect.to_zone or effect.zone or "attack")
    cf = effect.card_filter
    # Guts 池：從 counters 找記錄的 guts card list
    guts_cards = actor.counters.get(f"guts_{zone}_cards", [])
    candidates = [c for c in guts_cards if _matches_filter(c, cf)]
    if not candidates:
        state.log("deploy_from_guts: Guts 無符合卡")
        return
    chosen = candidates[0]
    guts_cards.remove(chosen)
    attr = f"g_{zone}"
    if hasattr(actor, attr):
        setattr(actor, attr, max(0, getattr(actor, attr) - 1))
    _place_to_zone(actor, chosen, zone)
    state.log(f"deploy_from_guts: {get_name(chosen)} → {zone}")


def apply_return_to_hand(effect: Effect, state: GameState, actor: PlayerState,
                         card_no: str = "") -> None:
    zone = str(effect.from_zone or effect.zone or "")
    target = _zone_card(actor, zone) if zone else card_no
    if not target:
        state.log("return_to_hand: 無目標卡")
        return
    # 移出場地
    _clear_zone_card(actor, zone or _find_zone(actor, target))
    actor.hand.append(target)
    state.log(f"return_to_hand: {get_name(target)} 回手牌")


def apply_return_to_pile(effect: Effect, state: GameState, actor: PlayerState,
                         card_no: str = "") -> None:
    position = effect.pile_position or "top"
    zone = str(effect.from_zone or "")
    target = _zone_card(actor, zone) if zone else card_no
    if not target:
        state.log("return_to_pile: 無目標卡")
        return
    _clear_zone_card(actor, zone or _find_zone(actor, target))
    if position == "top":
        actor.pile.append(target)
    else:
        actor.pile.insert(0, target)
    state.log(f"return_to_pile: {get_name(target)} → 牌庫{position}")


def apply_move_to_zone(effect: Effect, state: GameState, actor: PlayerState,
                       card_no: str = "") -> None:
    from_z = str(effect.from_zone or "")
    to_z = str(effect.to_zone or effect.zone or "")
    target = _zone_card(actor, from_z) if from_z else card_no
    if not target or not to_z:
        return
    _clear_zone_card(actor, from_z or _find_zone(actor, target))
    _place_to_zone(actor, target, to_z)
    state.log(f"move_to_zone: {get_name(target)} {from_z}→{to_z}")


def apply_swap_zone(effect: Effect, state: GameState, actor: PlayerState) -> None:
    z1 = str(effect.from_zone or "")
    z2 = str(effect.to_zone or "")
    c1 = _zone_card(actor, z1)
    c2 = _zone_card(actor, z2)
    if not c1 or not c2:
        state.log(f"swap_zone: {z1}/{z2} 其中一個無卡")
        return
    _clear_zone_card(actor, z1)
    _clear_zone_card(actor, z2)
    _place_to_zone(actor, c1, z2)
    _place_to_zone(actor, c2, z1)
    state.log(f"swap_zone: {get_name(c1)} ⇄ {get_name(c2)}")


def apply_pile_peek(effect: Effect, state: GameState, actor: PlayerState) -> None:
    n = effect.amount or 1
    revealed = list(reversed(actor.pile[-n:]))
    state.log(f"pile_peek: 公開牌庫頂 {n} 張: {[get_name(c) for c in revealed]}")


def apply_pile_peek_and_keep(effect: Effect, state: GameState, actor: PlayerState,
                              ai=None) -> None:
    n = effect.amount or 1
    revealed = list(reversed(actor.pile[-n:]))
    state.log(f"pile_peek_and_keep: 公開 {[get_name(c) for c in revealed]}")
    cf = effect.card_filter
    candidates = [c for c in revealed if _matches_filter(c, cf)]
    if candidates:
        chosen = candidates[0]
        actor.pile.remove(chosen)
        actor.hand.append(chosen)
        # 其餘放牌庫底
        for c in revealed:
            if c != chosen and c in actor.pile:
                actor.pile.remove(c)
                actor.pile.insert(0, c)
        state.log(f"pile_peek_and_keep: 取 {get_name(chosen)} 加手牌")


def apply_shuffle_pile(effect: Effect, state: GameState, actor: PlayerState) -> None:
    random.shuffle(actor.pile)
    state.log("shuffle_pile: 牌庫洗牌")


def apply_event_zone_place(effect: Effect, state: GameState, actor: PlayerState,
                            card_no: str = "") -> None:
    if not card_no and not effect.card_filter:
        return
    cf = effect.card_filter
    target = card_no
    if not target:
        candidates = [c for c in actor.hand if is_event(c) and _matches_filter(c, cf)]
        target = candidates[0] if candidates else None
    if target and target in actor.hand:
        actor.hand.remove(target)
        actor.event_zone.append(target)
        state.log(f"event_zone_place: {get_name(target)} → Event區")


def apply_move_guts_to_zone(effect: Effect, state: GameState, actor: PlayerState) -> None:
    zone = str(effect.to_zone or effect.zone or "attack")
    cf = effect.card_filter
    guts_key = f"guts_{zone}_cards"
    cards = actor.counters.get(guts_key, [])
    candidates = [c for c in cards if _matches_filter(c, cf)]
    if not candidates:
        return
    chosen = candidates[0]
    cards.remove(chosen)
    _place_to_zone(actor, chosen, zone)
    state.log(f"move_guts_to_zone: {get_name(chosen)} Guts→{zone}")


def apply_tap_deploy(effect: Effect, state: GameState, actor: PlayerState,
                     card_no: str = "") -> None:
    zone = str(effect.zone or "attack")
    if card_no:
        _place_to_zone(actor, card_no, zone)
        zobj = getattr(actor, f"{zone}_zone", None)
        if zobj:
            zobj.tapped = True
    state.log(f"tap_deploy: {get_name(card_no)} 横置出場→{zone}")


# ── helpers ──────────────────────────────────────────────────────────────────

def _find_zone(actor: PlayerState, card_no: str) -> str:
    for attr in ("toss_zone", "attack_zone", "receive_zone", "serve_zone"):
        z = getattr(actor, attr)
        if z.card == card_no:
            return attr.replace("_zone", "")
    for i, bz in enumerate(actor.block_zones):
        if bz.card == card_no:
            return "block"
    return ""


def _clear_zone_card(actor: PlayerState, zone_name: str) -> None:
    zn = (zone_name or "").lower()
    if zn in ("toss", "attack", "receive", "serve"):
        setattr(actor, f"{zn}_zone", ZoneState())
    elif zn == "block":
        for i, bz in enumerate(actor.block_zones):
            if bz.card:
                actor.block_zones[i] = ZoneState()
                return
