"""Build sample decks for simulation from card pool."""
import random
from ..engine.card import Card
from ..data_loader import load_all_cards
from ..analysis.synergy_analyzer import SynergyAnalyzer

_analyzer = SynergyAnalyzer()

# ── Scoring ───────────────────────────────────────────────────────────────────

# Stat weights: ATK最重要，依序遞減
_STAT_W = {'atk': 1.5, 'blk': 1.2, 'rcv': 1.0, 'srv': 1.1, 'tos': 0.8}

def _stat_score(c: Card) -> float:
    return sum(getattr(c, stat, 0) * w for stat, w in _STAT_W.items())


def _combined_score(c: Card, current_deck: list[Card], synergy_weight: float = 1.0) -> float:
    """
    選牌公式 = 數值評分 + 連動加成

    數值評分: ATK×1.5 + BLK×1.2 + RCV×1.0 + SRV×1.1 + TOS×0.8
    連動加成: SynergyAnalyzer.score_card_in_context() × synergy_weight
              — 指名連動(×1.5~3.0) / 棄牌循環(×3.0) / Guts召喚(×2.5) /
                事件觸發(×1.0~2.0) / 條件解鎖(×2.0×覆蓋率)
    """
    stat = _stat_score(c)
    syn  = _analyzer.score_card_in_context(c, current_deck) if current_deck else 0.0
    return stat + syn * synergy_weight


# ── Public API ────────────────────────────────────────────────────────────────

def build_school_deck(
    school: str,
    seed: int | None = None,
    synergy_weight: float = 1.0,
) -> list[Card]:
    """
    Build a legal 40-card deck for a school.
    Rules: max 4 copies of same card_no, max 8 EVENT cards.

    synergy_weight=0  → 純數值貪婪（舊行為）
    synergy_weight=1  → 數值 + 技能連動並重（預設）
    synergy_weight=2  → 強調連動構築
    """
    rng = random.Random(seed)
    all_raw = load_all_cards()

    chars_raw  = [c for c in all_raw if c['category'] == 'CHARACTER' and c['school'] == school]
    events_raw = [c for c in all_raw if c['category'] == 'EVENT'
                  and (c['school'] == school or c['school'] == '烏野')]

    all_chars  = [Card.from_dict(c) for c in chars_raw]
    all_events = [Card.from_dict(c) for c in events_raw]

    deck: list[Card] = []
    counts: dict[str, int] = {}

    def add_card(card: Card, limit: int, evt_limit: int | None = None) -> bool:
        if len(deck) >= limit:
            return False
        if counts.get(card.card_no, 0) >= 4:
            return False
        if evt_limit is not None:
            evt_count = sum(1 for c in deck if c.category == 'EVENT')
            if evt_count >= evt_limit:
                return False
        deck.append(card)
        counts[card.card_no] = counts.get(card.card_no, 0) + 1
        return True

    # ── Phase 1: iterative synergy-aware character selection (32 slots) ──────
    # Re-score after each pick so that synergy with already-chosen cards accumulates
    remaining_chars = list(all_chars)
    while len(deck) < 32 and remaining_chars:
        # Score all candidates against current deck
        scored = sorted(
            remaining_chars,
            key=lambda c: _combined_score(c, deck, synergy_weight),
            reverse=True,
        )
        placed = False
        for card in scored:
            if counts.get(card.card_no, 0) < 4:
                add_card(card, 32)
                placed = True
                break
        if not placed:
            break  # all candidates are maxed

    # ── Phase 2: event selection (8 slots, synergy-aware) ────────────────────
    events_scored = sorted(
        all_events,
        key=lambda c: _combined_score(c, deck, synergy_weight),
        reverse=True,
    )
    for card in events_scored:
        if len(deck) >= 40:
            break
        evt_count = sum(1 for c in deck if c.category == 'EVENT')
        if evt_count >= 8:
            break
        add_card(card, 40)

    # ── Phase 3: fill remaining slots with best chars ─────────────────────────
    fill_scored = sorted(all_chars, key=lambda c: _combined_score(c, deck, synergy_weight), reverse=True)
    for card in fill_scored:
        if len(deck) >= 40:
            break
        add_card(card, 40)

    rng.shuffle(deck)
    return deck[:40]


def build_custom_deck(card_list: list[dict], seed: int | None = None) -> list[Card]:
    """Build deck from explicit list of {card_no / image_file, count} dicts."""
    rng = random.Random(seed)
    all_raw = {c['card_no']: c for c in load_all_cards()}
    deck: list[Card] = []
    counts: dict[str, int] = {}
    for entry in card_list:
        card_no = entry.get('card_no', '')
        count   = entry.get('count', 1)
        if card_no not in all_raw:
            continue
        card = Card.from_dict(all_raw[card_no])
        copies = min(count, 4 - counts.get(card_no, 0))
        for _ in range(copies):
            deck.append(card)
            counts[card_no] = counts.get(card_no, 0) + 1
    rng.shuffle(deck)
    return deck[:40]


def analyze_deck_synergy(deck: list[Card]) -> str:
    """Return a human-readable synergy report for a deck."""
    report = _analyzer.analyze(deck)
    lines = [
        f"連動總分: {report.total_synergy:.1f}",
        f"連動邊數: {len(report.edges)} 條",
        "",
        "主要連動鏈:",
    ]
    for chain in report.chain_descriptions:
        lines.append(f"  {chain}")

    if report.card_synergy_scores:
        top = sorted(report.card_synergy_scores.items(), key=lambda x: x[1], reverse=True)[:5]
        lines += ["", "連動核心牌 (Top 5):"]
        for card_no, score in top:
            lines.append(f"  {card_no}  +{score:.1f}")
    return "\n".join(lines)
