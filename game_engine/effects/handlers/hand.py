"""
game_engine/effects/handlers/hand.py
Handles all hand / draw / recover effects:
  - DRAW                   : draw N cards from pile to hand
  - DISCARD_FROM_HAND      : smart discard (AI callback chooses which card)
  - RECOVER_CHAR           : recover CHARACTER card from grave to hand (with CardFilter)
  - RECOVER_EVENT          : recover EVENT card from grave to hand (with CardFilter)
  - RECOVER_FROM_EVENT_ZONE: move card from actor's Event zone to hand
  - ADD_TO_HAND_FROM_PILE  : search pile for card matching filter, add to hand, shuffle pile
"""
from __future__ import annotations

import random
from typing import Callable

from game_engine.schema import CardFilter, Effect, GameState, PlayerState
from game_engine.card_db import get_card   # type: ignore[import]  # provided at runtime


# ── private helpers ───────────────────────────────────────────────────────────

def _matches_filter(card_no: str, cf: CardFilter) -> bool:
    """Return True if the card identified by *card_no* satisfies all non-None
    fields in *cf* (CardFilter).  Unknown card_no → False."""
    try:
        card = get_card(card_no)
    except Exception:
        return False

    if cf.school is not None and card.get("school") != cf.school:
        return False
    if cf.position is not None:
        pos = card.get("position")
        if pos not in cf.position:
            return False
    if cf.category is not None:
        cat = card.get("category")
        if cat != cf.category:
            return False
    if cf.name is not None and card.get("name") != cf.name:
        return False
    if cf.rarity is not None and card.get("rarity") != cf.rarity:
        return False
    return True


def _card_name(card_no: str) -> str:
    """Return card name or fall back to card_no."""
    try:
        return get_card(card_no).get("name", card_no)
    except Exception:
        return card_no


# ── public handlers ───────────────────────────────────────────────────────────

def apply_draw(
    effect: Effect,
    state: GameState,
    actor: PlayerState,
) -> None:
    """Draw effect.amount cards from actor's pile to hand.

    If the pile has fewer cards than requested, draw only what's available
    and log a warning (the engine can trigger a game-over condition separately).
    """
    n = effect.amount
    available = len(actor.pile)
    draw_count = min(n, available)

    if draw_count == 0:
        state.log(f"[WARN] {actor.name} 牌庫為空，無法抽牌")
        return

    if draw_count < n:
        state.log(
            f"[WARN] {actor.name} 牌庫剩 {available} 張，"
            f"只能抽 {draw_count}（要求 {n}）"
        )

    drawn = actor.pile[:draw_count]
    actor.pile = actor.pile[draw_count:]
    actor.hand.extend(drawn)

    names = [_card_name(c) for c in drawn]
    state.log(f"{actor.name} 抽牌 {draw_count} 張：{names}")


def apply_discard_from_hand(
    effect: Effect,
    state: GameState,
    actor: PlayerState,
    ai_discard_fn: Callable[[list[str], GameState], str],
) -> None:
    """Discard effect.amount cards from actor's hand chosen by the AI callback.

    ai_discard_fn(hand, state) -> card_no_to_discard  (called once per card).
    If hand is empty before all discards are done, stop early.
    """
    n = effect.amount
    for i in range(n):
        if not actor.hand:
            state.log(f"[WARN] {actor.name} 手牌已空，停止棄牌（已棄 {i} 張）")
            return
        chosen = ai_discard_fn(actor.hand, state)
        if chosen not in actor.hand:
            # Fallback: discard last card in hand
            chosen = actor.hand[-1]
            state.log(
                f"[WARN] {actor.name} AI 選擇的棄牌 [{chosen}] 不在手牌中，"
                f"改棄最後一張"
            )
        actor.hand.remove(chosen)
        actor.add_to_grave(chosen, _card_name(chosen))
        state.log(f"{actor.name} 棄牌：[{chosen}] {_card_name(chosen)}")


