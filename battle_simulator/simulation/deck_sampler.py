"""Build sample decks for simulation from card pool."""
import random
from ..engine.card import Card
from ..data_loader import load_all_cards, get_by_school, get_events


def build_school_deck(school: str, seed: int | None = None) -> list[Card]:
    """
    Build a legal 40-card deck for a school.
    Rules: max 4 copies of same card_no, max 8 EVENT cards.
    Strategy: pick top cards by combined stat value, fill remaining with best available.
    """
    rng = random.Random(seed)
    all_cards = load_all_cards()

    # Separate characters and events for this school
    chars = [Card.from_dict(c) for c in all_cards
             if c['category'] == 'CHARACTER' and c['school'] == school]
    events = [Card.from_dict(c) for c in all_cards
              if c['category'] == 'EVENT' and (c['school'] == school or c['school'] in ('烏野', school))]

    # Score each character card by total stats
    def score_card(c: Card) -> float:
        return c.atk * 1.5 + c.blk * 1.2 + c.rcv * 1.0 + c.srv * 1.1 + c.tos * 0.8

    chars.sort(key=score_card, reverse=True)
    events.sort(key=score_card, reverse=True)

    deck: list[Card] = []
    card_counts: dict[str, int] = {}

    # Add up to 4 copies of best characters (up to 32 character slots)
    for card in chars:
        if len(deck) >= 32:
            break
        copies = min(4, 4 - card_counts.get(card.card_no, 0))
        for _ in range(copies):
            if len(deck) < 32:
                deck.append(card)
                card_counts[card.card_no] = card_counts.get(card.card_no, 0) + 1

    # Add up to 8 event cards
    evt_count = 0
    for card in events:
        if evt_count >= 8 or len(deck) >= 40:
            break
        copies = min(4 - card_counts.get(card.card_no, 0), 8 - evt_count, 40 - len(deck))
        for _ in range(copies):
            deck.append(card)
            card_counts[card.card_no] = card_counts.get(card.card_no, 0) + 1
            evt_count += 1

    # Fill remaining with best chars if needed
    for card in chars:
        if len(deck) >= 40:
            break
        count = card_counts.get(card.card_no, 0)
        if count < 4:
            deck.append(card)
            card_counts[card.card_no] = count + 1

    rng.shuffle(deck)
    return deck[:40]


def build_custom_deck(card_list: list[dict], seed: int | None = None) -> list[Card]:
    """Build deck from explicit list of {card_no, count} dicts."""
    rng = random.Random(seed)
    all_cards = {c['card_no']: c for c in load_all_cards()}
    deck = []
    for entry in card_list:
        card_no = entry['card_no']
        count = entry.get('count', 1)
        if card_no in all_cards:
            card = Card.from_dict(all_cards[card_no])
            deck.extend([card] * min(count, 4))
    rng.shuffle(deck)
    return deck[:40]
