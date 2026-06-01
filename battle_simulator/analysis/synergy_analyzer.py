"""
技能連動性分析器

偵測七類連動：
  SYN_NAME      — 指名連動：技能文字直接提及隊友名稱
  SYN_ENTER     — 登場觸發：「當X出場時 +N」此回合條件性加值
  SYN_ZONE_COND — 區域條件：要求指定角色在特定功能區（舉球/攻擊/接球/攔網/發球）
  SYN_JOINT     — 聯合條件：EVENT 牌需要兩名指定角色同時在場才觸發強效
  SYN_DISCARD   — 棄牌循環：從棄牌區召回指定角色
  SYN_GUTS      — Guts 召喚：從 Guts 直接出場指定角色
  SYN_EVENT     — 事件觸發：EVENT 牌觸發時惠及場上角色
  SYN_CONDITION — 條件解鎖：達到特定牌組條件才能解鎖的強力效果
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..engine.card import Card


# ── Pattern library ──────────────────────────────────────────────────────────

_RE_NAME_REF    = re.compile(r'「([^」]{2,12})」')
_RE_DISCARD_REF = re.compile(r'棄牌區.{0,20}「([^」]+)」')
_RE_GUTS_REF    = re.compile(r'Guts.{0,15}「([^」]+)」.{0,10}出場')
_RE_DIVERSE_COND= re.compile(r'牌名各不相同.+?(\d+)種類')
_RE_STAT_BOOST  = re.compile(r'(攻擊|攔網|接球|發球|舉球)值\s*[＋+](\d+)')

# New: "當自己的「X」出場時...+N" — enter-triggered buff, specifically attributed to X
_RE_ENTER_BOOST = re.compile(r'當自己的「([^」]+)」出場時[^。\n]*?[+＋](\d+)')

# New: "(zone)角色是「X」" — requires X to be in a specific functional zone
_RE_ZONE_COND   = re.compile(r'(舉球|攻擊|接球|攔網|發球)角色是「([^」]+)」')

# New: multi-name discard — find ALL 「」names within the same discard sentence
_RE_DISCARD_SENTENCE = re.compile(r'棄牌區[^。\n]+')

# New: joint condition — "(zone)角色是「X」且(zone)角色是「Y」" (two simultaneous requirements)
_RE_JOINT_COND  = re.compile(
    r'(舉球|攻擊|接球|攔網|發球)角色是「([^」]+)」且(舉球|攻擊|接球|攔網|發球)角色是「([^」]+)」'
)


@dataclass
class SynergyEdge:
    source: str          # card_no of the card providing the effect
    target: str          # card name being referenced
    syn_type: str
    weight: float


@dataclass
class DeckSynergyReport:
    edges: list[SynergyEdge] = field(default_factory=list)
    card_synergy_scores: dict[str, float] = field(default_factory=dict)
    total_synergy: float = 0.0
    chain_descriptions: list[str] = field(default_factory=list)


class SynergyAnalyzer:
    WEIGHTS = {
        'SYN_NAME':      1.5,
        'SYN_ENTER':     2.0,   # conditional enter buff — stronger than generic name ref
        'SYN_ZONE_COND': 2.5,   # hard zone dependency — card is useless without the target
        'SYN_JOINT':     3.5,   # requires two specific cards simultaneously
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
        handled: set[str] = set()  # refs already assigned a specific edge type

        # 1. SYN_DISCARD — from discard pile, retrieve named card(s)
        #    Scan every "棄牌區…" sentence to capture ALL names in that sentence,
        #    not just the first one (fixes 鬼と鬼だな double-recovery).
        for sentence in _RE_DISCARD_SENTENCE.findall(skill):
            for ref in _RE_NAME_REF.findall(sentence):
                if ref in name_index and ref != card.name and ref not in handled:
                    edges.append(SynergyEdge(card.card_no, ref, 'SYN_DISCARD',
                                             self.WEIGHTS['SYN_DISCARD']))
                    handled.add(ref)

        # 2. SYN_GUTS — deploy from Guts pile
        for m in _RE_GUTS_REF.finditer(skill):
            ref = m.group(1)
            if ref in name_index and ref != card.name and ref not in handled:
                edges.append(SynergyEdge(card.card_no, ref, 'SYN_GUTS',
                                         self.WEIGHTS['SYN_GUTS']))
                handled.add(ref)

        # 3. SYN_ENTER — "當自己的「X」出場時 +N"
        #    Attributes the boost only to the specifically named card X.
        enter_boost_refs: dict[str, int] = {}
        for m in _RE_ENTER_BOOST.finditer(skill):
            ref, n = m.group(1), int(m.group(2))
            enter_boost_refs[ref] = enter_boost_refs.get(ref, 0) + n
        for ref, total_boost in enter_boost_refs.items():
            if ref in name_index and ref != card.name and ref not in handled:
                w = self.WEIGHTS['SYN_ENTER'] + min(total_boost * 0.2, 2.0)
                edges.append(SynergyEdge(card.card_no, ref, 'SYN_ENTER', w))
                handled.add(ref)

        # 4. SYN_JOINT — EVENT requires two named cards simultaneously on field
        #    "(zone)角色是「X」且(zone)角色是「Y」" → strongest synergy type
        #    Only awards full JOINT weight when BOTH required cards are in deck.
        #    If only one is present, falls back to SYN_ZONE_COND weight to still
        #    incentivize picking the missing card.
        joint_pairs: set[tuple[str, str]] = set()
        for m in _RE_JOINT_COND.finditer(skill):
            a, b = m.group(2), m.group(4)
            if (a, b) not in joint_pairs and (b, a) not in joint_pairs:
                joint_pairs.add((a, b))
        for a, b in joint_pairs:
            a_present = a in name_index and a != card.name
            b_present = b in name_index and b != card.name
            boost = sum(int(n) for _, n in _RE_STAT_BOOST.findall(skill))
            if a_present and b_present:
                w = self.WEIGHTS['SYN_JOINT'] + min(boost * 0.15, 1.5)
                edges.append(SynergyEdge(card.card_no, a, 'SYN_JOINT', w))
                edges.append(SynergyEdge(card.card_no, b, 'SYN_JOINT', w))
                handled.add(a)
                handled.add(b)
            else:
                # Only one piece present — partial credit, incentivise picking the other
                for ref, present in ((a, a_present), (b, b_present)):
                    if present and ref not in handled:
                        edges.append(SynergyEdge(card.card_no, ref, 'SYN_ZONE_COND',
                                                  self.WEIGHTS['SYN_ZONE_COND']))
                        handled.add(ref)

        # 5. SYN_ZONE_COND — "(zone)角色是「X」" without joint (single zone requirement)
        for m in _RE_ZONE_COND.finditer(skill):
            zone, ref = m.group(1), m.group(2)
            if ref in name_index and ref != card.name and ref not in handled:
                edges.append(SynergyEdge(card.card_no, ref, 'SYN_ZONE_COND',
                                         self.WEIGHTS['SYN_ZONE_COND']))
                handled.add(ref)

        # 6. SYN_NAME — remaining name references not already classified
        #    Deduplicate: each unique name produces at most one SYN_NAME edge.
        seen_name_refs: set[str] = set()
        for m in _RE_NAME_REF.finditer(skill):
            ref = m.group(1)
            if ref in name_index and ref != card.name and ref not in handled and ref not in seen_name_refs:
                seen_name_refs.add(ref)
                # Use boost only when skill directly grants a stat to this ref
                # (no enter-trigger pattern present for this ref)
                boost = sum(int(n) for _, n in _RE_STAT_BOOST.findall(skill))
                w = self.WEIGHTS['SYN_NAME'] + min(boost * 0.1, 1.0)
                edges.append(SynergyEdge(card.card_no, ref, 'SYN_NAME', w))

        # 7. SYN_CONDITION — skill needs diverse discard pile
        if _RE_DIVERSE_COND.search(skill):
            threshold = int(_RE_DIVERSE_COND.search(skill).group(1))
            unique_names = len({c.name for c in deck if c.category == 'CHARACTER'})
            coverage = min(unique_names / max(threshold, 1), 1.0)
            edges.append(SynergyEdge(card.card_no, '__condition__', 'SYN_CONDITION',
                                     self.WEIGHTS['SYN_CONDITION'] * coverage))

        # 8. SYN_EVENT — Event cards: count deck characters that benefit from the trigger
        if card.category == 'EVENT':
            beneficiaries = self._count_event_beneficiaries(card, deck)
            if beneficiaries > 0:
                edges.append(SynergyEdge(card.card_no, '__event_field__', 'SYN_EVENT',
                                         self.WEIGHTS['SYN_EVENT'] * min(beneficiaries / 3, 2.0)))

        return edges

    def _count_event_beneficiaries(self, event: Card, deck: list[Card]) -> int:
        """Count characters in deck that would benefit from this event's trigger."""
        count = 0
        triggers = event.skill_tags
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
        by_type: dict[str, list[SynergyEdge]] = {}
        for e in edges:
            by_type.setdefault(e.syn_type, []).append(e)

        for e in by_type.get('SYN_DISCARD', []):
            chains.append(f"[棄牌循環] → 「{e.target}」（強度 {e.weight:.1f}）")
        for e in by_type.get('SYN_GUTS', []):
            chains.append(f"[Guts召喚] → 「{e.target}」（強度 {e.weight:.1f}）")
        for e in by_type.get('SYN_JOINT', []):
            chains.append(f"[聯合條件] {e.source} ×「{e.target}」（強度 {e.weight:.1f}）")
        for e in by_type.get('SYN_ZONE_COND', []):
            chains.append(f"[區域依賴] → 需「{e.target}」在指定區（強度 {e.weight:.1f}）")
        for e in by_type.get('SYN_ENTER', []):
            chains.append(f"[登場觸發] 「{e.target}」入場加值（強度 {e.weight:.1f}）")
        for e in (by_type.get('SYN_NAME', []))[:6]:
            chains.append(f"[指名連動] → 「{e.target}」（強度 {e.weight:.1f}）")
        if by_type.get('SYN_CONDITION'):
            chains.append(f"[條件解鎖] ×{len(by_type['SYN_CONDITION'])} 組（種類多樣性觸發）")
        return chains
