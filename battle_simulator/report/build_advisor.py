"""Deck building advisor: recommend deck construction against a given meta."""
from __future__ import annotations

from collections import Counter
from ..engine.card import Card
from ..analysis.archetype_classifier import Archetype, classify_deck
from ..analysis.counter_analyzer import COUNTER_ADVICE
from ..data_loader import load_all_cards
from ..simulation.deck_sampler import build_school_deck


SCHOOL_ARCHETYPE_HINTS = {
    '伊達工業': Archetype.DEF,
    '音駒':    Archetype.DEF,
    '稲荷崎':  Archetype.AGG,
    '白鳥沢':  Archetype.AGG,
    '梟谷':    Archetype.COMBO,
    '青葉城西': Archetype.TEMPO,
    '烏野':    Archetype.HYBRID,
}


def _stat_power(c: Card) -> float:
    return c.atk * 1.5 + c.blk * 1.2 + c.rcv * 1.0 + c.srv * 1.1 + c.tos * 0.8


def recommend_deck(
    school: str,
    meta_threats: list[Archetype] | None = None,
    budget: str = "全部",
) -> str:
    """
    Produce a deck building recommendation for a school targeting given meta threats.
    budget: '全部' | '稀有以下' | '普通卡' (rarity filter)
    """
    all_raw = load_all_cards()

    rarity_filter: set[str] = set()
    if budget == "普通卡":
        rarity_filter = {"N", "NP"}
    elif budget == "稀有以下":
        rarity_filter = {"N", "NP", "R", "RP"}

    pool = [
        Card.from_dict(c) for c in all_raw
        if c['school'] == school
        and (not rarity_filter or c.get('rarity_code', '') in rarity_filter)
    ]
    evt_pool = [
        Card.from_dict(c) for c in all_raw
        if c['category'] == 'EVENT'
        and (c['school'] == school or c['school'] == '烏野')
        and (not rarity_filter or c.get('rarity_code', '') in rarity_filter)
    ]

    if not pool:
        return f"找不到學校 [{school}] 的可用卡牌（預算：{budget}）"

    archetype = SCHOOL_ARCHETYPE_HINTS.get(school, Archetype.HYBRID)
    advice = COUNTER_ADVICE.get(archetype, COUNTER_ADVICE[Archetype.HYBRID])
    criteria = advice['tech_cards_criteria']

    # Separate tech cards (counter-specific) from general power cards
    tech_cards = [c for c in pool if c.category == 'CHARACTER' and criteria(c)]
    general_chars = [c for c in pool if c.category == 'CHARACTER' and c not in tech_cards]

    tech_cards.sort(key=_stat_power, reverse=True)
    general_chars.sort(key=_stat_power, reverse=True)
    evt_pool.sort(key=_stat_power, reverse=True)

    # Build 40-card deck: 8 tech + 24 general + 8 event
    deck: list[Card] = []
    counts: Counter = Counter()

    def add_cards(source: list[Card], limit: int):
        for card in source:
            if len(deck) >= limit:
                break
            can_add = min(4 - counts[card.card_no], limit - len(deck))
            for _ in range(can_add):
                deck.append(card)
                counts[card.card_no] += 1

    add_cards(tech_cards, 8)
    add_cards(general_chars, 32)
    add_cards(evt_pool, 40)
    add_cards(general_chars, 40)  # fill any remaining slots

    profile = classify_deck(deck, school)

    # Format output
    char_slots = [c for c in deck if c.category == 'CHARACTER']
    evt_slots = [c for c in deck if c.category == 'EVENT']

    char_counts: Counter = Counter(c.card_no for c in char_slots)
    evt_counts: Counter = Counter(c.card_no for c in evt_slots)

    card_map = {c.card_no: c for c in deck}

    lines = [
        f"# 構築建議：{school}（{archetype.value}）",
        f"預算限制: {budget} | 總計: {len(deck)} 張",
        "",
        f"## 牌組類型分析",
        f"推測類型: {profile.archetype.value}（信心度 {profile.confidence:.0%}）",
        f"數值輪廓: ATK={profile.avg_atk:.1f} BLK={profile.avg_blk:.1f} "
        f"RCV={profile.avg_rcv:.1f} SRV={profile.avg_srv:.1f} TOS={profile.avg_tos:.1f}",
        "",
        f"## 核心策略",
        advice['key_strategy'],
        "",
    ]

    if meta_threats:
        lines += [
            "## 針對環境威脅",
            *[f"- 對抗 **{t.value}**: {COUNTER_ADVICE.get(t, {}).get('key_strategy', '—')}" for t in meta_threats],
            "",
        ]

    lines += [
        "## 角色牌清單",
        f"{'張數':>4}  {'卡號':<14}  {'名稱':<12}  {'學校':<6}  ATK BLK RCV SRV TOS  {'技能標籤'}",
        "-" * 72,
    ]
    for card_no, cnt in sorted(char_counts.items(), key=lambda x: -x[1]):
        c = card_map[card_no]
        tags = " ".join(f"[{t}]" for t in c.skill_tags[:3])
        lines.append(
            f"{cnt:>4}x  {c.card_no:<14}  {c.name:<12}  {c.school:<6}  "
            f"{c.atk:>3} {c.blk:>3} {c.rcv:>3} {c.srv:>3} {c.tos:>3}  {tags}"
        )

    lines += [
        "",
        "## 事件牌清單",
        f"{'張數':>4}  {'卡號':<14}  {'名稱':<16}  {'技能預覽'}",
        "-" * 72,
    ]
    for card_no, cnt in sorted(evt_counts.items(), key=lambda x: -x[1]):
        c = card_map[card_no]
        preview = c.skill_zh[:50] + ("…" if len(c.skill_zh) > 50 else "")
        lines.append(f"{cnt:>4}x  {c.card_no:<14}  {c.name:<16}  {preview}")

    lines += [
        "",
        "## 數值統計",
        f"角色牌: {len(char_slots)} 張 | 事件牌: {len(evt_slots)} 張",
        f"平均 ATK: {sum(c.atk for c in char_slots)/len(char_slots):.2f}",
        f"平均 BLK: {sum(c.blk for c in char_slots)/len(char_slots):.2f}",
        f"平均 RCV: {sum(c.rcv for c in char_slots)/len(char_slots):.2f}",
        f"平均 SRV: {sum(c.srv for c in char_slots)/len(char_slots):.2f}",
        f"平均 TOS: {sum(c.tos for c in char_slots)/len(char_slots):.2f}",
    ]

    return "\n".join(lines)
