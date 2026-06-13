"""
技能連動性分析器

偵測連動類型：
  SYN_NAME           — 指名連動：技能文字直接提及隊友名稱
  SYN_ENTER          — 登場觸發：「當X出場時 +N」此回合條件性加值
  SYN_ZONE_COND      — 區域條件：要求指定角色在特定功能區（舉球/攻擊/接球/攔網/發球）
  SYN_JOINT          — 聯合條件：EVENT 牌需要兩名指定角色同時在場才觸發強效
  SYN_VIA_EVENT      — 事件部署：角色以特定 EVENT 牌的技能出場時才能解鎖強力效果
  SYN_DISCARD        — 棄牌循環：從棄牌區召回指定角色
  SYN_GUTS           — Guts 召喚：從 Guts 直接出場指定角色
  SYN_EVENT          — 事件觸發：EVENT 牌觸發時惠及場上角色
  SYN_CONDITION      — 條件解鎖：達到牌組條件（如墓地種類多樣性）才能解鎖的強力效果
  SYN_MILL_FUEL      — 墓地填充：主動把牌送進棄牌區，餵養種類多樣性引擎
  SYN_ROLE_RECOVER   — 墓地回收：以角色/學校為條件從棄牌區回收（非指名）
  SYN_EVENT_RECOVER  — Event區回收：從 Event 區取回已用事件牌至手牌，實現重複使用

引擎偵測（detect_engines）：把上述邊組合成可運作的「核心機制」——
  例如「墓地豐度引擎」= 填充牌 → 種類條件 → 收益牌 → 回收牌的閉環；
  「Event區Loop引擎」= 事件發動→Event區→回收角色撿回→重複使用；
  並評估其完成度與運轉可靠度，指出補完方向。
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

# Diverse discard condition — the discard pile must hold N differently-named school
# character cards. Card text uses several phrasings of "different names":
#   「牌名各不相同」(各-不-相-同) and 「牌名的不同」(的-不-同).
# Anchor on 牌名 … 不(相)同 … N種類 so all variants match and the threshold is captured.
_RE_DIVERSE_COND = re.compile(r'牌名.{0,4}不(?:相)?同.{0,20}?(\d+)種類')

# Mill fuel — a card that actively pushes cards into the discard pile, feeding the
# diversity engine: discard from hand, self-discard, or deck-to-discard.
_RE_MILL_FUEL = re.compile(r'(?:從(?:自己的)?手牌棄置|棄置此牌|牌庫.{0,8}棄置|送入棄牌區)')

# Role / school-based discard recovery — recovers ANY card of a role or school from
# the discard (not a specific named card), e.g. 「從棄牌區將稲荷崎的WS或MB角色牌…加入手牌」.
# This is engine-sustain value: it refills the hand while the pile stays stocked.
_RE_ROLE_RECOVER = re.compile(r'從(?:自己的)?棄牌區將.{0,16}?(?:角色牌|WS|MB).{0,10}?加入手牌')

# Event Zone recovery — the key mechanism that enables event replay loops.
# A character recovers a used event (which went to the Event Zone) back to hand.
# Example: 北信介 P02-024 「從自己的Event區稲荷崎的牌最多加1張至手牌」
# or D03-001 宮侑 「從自己的Event區將「今日 何をする？」最多1張加入手牌」
_RE_EVENT_ZONE_RECOVER = re.compile(r'從(?:自己的)?Event區.{0,30}?(?:加入手牌|至手牌)')

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


@dataclass
class DeckEngine:
    """A coherent core mechanism identified in a deck.

    role_cards maps an engine role (e.g. '收益', '填充', '回收', '核心', '啟動')
    to the card_nos that fill it. coherence (0-1) is how reliably the engine turns
    on given the current build; advice lists concrete completion suggestions.
    """
    name: str
    summary: str
    role_cards: dict[str, list[str]] = field(default_factory=dict)
    coherence: float = 0.0
    advice: list[str] = field(default_factory=list)


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
        'SYN_MILL_FUEL':      1.5,   # fills the discard pile — only useful with a payoff
        'SYN_ROLE_RECOVER':   2.5,   # recurs any role/school card from discard (engine sustain)
        'SYN_EVENT_RECOVER':  3.5,   # highest: enables event replay loops (e.g. どんぴしゃり loop)
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

    # ── Engine detection ────────────────────────────────────────────────────────

    def detect_engines(self, deck: list[Card]) -> list[DeckEngine]:
        """Identify the deck's core operating mechanisms (engines).

        Unlike per-card edges, an engine is a multi-card loop. We currently
        recognise three:
          • 墓地豐度引擎 — fill discard → diversity condition → payoff → recover
          • Guts速攻引擎 — event enabler → deploy named pieces from Guts
          • 區域聯動引擎 — two named cards must occupy specific zones together
        """
        engines: list[DeckEngine] = []
        first = {}                      # card_no -> Card (first seen)
        for c in deck:
            first.setdefault(c.card_no, c)
        uniq = list(first.values())

        eng = self._detect_event_loop_engine(deck, uniq)
        if eng:
            engines.append(eng)
        eng = self._detect_diversity_engine(deck, uniq)
        if eng:
            engines.append(eng)
        eng = self._detect_guts_combo_engine(deck, uniq)
        if eng:
            engines.append(eng)
        eng = self._detect_zone_lock_engine(deck, uniq)
        if eng:
            engines.append(eng)

        engines.sort(key=lambda e: e.coherence, reverse=True)
        return engines

    def _detect_event_loop_engine(
        self, deck: list[Card], uniq: list[Card],
    ) -> DeckEngine | None:
        """Detect the Event-Zone replay loop.

        Pattern: event card activates → goes to Event Zone → a recovery character
        (接球區) retrieves it back to hand → event replayed next turn.
        The canonical example is: どんぴしゃり → Event區 → 北信介 P02-024 回收 → repeat.
        """
        recyclers = [c for c in uniq if _RE_EVENT_ZONE_RECOVER.search(c.skill_zh)]
        if not recyclers:
            return None

        guts_events = [c for c in uniq
                       if c.category == 'EVENT' and _RE_GUTS_REF.search(c.skill_zh)]
        if not guts_events:
            return None

        via_chars = [c for c in uniq if _RE_VIA_EVENT.search(c.skill_zh)]

        recycler_copies = sum(1 for c in deck if _RE_EVENT_ZONE_RECOVER.search(c.skill_zh))
        event_copies    = sum(1 for c in deck
                              if c.category == 'EVENT' and _RE_GUTS_REF.search(c.skill_zh))

        recycler_cov = min(recycler_copies / 3, 1.0)
        event_cov    = min(event_copies / 4, 1.0)
        piece_cov    = min(len(via_chars) / 2, 1.0)
        coherence    = round((recycler_cov + event_cov + piece_cov) / 3, 2)

        advice: list[str] = []
        if recycler_copies < 2:
            advice.append(
                f"Event回收角色（接球區）現有 {recycler_copies} 張，建議補到3張確保Loop穩定。"
            )
        if event_copies < 3:
            advice.append(
                f"Loop核心事件現有 {event_copies} 張，建議補到4張以提高首回觸發率。"
            )
        if not via_chars:
            advice.append("缺少以事件技能出場解鎖加值的角色，Loop產出僅為基礎效果。")

        return DeckEngine(
            name="Event區Loop引擎",
            summary=(
                "事件牌發動後進入Event區；接球區角色（如北信介P02-024）"
                "棄1張手牌+3 Guts，將其取回手牌，下回合重複發動。"
                "每個Loop循環同時填充棄牌區，雙引擎聯動。"
            ),
            role_cards={
                '回收核心（接球區）': [c.card_no for c in recyclers],
                'Loop事件':           [c.card_no for c in guts_events],
                '事件出場解鎖角色':   [c.card_no for c in via_chars],
            },
            coherence=coherence,
            advice=advice,
        )

    def _detect_diversity_engine(
        self, deck: list[Card], uniq: list[Card],
    ) -> DeckEngine | None:
        payoff = [c for c in uniq if _RE_DIVERSE_COND.search(c.skill_zh)]
        if not payoff:
            return None

        fuel    = [c for c in uniq if _RE_MILL_FUEL.search(c.skill_zh)]
        draw    = [c for c in uniq if '抽' in c.skill_zh and c not in fuel]
        recover = [c for c in uniq if _RE_ROLE_RECOVER.search(c.skill_zh)]
        threshold = max(int(_RE_DIVERSE_COND.search(c.skill_zh).group(1)) for c in payoff)
        unique_char_names = len({c.name for c in deck if c.category == 'CHARACTER'})

        name_cov = min(unique_char_names / max(threshold, 1), 1.0)
        fuel_cov = min((len(fuel) + 0.5 * len(draw)) / 6, 1.0)
        coherence = round(name_cov * (0.4 + 0.6 * fuel_cov), 2)

        advice: list[str] = []
        if unique_char_names < threshold + 2:
            advice.append(
                f"棄牌種類門檻為 {threshold}，但牌組僅有 {unique_char_names} 種不同角色名；"
                f"建議增加到 {threshold + 3}+ 種，確保中期能穩定達標。"
            )
        if len(fuel) + len(draw) < 6:
            advice.append(
                f"主動填充/抽牌來源僅 {len(fuel) + len(draw)} 張，引擎啟動偏慢；"
                f"建議補入更多『棄牌/抽牌』牌把角色送進墓地。"
            )
        if not recover:
            advice.append("缺少墓地回收牌，難以把資源拉回手牌；可考慮加入角色/學校回收效果。")

        return DeckEngine(
            name="墓地豐度引擎",
            summary=(
                f"以墓地累積 {threshold} 種不同名稱的角色為開關，"
                f"解鎖收益牌的強化效果（攻擊/舉球加值、無視對手攔網等）。"
            ),
            role_cards={
                '收益（達標強化）': [c.card_no for c in payoff],
                '填充（送墓地）':   [c.card_no for c in fuel],
                '抽牌（挖掘）':     [c.card_no for c in draw],
                '回收（墓地→手）': [c.card_no for c in recover],
            },
            coherence=coherence,
            advice=advice,
        )

    def _detect_guts_combo_engine(
        self, deck: list[Card], uniq: list[Card],
    ) -> DeckEngine | None:
        via_chars     = [c for c in uniq if _RE_VIA_EVENT.search(c.skill_zh)]
        guts_events   = [c for c in uniq if _RE_GUTS_REF.search(c.skill_zh)]
        if not via_chars and not guts_events:
            return None

        # The named character pieces deployed from Guts (the VIA_EVENT refs are the
        # enabler EVENTS themselves, already captured by via_chars — not pieces).
        named_targets: set[str] = set()
        for c in guts_events:
            for m in _RE_GUTS_REF.finditer(c.skill_zh):
                named_targets.add(m.group(1))

        deck_names = {c.name for c in deck}
        present = [n for n in named_targets if n in deck_names]
        missing = [n for n in named_targets if n not in deck_names]

        # Coherence: do we have both the enablers AND the named pieces they deploy?
        enabler_present = bool(guts_events or via_chars)
        piece_cov = (len(present) / len(named_targets)) if named_targets else 0.0
        coherence = round((0.5 if enabler_present else 0.0) + 0.5 * piece_cov, 2)

        advice: list[str] = []
        if missing:
            advice.append(f"啟動牌指名的角色未入場：{ '、'.join(missing) }，補入後才能完整觸發。")
        if not via_chars:
            advice.append("缺少『以事件技能出場』的角色，Guts 召喚的額外加值無法觸發。")

        return DeckEngine(
            name="Guts速攻引擎",
            summary=(
                "以事件牌把指定角色從 Guts 直接部署到場上（舉球/攻擊區），"
                "達成區域指名後追加加值與壓制效果，形成爆發回合。"
            ),
            role_cards={
                '啟動（事件）':     [c.card_no for c in guts_events],
                '事件部署角色':     [c.card_no for c in via_chars],
                '指名目標（在場）': present,
            },
            coherence=coherence,
            advice=advice,
        )

    def _detect_zone_lock_engine(
        self, deck: list[Card], uniq: list[Card],
    ) -> DeckEngine | None:
        deck_names = {c.name for c in deck}
        pairs: set[tuple[str, str]] = set()
        sources: list[str] = []
        for c in uniq:
            for m in _RE_JOINT_COND.finditer(c.skill_zh):
                a, b = m.group(2), m.group(4)
                key = tuple(sorted((a, b)))
                if key not in pairs:
                    pairs.add(key)
                    sources.append(c.card_no)
        if not pairs:
            return None

        complete = [p for p in pairs if all(n in deck_names for n in p)]
        coherence = round(len(complete) / len(pairs), 2) if pairs else 0.0

        advice: list[str] = []
        for p in pairs:
            missing = [n for n in p if n not in deck_names]
            if missing:
                advice.append(f"區域聯動「{p[0]}＋{p[1]}」缺少：{'、'.join(missing)}。")

        return DeckEngine(
            name="區域聯動引擎",
            summary="兩名指定角色須同時佔據特定功能區（如舉球＋攻擊），才能觸發事件的強效。",
            role_cards={
                '聯動事件': sources,
                '所需配對': ['＋'.join(p) for p in pairs],
            },
            coherence=coherence,
            advice=advice,
        )

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

        # 8a. SYN_EVENT_RECOVER — recover a card from the EVENT ZONE back to hand.
        #     This enables replay loops (e.g. どんぴしゃり Loop via 北信介 P02-024).
        #     Only scored when the deck actually runs a Guts-deploy event to recover.
        if _RE_EVENT_ZONE_RECOVER.search(skill):
            has_loop_target = any(
                c.category == 'EVENT' and _RE_GUTS_REF.search(c.skill_zh)
                for c in deck
            )
            if has_loop_target:
                edges.append(SynergyEdge(card.card_no, '__event_zone__', 'SYN_EVENT_RECOVER',
                                         self.WEIGHTS['SYN_EVENT_RECOVER']))

        # 8b. SYN_ROLE_RECOVER — recover ANY role/school card from the discard pile.
        #     Self-sustaining engine value, independent of which specific card is named.
        if _RE_ROLE_RECOVER.search(skill):
            edges.append(SynergyEdge(card.card_no, '__discard_pool__', 'SYN_ROLE_RECOVER',
                                     self.WEIGHTS['SYN_ROLE_RECOVER']))

        # 8c. SYN_MILL_FUEL — actively feeds the discard pile. Only rewarded when the
        #     deck actually runs a diversity payoff (otherwise milling is pure downside).
        if _RE_MILL_FUEL.search(skill):
            has_payoff = any(_RE_DIVERSE_COND.search(c.skill_zh) for c in deck)
            if has_payoff:
                edges.append(SynergyEdge(card.card_no, '__discard_pool__', 'SYN_MILL_FUEL',
                                         self.WEIGHTS['SYN_MILL_FUEL']))

        # 8d. SYN_CONDITION — diverse discard-pile payoff. Coverage now reflects whether
        #     the deck can REALISTICALLY stock N unique names: it needs both enough unique
        #     character names AND fuel/draw to put them into the pile. A payoff with no
        #     way to fill the pile is a dead condition and scores near zero.
        if _RE_DIVERSE_COND.search(skill):
            threshold = int(_RE_DIVERSE_COND.search(skill).group(1))
            unique_names = len({c.name for c in deck if c.category == 'CHARACTER'})
            name_coverage = min(unique_names / max(threshold, 1), 1.0)
            fuel_cards = sum(
                1 for c in deck
                if _RE_MILL_FUEL.search(c.skill_zh) or '抽' in c.skill_zh
            )
            fuel_coverage = min(fuel_cards / 6, 1.0)   # ~6 fuel/draw sources = reliable
            coverage = name_coverage * (0.4 + 0.6 * fuel_coverage)
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
        for e in by_type.get('SYN_EVENT_RECOVER', [])[:4]:
            chains.append(f"[Event回收] {e.source} 從Event區取回事件牌→Loop（強度 {e.weight:.1f}）")
        for e in by_type.get('SYN_ROLE_RECOVER', [])[:4]:
            chains.append(f"[墓地回收] {e.source} 從棄牌區回收角色（強度 {e.weight:.1f}）")
        if by_type.get('SYN_MILL_FUEL'):
            n = len(by_type['SYN_MILL_FUEL'])
            chains.append(f"[墓地填充] ×{n} 張（餵養種類多樣性引擎）")
        if by_type.get('SYN_CONDITION'):
            chains.append(f"[條件解鎖] ×{len(by_type['SYN_CONDITION'])} 組（種類多樣性觸發）")
        return chains
