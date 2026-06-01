"""
技能連動性分析器

偵測五類連動：
  SYN_NAME     — 指名連動：技能文字直接提及隊友名稱
  SYN_DISCARD  — 棄牌循環：從棄牌區召回指定角色
  SYN_GUTS     — Guts 召喚：從 Guts 直接出場指定角色
  SYN_EVENT    — 事件觸發：EVENT 牌觸發時惠及場上角色
  SYN_CONDITION— 條件解鎖：達到特定牌組條件才能解鎖的強力效果
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..engine.card import Card


# ── Pattern library ──────────────────────────────────────────────────────────

_RE_NAME_REF    = re.compile(r'「([^」]{2,12})」')          # 「影山 飛雄」
_RE_DISCARD_REF = re.compile(r'棄牌區.{0,20}「([^」]+)」')  # 從棄牌區...「X」
_RE_GUTS_REF    = re.compile(r'Guts.{0,15}「([^」]+)」.{0,10}出場')
_RE_DIVERSE_COND= re.compile(r'牌名各不相同.+?(\d+)種類')   # 棄牌區種類數條件
_RE_STAT_BOOST  = re.compile(r'(攻擊|攔網|接球|發球|舉球)值\s*[＋+](\d+)')


@dataclass
class SynergyEdge:
    source: str          # card_no of the card providing the effect
    target: str          # card_no / card name being referenced
    syn_type: str        # SYN_NAME | SYN_DISCARD | SYN_GUTS | SYN_EVENT | SYN_CONDITION
    weight: float        # synergy strength


@dataclass
class DeckSynergyReport:
    edges: list[SynergyEdge] = field(default_factory=list)
    card_synergy_scores: dict[str, float] = field(default_factory=dict)  # card_no → total synergy
    total_synergy: float = 0.0
    chain_descriptions: list[str] = field(default_factory=list)


class SynergyAnalyzer:
    # Weights per synergy type
    WEIGHTS = {
        'SYN_NAME':      1.5,
        'SYN_DISCARD':   3.0,   # loop value is very high
        'SYN_GUTS':      2.5,
        'SYN_EVENT':     1.0,
        'SYN_CONDITION': 2.0,
    }

    def analyze(self, deck: list[Card]) -> DeckSynergyReport:
        report = DeckSynergyReport()
        name_to_cards = self._build_name_index(deck)

        for card in deck:
            if not card.skill_zh.strip():
                continue
            edges = self._detect_edges(card, name_to_cards, deck)
            report.edges.extend(edges)

        # Aggregate per-card scores
        scores: dict[str, float] = {}
        for e in report.edges:
            scores[e.source] = scores.get(e.source, 0.0) + e.weight
        report.card_synergy_scores = scores
        report.total_synergy = sum(scores.values())
        report.chain_descriptions = self._describe_chains(report.edges, name_to_cards)
        return report

    def score_card_in_context(self, card: Card, deck: list[Card]) -> float:
        """Return the synergy score a card would contribute to `deck`."""
        if not card.skill_zh.strip():
            return 0.0
        name_to_cards = self._build_name_index(deck)
        edges = self._detect_edges(card, name_to_cards, deck)
        return sum(e.weight for e in edges)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_name_index(self, deck: list[Card]) -> dict[str, list[Card]]:
        index: dict[str, list[Card]] = {}
        for c in deck:
            index.setdefault(c.name, []).append(c)
        return index

    def _detect_edges(
        self,
        card: Card,
        name_index: dict[str, list[Card]],
        deck: list[Card],
    ) -> list[SynergyEdge]:
        edges: list[SynergyEdge] = []
        skill = card.skill_zh

        # 1. SYN_DISCARD — from discard pile, retrieve named card
        for m in _RE_DISCARD_REF.finditer(skill):
            ref = m.group(1)
            if ref in name_index and ref != card.name:
                edges.append(SynergyEdge(card.card_no, ref, 'SYN_DISCARD',
                                         self.WEIGHTS['SYN_DISCARD']))

        # 2. SYN_GUTS — deploy from Guts pile
        for m in _RE_GUTS_REF.finditer(skill):
            ref = m.group(1)
            if ref in name_index and ref != card.name:
                edges.append(SynergyEdge(card.card_no, ref, 'SYN_GUTS',
                                         self.WEIGHTS['SYN_GUTS']))

        # 3. SYN_NAME — any other name reference not already caught
        discard_refs = {m.group(1) for m in _RE_DISCARD_REF.finditer(skill)}
        guts_refs    = {m.group(1) for m in _RE_GUTS_REF.finditer(skill)}
        for m in _RE_NAME_REF.finditer(skill):
            ref = m.group(1)
            if ref in name_index and ref != card.name and ref not in discard_refs | guts_refs:
                # Weight scales with the stat boost granted
                boost = sum(int(b) for _, b in _RE_STAT_BOOST.findall(skill))
                w = self.WEIGHTS['SYN_NAME'] + min(boost * 0.15, 1.5)
                edges.append(SynergyEdge(card.card_no, ref, 'SYN_NAME', w))

        # 4. SYN_CONDITION — skill needs diverse discard pile
        if _RE_DIVERSE_COND.search(skill):
            threshold = int(_RE_DIVERSE_COND.search(skill).group(1))
            unique_names = len({c.name for c in deck if c.category == 'CHARACTER'})
            # Higher score if the deck naturally meets the condition
            coverage = min(unique_names / max(threshold, 1), 1.0)
            edges.append(SynergyEdge(card.card_no, '__condition__', 'SYN_CONDITION',
                                     self.WEIGHTS['SYN_CONDITION'] * coverage))

        # 5. SYN_EVENT — Event cards: count deck characters that benefit from the trigger
        if card.category == 'EVENT':
            beneficiaries = self._count_event_beneficiaries(card, deck)
            if beneficiaries > 0:
                edges.append(SynergyEdge(card.card_no, '__event_field__', 'SYN_EVENT',
                                         self.WEIGHTS['SYN_EVENT'] * min(beneficiaries / 3, 2.0)))

        return edges

    def _count_event_beneficiaries(self, event: Card, deck: list[Card]) -> int:
        """Count characters in deck that would benefit from this event's trigger."""
        count = 0
        triggers = event.skill_tags  # e.g. ['攻擊', '接球']
        stat_map = {'攻擊': 'atk', '接球': 'rcv', '攔網': 'blk', '發球': 'srv', '舉球': 'tos'}
        for c in deck:
            if c.category != 'CHARACTER':
                continue
            for tag in triggers:
                stat = stat_map.get(tag)
                if stat and getattr(c, stat, 0) > 0:
                    count += 1
                    break
        return count

    def _describe_chains(
        self,
        edges: list[SynergyEdge],
        name_index: dict[str, list[Card]],
    ) -> list[str]:
        chains = []
        discard_loops = [e for e in edges if e.syn_type == 'SYN_DISCARD']
        guts_deploys  = [e for e in edges if e.syn_type == 'SYN_GUTS']
        name_refs     = [e for e in edges if e.syn_type == 'SYN_NAME']
        cond_unlocks  = [e for e in edges if e.syn_type == 'SYN_CONDITION']

        for e in discard_loops:
            src_cards = name_index.get(e.source)  # might be card_no, not name
            chains.append(f"[棄牌循環] → 「{e.target}」（強度 {e.weight:.1f}）")
        for e in guts_deploys:
            chains.append(f"[Guts召喚] → 「{e.target}」（強度 {e.weight:.1f}）")
        for e in name_refs[:6]:  # top 6
            chains.append(f"[指名連動] → 「{e.target}」（強度 {e.weight:.1f}）")
        if cond_unlocks:
            chains.append(f"[條件解鎖] ×{len(cond_unlocks)} 組（種類多樣性觸發）")
        return chains
