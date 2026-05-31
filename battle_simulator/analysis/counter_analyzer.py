"""Analyze counter strategies against a given deck or archetype."""
from dataclasses import dataclass
from ..engine.card import Card
from ..analysis.archetype_classifier import Archetype, classify_deck, ArchetypeProfile
from ..simulation.monte_carlo import run_simulation
from ..simulation.deck_sampler import build_school_deck
from ..data_loader import load_all_cards

COUNTER_ADVICE = {
    Archetype.AGG: {
        'weaknesses': ['高BLK可封鎖強攻', '無法應對高RCV的持久戰'],
        'counter_archetype': Archetype.DEF,
        'counter_schools': ['伊達工業', '音駒'],
        'key_strategy': '部署高BLK角色（BLK 4+），配合RCV穩守，耗盡對手攻擊資源',
        'tech_cards_criteria': lambda c: c.blk >= 4 or c.rcv >= 5,
    },
    Archetype.DEF: {
        'weaknesses': ['低ATK難以主動得分', '依賴對手失誤'],
        'counter_archetype': Archetype.COMBO,
        'counter_schools': ['梟谷', '青葉城西'],
        'key_strategy': '使用連鎖技能繞過防守，配合TOS提升ATK爆發',
        'tech_cards_criteria': lambda c: c.atk >= 3 or (c.tos >= 3 and c.atk >= 2),
    },
    Archetype.COMBO: {
        'weaknesses': ['技能依賴使其不穩定', '手牌消耗大'],
        'counter_archetype': Archetype.CONTROL,
        'counter_schools': ['音駒', '伊達工業'],
        'key_strategy': '干擾技能阻止連鎖觸發，限制對手關鍵角色出場',
        'tech_cards_criteria': lambda c: any(kw in c.skill_zh for kw in ['不能出場', '最多只能']),
    },
    Archetype.TEMPO: {
        'weaknesses': ['中速節奏容易被快攻壓制'],
        'counter_archetype': Archetype.AGG,
        'counter_schools': ['稲荷崎', '白鳥沢'],
        'key_strategy': '高速壓制，在對手資源引擎啟動前搶分',
        'tech_cards_criteria': lambda c: c.srv >= 4 or c.atk >= 3,
    },
    Archetype.CONTROL: {
        'weaknesses': ['Guts消耗大，資源耗盡後無力'],
        'counter_archetype': Archetype.AGG,
        'counter_schools': ['稲荷崎', '白鳥沢'],
        'key_strategy': '大量快速得分消耗對手Guts，在干擾技能發動前搶先7分',
        'tech_cards_criteria': lambda c: c.srv >= 4 or (c.atk >= 3 and c.guts_cost == 0),
    },
    Archetype.HYBRID: {
        'weaknesses': ['全面型但無突出優勢'],
        'counter_archetype': Archetype.CONTROL,
        'counter_schools': ['音駒', '梟谷'],
        'key_strategy': '針對性壓制其最弱維度',
        'tech_cards_criteria': lambda c: c.blk >= 3 and c.atk >= 2,
    },
}


@dataclass
class CounterReport:
    target_archetype: Archetype
    target_school: str
    weaknesses: list[str]
    counter_archetype: Archetype
    counter_schools: list[str]
    key_strategy: str
    recommended_cards: list[Card]    # top tech cards
    simulation_win_rate: float       # counter deck win rate vs target

    def format(self) -> str:
        lines = [
            f"=== 克制分析：對抗 {self.target_archetype.value}（{self.target_school}）===",
            "",
            "【弱點】",
            *[f"  • {w}" for w in self.weaknesses],
            "",
            f"【推薦對策類型】{self.counter_archetype.value}",
            f"【推薦學校】{'、'.join(self.counter_schools)}",
            "",
            f"【核心策略】{self.key_strategy}",
            "",
            "【關鍵技術牌 Top 5】",
        ]
        for i, card in enumerate(self.recommended_cards[:5], 1):
            lines.append(f"  {i}. {card.name} [{card.school}] "
                         f"ATK={card.atk} BLK={card.blk} RCV={card.rcv} SRV={card.srv}")
        lines.append("")
        lines.append(f"【模擬勝率】{self.simulation_win_rate:.1%} "
                     f"（{self.counter_archetype.value} vs {self.target_archetype.value}）")
        return "\n".join(lines)


def analyze_counter(
    target_archetype: Archetype,
    target_school: str = '',
    n_sim: int = 200,
) -> CounterReport:
    advice = COUNTER_ADVICE.get(target_archetype, COUNTER_ADVICE[Archetype.HYBRID])

    all_cards = load_all_cards()
    criteria = advice['tech_cards_criteria']
    tech_cards = [
        Card.from_dict(c) for c in all_cards
        if c['category'] == 'CHARACTER' and criteria(Card.from_dict(c))
    ]
    tech_cards.sort(key=lambda c: c.atk + c.blk + c.rcv + c.srv, reverse=True)

    # Run simulation: counter school vs target school
    counter_school = advice['counter_schools'][0]
    target_sim_school = target_school or advice.get('target_school_fallback', '烏野')

    try:
        counter_deck = build_school_deck(counter_school)
        target_deck = build_school_deck(target_sim_school if target_sim_school else '烏野')
        sim = run_simulation(counter_deck, target_deck, n=n_sim,
                              deck1_name=counter_school, deck2_name=target_sim_school or '烏野')
        win_rate = sim.p1_win_rate
    except Exception:
        win_rate = 0.0

    return CounterReport(
        target_archetype=target_archetype,
        target_school=target_school,
        weaknesses=advice['weaknesses'],
        counter_archetype=advice['counter_archetype'],
        counter_schools=advice['counter_schools'],
        key_strategy=advice['key_strategy'],
        recommended_cards=tech_cards[:10],
        simulation_win_rate=win_rate,
    )