def apply_recover_char(
    effect: Effect,
    state: GameState,
    actor: PlayerState,
) -> None:
    """Recover a CHARACTER card from grave to hand matching effect.card_filter.

    Picks the first matching card found in grave (order = insertion order).
    Respects card_filter.max_count (default 1).
    """
    cf = effect.card_filter
    # Force category to CHARACTER regardless of what filter says
    category_override = CardFilter(
        school=cf.school,
        position=cf.position,
        category="CHARACTER",
        name=cf.name,
        rarity=cf.rarity,
        max_count=cf.max_count,
    )

    candidates = [c for c in actor.grave if _matches_filter(c, category_override)]
    if not candidates:
        state.log(
            f"[WARN] {actor.name} 棄牌區無符合條件的角色牌"
            f"（filter={category_override}）"
        )
        return

    to_recover = candidates[: category_override.max_count]
    for card_no in to_recover:
        actor.grave.remove(card_no)
        actor.hand.append(card_no)
        state.log(
            f"{actor.name} 從棄牌區回收角色牌 [{card_no}] {_card_name(card_no)} 至手牌"
        )


def apply_recover_event(
    effect: Effect,
    state: GameState,
    actor: PlayerState,
) -> None:
    """Recover an EVENT card from grave to hand matching effect.card_filter."""
    cf = effect.card_filter
    category_override = CardFilter(
        school=cf.school,
        position=cf.position,
        category="EVENT",
        name=cf.name,
        rarity=cf.rarity,
        max_count=cf.max_count,
    )

    candidates = [c for c in actor.grave if _matches_filter(c, category_override)]
    if not candidates:
        state.log(
            f"[WARN] {actor.name} 棄牌區無符合條件的Event牌"
            f"（filter={category_override}）"
        )
        return

    to_recover = candidates[: category_override.max_count]
    for card_no in to_recover:
        actor.grave.remove(card_no)
        actor.hand.append(card_no)
        state.log(
            f"{actor.name} 從棄牌區回收Event牌 [{card_no}] {_card_name(card_no)} 至手牌"
        )


def apply_recover_from_event_zone(
    effect: Effect,
    state: GameState,
    actor: PlayerState,
    card_no: str | None = None,
) -> None:
    """Move a card from actor's Event zone to hand.

    If card_no is specified, move that specific card.
    Otherwise move the first card in event_zone (or first matching filter).
    """
    cf = effect.card_filter

    if card_no is not None:
        if card_no not in actor.event_zone:
            state.log(
                f"[WARN] {actor.name} Event區無 [{card_no}]，無法回收至手牌"
            )
            return
        actor.event_zone.remove(card_no)
        actor.hand.append(card_no)
        state.log(
            f"{actor.name} Event區 [{card_no}] {_card_name(card_no)} → 手牌"
        )
        return

    # No specific card_no — pick first matching card
    candidates = [c for c in actor.event_zone if _matches_filter(c, cf)]
    if not candidates:
        # If filter is empty (all-None), take first card in zone
        if actor.event_zone:
            candidates = [actor.event_zone[0]]
        else:
            state.log(f"[WARN] {actor.name} Event區為空，無法回收")
            return

    to_move = candidates[: max(cf.max_count, 1)]
    for cn in to_move:
        actor.event_zone.remove(cn)
        actor.hand.append(cn)
        state.log(
            f"{actor.name} Event區 [{cn}] {_card_name(cn)} → 手牌"
        )


def apply_add_to_hand_from_pile(
    effect: Effect,
    state: GameState,
    actor: PlayerState,
) -> None:
    """Search actor's pile for a card matching effect.card_filter, add to hand,
    then shuffle the remaining pile.

    Respects card_filter.max_count.
    """
    cf = effect.card_filter
    candidates = [c for c in actor.pile if _matches_filter(c, cf)]

    if not candidates:
        state.log(
            f"[WARN] {actor.name} 牌庫中無符合條件的牌（filter={cf}），洗牌"
        )
        random.shuffle(actor.pile)
        return

    to_take = candidates[: max(cf.max_count, 1)]
    for card_no in to_take:
        actor.pile.remove(card_no)
        actor.hand.append(card_no)
        state.log(
            f"{actor.name} 從牌庫搜尋 [{card_no}] {_card_name(card_no)} 加入手牌"
        )

    random.shuffle(actor.pile)
    state.log(f"{actor.name} 牌庫洗牌完畢（剩餘 {len(actor.pile)} 張）")
