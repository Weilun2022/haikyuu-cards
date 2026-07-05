"""Classify decks into competitive archetypes based on stat distribution and skill patterns."""
import re
from enum import Enum
from dataclasses import dataclass
from ..engine.card import Card


class Archetype(str, Enum):
    AGG     = "攻擊型"      # High ATK/SRV, fast scoring
    DEF     = "防守型"      # High BLK/RCV, defensive
    COMBO   = "連鎖型"      # Skill chain combos
    TEMPO   = "資源型"      # High TOS/Guts efficiency
    CONTROL = "干擾型"      # Skill-based opponent disruption
    HYBRID  = "混合型"      # Balanced


@dataclass
class ArchetypeProfile:
    archetype: Archetype
    school: str
    avg_atk: float
    avg_blk: float
    avg_rcv: float
    avg_srv: float
    avg_tos: float
    skill_richness: float    # fraction of cards with skills
    combo_density: float     # fraction with combo-type skill tags
    control_density: float   # fraction with control-type skill tags
    confidence: float        # 0-1 classification confidence


COMBO_TAGS = {'攻擊', '舉球', '接球', '攔網', '抽牌', '登場'}
CONTROL_KEYWORDS = ['不能出場', '最多只能', '禁止', '無法', '封鎖']


def classify_deck(deck: list[Card], school: str = '') -> ArchetypeProfile:
    chars = [c for c in deck if c.category == 'CHARACTER']
    if not chars:
        return ArchetypeProfile(Archetype.HYBRID, school, 0, 0, 0, 0, 0, 0, 0, 0, 0.0)

    n = len(chars)
    avg_atk = sum(c.atk for c in chars) / n
    avg_blk = sum(c.blk for c in chars) / n
    avg_rcv = sum(c.rcv for c in chars) / n
    avg_srv = sum(c.srv for c in chars) / n
    avg_tos = sum(c.tos for c in chars) / n

    skilled = [c for c in chars if c.skill_zh.strip()]
    skill_richness = len(skilled) / n

    combo_count = sum(1 for c in chars if any(t in COMBO_TAGS for t in c.skill_tags) and len(c.skill_tags) >= 2)
    combo_density = combo_count / n

    control_count = sum(1 for c in chars if any(kw in c.skill_zh for kw in CONTROL_KEYWORDS))
    control_density = control_count / n

    # Score each archetype
    scores = {
        Archetype.AGG:     avg_atk * 0.4 + avg_srv * 0.35 - avg_blk * 0.1,
        Archetype.DEF:     avg_blk * 0.45 + avg_rcv * 0.35 - avg_atk * 0.1,
        Archetype.COMBO:   combo_density * 2.0 + skill_richness * 0.5 + avg_tos * 0.2,
        Archetype.TEMPO:   avg_tos * 0.5 + skill_richness * 0.4 + (avg_atk + avg_srv) * 0.15,
        Archetype.CONTROL: control_density * 2.5 + skill_richness * 0.3,
        Archetype.HYBRID:  0.5,  # baseline
    }

    best = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = scores[best] / total if total > 0 else 0.0

    return ArchetypeProfile(
        archetype=best, school=school,
        avg_atk=avg_atk, avg_blk=avg_blk, avg_rcv=avg_rcv,
        avg_srv=avg_srv, avg_tos=avg_tos,
        skill_richness=skill_richness,
        combo_density=combo_density,
        control_density=control_density,
        confidence=confidence,
    )


def describe_archetype(profile: ArchetypeProfile) -> str:
    lines = [
        f"類型: {profile.archetype.value} (信心度 {profile.confidence:.0%})",
        f"學校: {profile.school}",
        f"數值輪廓: ATK={profile.avg_atk:.1f} BLK={profile.avg_blk:.1f} "
        f"RCV={profile.avg_rcv:.1f} SRV={profile.avg_srv:.1f} TOS={profile.avg_tos:.1f}",
        f"技能密度: {profile.skill_richness:.0%} 連鎖={profile.combo_density:.0%} 干擾={profile.control_density:.0%}",
    ]
    return "\n".join(lines)
