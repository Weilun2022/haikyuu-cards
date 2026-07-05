"""Monte Carlo simulation: run N games between two decks and collect statistics."""
import random
import copy
from dataclasses import dataclass, field
from typing import Callable

from ..engine.card import Card
from ..engine.game_state import GameState, PlayerState
from ..engine.skill_engine import SkillEngine
from ..engine.action_resolver import ActionResolver
from ..engine.turn_controller import TurnController
from .ai_player import AIPlayer


@dataclass
class SimResult:
    deck1_name: str
    deck2_name: str
    n_games: int
    p1_wins: int
    p2_wins: int
    avg_turns: float
    avg_p1_score: float
    avg_p2_score: float
    p1_win_rate: float
    skill_activations_p1: float   # avg per game
    skill_activations_p2: float

    def summary(self) -> str:
        return (
            f"{self.deck1_name} vs {self.deck2_name} | N={self.n_games}\n"
            f"  Win rate: {self.deck1_name}={self.p1_win_rate:.1%} | "
            f"{self.deck2_name}={1-self.p1_win_rate:.1%}\n"
            f"  Avg turns: {self.avg_turns:.1f} | "
            f"Avg score: {self.avg_p1_score:.1f}-{self.avg_p2_score:.1f}"
        )


def _make_player(name: str, deck: list[Card], start_guts: int = 3) -> PlayerState:
    d = list(deck)
    random.shuffle(d)
    hand = d[:5]
    remaining = d[5:]
    return PlayerState(
        name=name,
        deck=remaining,
        hand=hand,
        field={'srv': None, 'blk': None, 'rcv': None, 'tos': None, 'atk': None, 'evt': []},
        guts=start_guts,
        score=0,
        discard=[],
        atk_bonus=0, blk_bonus=0, rcv_bonus=0, srv_bonus=0,
        rcv_lock=0, blk_lock=0,
    )


def _run_single_game(
    deck1: list[Card],
    deck2: list[Card],
    max_turns: int = 60,
    seed: int | None = None,
) -> dict:
    if seed is not None:
        random.seed(seed)

    skill_engine = SkillEngine()
    resolver = ActionResolver(skill_engine)
    controller = TurnController(resolver, skill_engine)
    ai = AIPlayer()

    p1 = _make_player("P1", deck1)
    p2 = _make_player("P2", deck2)
    gs = GameState(p1=p1, p2=p2, turn=1, current_player=1, phase='draw', game_log=[])

    skill_acts = {1: 0, 2: 0}

    for _ in range(max_turns):
        if gs.is_terminal():
            break

        acting_player = gs.current_player  # capture before turn_controller switches it
        active = gs.active()
        passive = gs.passive()
        ai_decisions = ai.decide_plays(active, passive)

        result = controller.run_full_turn(gs, ai_decisions)
        # run_end_phase already switches current_player; track against who just acted
        skill_acts[acting_player] += result.get('skills_activated', 0)

    winner = gs.winner() or (1 if gs.p1.score >= gs.p2.score else 2)
    return {
        'winner': winner,
        'turns': gs.turn,
        'p1_score': gs.p1.score,
        'p2_score': gs.p2.score,
        'skill_acts_p1': skill_acts[1],
        'skill_acts_p2': skill_acts[2],
    }


def run_simulation(
    deck1: list[Card],
    deck2: list[Card],
    n: int = 500,
    deck1_name: str = "Deck1",
    deck2_name: str = "Deck2",
) -> SimResult:
    results = [_run_single_game(deck1, deck2, seed=i) for i in range(n)]

    p1_wins = sum(1 for r in results if r['winner'] == 1)
    return SimResult(
        deck1_name=deck1_name,
        deck2_name=deck2_name,
        n_games=n,
        p1_wins=p1_wins,
        p2_wins=n - p1_wins,
        avg_turns=sum(r['turns'] for r in results) / n,
        avg_p1_score=sum(r['p1_score'] for r in results) / n,
        avg_p2_score=sum(r['p2_score'] for r in results) / n,
        p1_win_rate=p1_wins / n,
        skill_activations_p1=sum(r['skill_acts_p1'] for r in results) / n,
        skill_activations_p2=sum(r['skill_acts_p2'] for r in results) / n,
    )
