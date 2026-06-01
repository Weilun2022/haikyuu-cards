"""
技能連動性分析器

偵測八類連動：
  SYN_NAME      — 指名連動：技能文字直接提及隊友名稱
  SYN_ENTER     — 登場觸發：「當X出場時 +N」此回合條件性加值
  SYN_ZONE_COND — 區域條件：要求指定角色在特定功能區（舉球/攻擊/接球/攔網/發球）
  SYN_JOINT     — 聯合條件：EVENT 牌需要兩名指定角色同時在場才觸發強效
  SYN_VIA_EVENT — 事件部署：角色以特定 EVENT 牌的技能出場時才能解鎖強力效果
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
_RE_STAT_BOOST  = re.compile(r'(攻擊|攔網|接球|發球|舉球)值\s*[＋+](\d+)')

# Diverse discard condition — matches both Chinese 各不相同 and Japanese の不同/的不同 variants
_RE_DIVERSE_COND = re.compile(r'牌名.{0,6}不同.+?(\d+)種類')

# "當自己的「X」出場時...+N" — enter-triggered buff attributed specifically to X
_RE_ENTER_BOOST = re.compile(r'當自己的「([^」]+)」出場時[^。\n]*?[+＋](\d+)')

# "(zone)角色は/是「X」" — zone-slot dependency; handles both Chinese 是 and Japanese は
_RE_ZONE_COND   = re.compile(r'(舉球|攻擊|接球|攔網|發球)角色[は是]「([^」]+)」')

# OR zone condition: "(zone)角色は/是「X」或「Y」" — either card satisfies the zone requirement
_RE_ZONE_OR     = re.compile(r'(舉球|攻擊|接球|攔網|發球)角色[は是]「([^」]+)」或「([^」]+)」')

# Joint condition: two zone slots must BOTH be filled by named cards simultaneously.
# Handles: 且 (logical AND), ，/、 (comma-separated clauses in JP/CN text)
_RE_JOINT_COND  = re.compile(
    r'(舉球|攻擊|接球|攔網|發球)角色[は是]「([^」]+)」[，、且]'
    r'(?:.*?)(舉球|攻擊|接球|攔網|發球)角色[は是]「([^」]+)」'
)

# "以「X」の/的技能出場" — character's bonus activates only when deployed via event X
_RE_VIA_EVENT   = re.compile(r'以「([^」]+)」[のの的]技能出場')

# Multi-name discard sentence
_RE_DISCARD_SENTENCE = re.compile(r'棄牌區[^。\n]+')


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
        'SYN_VIA_EVENT': 3.0,   # character bonus only when deployed via named event
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
        # effect_refs: refs claimed by action-type edges (DISCARD, GUTS, ENTER)
        #   → prevents SYN_NAME from double-counting the same card
        # cond_refs: refs claimed by condition-type edges (JOINT, ZONE_COND, VIA_EVENT)
        #   → GUTS/DISCARD may overlap with cond_refs (e.g. どんぴしゃり activates ON
        #     宮侑+宮治 in field AND deploys new copies FROM Guts — both are real value)
        effect_refs: set[str] = set()
        cond_refs: set[str] = set()

        # 1. SYN_DISCARD — find ALL named cards inside every "棄牌區…" sentence
        for sentence in _RE_DISCARD_SENTENCE.findall(skill):
            for ref in _RE_NAME_REF.findall(sentence):
                if ref in name_index and ref != card.name and ref not in effect_refs:
                    edges.append(SynergyEdge(card.card_no, ref, 'SYN_DISCARD',
                                             self.WEIGHTS['SYN_DISCARD']))
                    effect_refs.add(ref)

        # 2. SYN_GUTS — deploy named card(s) from Guts pile
        for m in _RE_GUTS_REF.finditer(skill):
            ref = m.group(1)
            if ref in name_index and ref != card.name and ref not in effect_refs:
                edges.append(SynergyEdge(card.card_no, ref, 'SYN_GUTS',
                                         self.WEIGHTS['SYN_GUTS']))
                effect_refs.add(ref)

        # 3. SYN_ENTER — "當自己的「X」出場時 +N" (buff attributed only to X)
        enter_boost_refs: dict[str, int] = {}
        for m in _RE_ENTER_BOOST.finditer(skill):
            ref, n = m.group(1), int(m.group(2))
            enter_boost_refs[ref] = enter_boost_refs.get(ref, 0) + n
        for ref, total_boost in enter_boost_refs.items():
            if ref in name_index and ref != card.name and ref not in effect_refs:
                w = self.WEIGHTS['SYN_ENTER'] + min(total_boost * 0.2, 2.0)
                edges.append(SynergyEdge(card.card_no, ref, 'SYN_ENTER', w))
                effect_refs.add(ref)

        # 4. SYN_VIA_EVENT — "以「X」の/的技能出場" — character power unlocked only
        #    when deployed through a specific named event (e.g. 宮侑 P02-016 via どんぴしゃり)
        for m in _RE_VIA_EVENT.finditer(skill):
            ref = m.group(1)
            if ref in name_index and ref != card.name and ref not in cond_refs:
                edges.append(SynergyEdge(card.card_no, ref, 'SYN_VIA_EVENT',
                                         self.WEIGHTS['SYN_VIA_EVENT']))
                cond_refs.add(ref)

        # 5. SYN_JOINT — two zone slots must BOTH be filled by named cards simultaneously.
        #    Handles: 且 (and), ，/、 (comma) between the two zone conditions.
        #    DOES NOT add to effect_refs so that GUTS edges can coexist for the same
        #    cards (e.g. どんぴしゃり: needs 宮侑+宮治 in field AND deploys them from Guts).
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
                for ref in (a, b):
                    edges.append(SynergyEdge(card.card_no, ref, 'SYN_JOINT', w))
                    cond_refs.add(ref)
            else:
                for ref, present in ((a, a_present), (b, b_present)):
                    if present and ref not in cond_refs:
                        edges.append(SynergyEdge(card.card_no, ref, 'SYN_ZONE_COND',
                                                  self.WEIGHTS['SYN_ZONE_COND']))
                        cond_refs.add(ref)

        # 6. SYN_ZONE_COND — single zone requirement "(zone)角色は/是「X」"
        #    Also handles OR variants: "(zone)角色は「X」或「Y」" → both X and Y are valid
        or_refs: set[str] = set()
        for m in _RE_ZONE_OR.finditer(skill):
            for ref in (m.group(2), m.group(3)):
                if ref in name_index and ref != card.name and ref not in cond_refs:
                    edges.append(SynergyEdge(card.card_no, ref, 'SYN_ZONE_COND',
                                             self.WEIGHTS['SYN_ZONE_COND']))
                    cond_refs.add(ref)
                    or_refs.add(ref)
        for m in _RE_ZONE_COND.finditer(skill):
            ref = m.group(2)
            if ref in name_index and ref != card.name and ref not in cond_refs and ref not in or_refs:
                edges.append(SynergyEdge(card.card_no, ref, 'SYN_ZONE_COND',
                                         self.WEIGHTS['SYN_ZONE_COND']))
                cond_refs.add(ref)

        # 7. SYN_NAME — remaining name references not already classified
        all_handled = effect_refs | cond_refs
        seen_name_refs: set[str] = set()
        for m in _RE_NAME_REF.finditer(skill):
            ref = m.group(1)
            if (ref in name_index and ref != card.name
                    and ref not in all_handled and ref not in seen_name_refs):
                seen_name_refs.add(ref)
                boost = sum(int(n) for _, n in _RE_STAT_BOOST.findall(skill))
                w = self.WEIGHTS['SYN_NAME'] + min(boost * 0.1, 1.0)
                edges.append(SynergyEdge(card.card_no, ref, 'SYN_NAME', w))

        # 8. SYN_CONDITION — diverse discard pile condition
        if _RE_DIVERSE_COND.search(skill):
            threshold = int(_RE_DIVERSE_COND.search(skill).group(1))
            unique_names = len({c.name for c in deck if c.category == 'CHARACTER'})
            coverage = min(unique_names / max(threshold, 1), 1.0)
            edges.append(SynergyEdge(card.card_no, '__condition__', 'SYN_CONDITION',
                                     self.WEIGHTS['SYN_CONDITION'] * coverage))

        # 9. SYN_EVENT — Event cards: count deck characters that benefit from the trigger
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
        for e in by_type.get('SYN_VIA_EVENT', []):
            chains.append(f"[事件部署] 以「{e.target}」出場解鎖（強度 {e.weight:.1f}）")
        for e in by_type.get('SYN_ZONE_COND', []):
            chains.append(f"[區域依賴] → 需「{e.target}」在指定區（強度 {e.weight:.1f}）")
        for e in by_type.get('SYN_ENTER', []):
            chains.append(f"[登場觸發] 「{e.target}」入場加值（強度 {e.weight:.1f}）")
        for e in (by_type.get('SYN_NAME', []))[:6]:
            chains.append(f"[指名連動] → 「{e.target}」（強度 {e.weight:.1f}）")
        if by_type.get('SYN_CONDITION'):
            chains.append(f"[條件解鎖] ×{len(by_type['SYN_CONDITION'])} 組（種類多樣性觸發）")
        return chains
