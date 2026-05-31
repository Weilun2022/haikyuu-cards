"""Build archetype vs archetype matchup matrix via simulation."""
from dataclasses import dataclass, field
from ..engine.card import Card
from ..simulation.monte_carlo import run_simulation, SimResult
from ..simulation.deck_sampler import build_school_deck
from .archetype_classifier import Archetype, classify_deck

SCHOOL_ARCHETYPE_MAP = {
    '伊達工業': Archetype.DEF,
    '音駒':    Archetype.DEF,
    '稲荷崎':  Archetype.AGG,
    '白鳥沢':  Archetype.AGG,
    '梟谷':    Archetype.COMBO,
    '青葉城西': Archetype.TEMPO,
    '烏野':    Archetype.HYBRID,
}

REPRESENTATIVE_SCHOOLS = {
    Archetype.AGG:     '稲荷崎',
    Archetype.DEF:     '伊達工業',
    Archetype.COMBO:   '梟谷',
    Archetype.TEMPO:   '青葉城西',
    Archetype.CONTROL: '音駒',
    Archetype.HYBRID:  '烏野',
}


@dataclass
class MatchupMatrix:
    archetypes: list[Archetype]
    # win_rates[i][j] = win rate of archetypes[i] vs archetypes[j]
    win_rates: dict[tuple[str, str], float] = field(default_factory=dict)
    n_games: int = 200

    def build(self, n: int = 200):
        self.n_games = n
        for a1 in self.archetypes:
            school1 = REPRESENTATIVE_SCHOOLS.get(a1, '烏野')
            deck1 = build_school_deck(school1)
            for a2 in self.archetypes:
                if a1 == a2:
                    self.win_rates[(a1.value, a2.value)] = 0.5
                    continue
                school2 = REPRESENTATIVE_SCHOOLS.get(a2, '烏野')
                deck2 = build_school_deck(school2)
                result = run_simulation(deck1, deck2, n=n,
                                        deck1_name=a1.value, deck2_name=a2.value)
                self.win_rates[(a1.value, a2.value)] = result.p1_win_rate

    def get_win_rate(self, a1: Archetype, a2: Archetype) -> float:
        return self.win_rates.get((a1.value, a2.value), 0.5)

    def best_counter(self, target: Archetype) -> Archetype:
        others = [a for a in self.archetypes if a != target]
        return max(others, key=lambda a: self.get_win_rate(a, target))

    def tier_ranking(self) -> list[tuple[Archetype, float]]:
        """Rank archetypes by average win rate across all matchups."""
        rankings = []
        for a in self.archetypes:
            others = [x for x in self.archetypes if x != a]
            avg = sum(self.get_win_rate(a, o) for o in others) / len(others) if others else 0.5
            rankings.append((a, avg))
        return sorted(rankings, key=lambda x: x[1], reverse=True)

    def format_table(self) -> str:
        header = f"{'':10}" + "".join(f"{a.value[:4]:>8}" for a in self.archetypes)
        rows = [header, "-" * len(header)]
        for a1 in self.archetypes:
            row = f"{a1.value[:8]:10}"
            for a2 in self.archetypes:
                wr = self.get_win_rate(a1, a2)
                row += f"{wr:>8.0%}"
            rows.append(row)
        return "\n".join(rows)
