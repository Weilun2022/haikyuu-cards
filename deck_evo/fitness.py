"""
deck_evo/fitness.py — Simulator Agent（模擬戰鬥 Agent）
並行執行 AI 對戰，回傳勝率與卡牌貢獻分。
"""
from __future__ import annotations
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from game_engine.sim_runner import run_one_game, _get_registry
from game_engine.card_db import load_cards, make_deck
from game_engine.schema import GameState, PlayerState
from game_engine.engine.turn_flow import TurnFlow
from game_engine.spectator import Spectator
from game_engine.ai.generic_ai import GenericAI
from deck_evo.card_pool import detect_school

META_DECKS: dict[str, dict] = {}   # 由 evo_server 注入
_WORKERS = 8


def _run_tracked(
    genome_cards: dict[str, int],
    genome_school: str,
    meta_deck: dict[str, int],
    meta_name: str,
    seed: int,
    save_replay: str | None = None,
) -> dict:
    """跑一局並回傳詳細結果。"""
    load_cards()
    registry = _get_registry()
    spec = Spectator(speed=0, html_out=save_replay, silent=True)
    flow = TurnFlow(spectator=spec, registry=registry)

    p1 = PlayerState(name="EVOLVED", school=genome_school,
                     pile=make_deck(genome_cards))
    p2 = PlayerState(name=meta_name, school=detect_school(meta_deck),
                     pile=make_deck(meta_deck))
    state = GameState(p1=p1, p2=p2)

    ai1 = GenericAI(player_num=1, name="EVOLVED")
    ai2 = GenericAI(player_num=2, name=meta_name)

    if seed is not None:
        random.seed(seed)
    winner = flow.run_full_game(state, ai1, ai2)

    return {
        "winner": winner,
        "turns": state.round_num,
        "p1_sets": p1.set_score,
        "p2_sets": p2.set_score,
    }


def evaluate(
    genome_cards: dict[str, int],
    meta_decks: dict[str, dict],
    n_games: int = 50,
    seed_base: int = 0,
    save_key_replays: bool = False,
    replays_dir: Path | None = None,
) -> dict:
    """
    並行評估牌組勝率。
    回傳 {win_rate, card_scores, key_games}
    """
    load_cards()
    school = detect_school(genome_cards)
    meta_list = list(meta_decks.items())
    games_per_meta = max(1, n_games // len(meta_list))

    tasks = []
    for meta_name, meta_deck in meta_list:
        for i in range(games_per_meta):
            seed = seed_base * 10000 + hash(meta_name) % 1000 + i
            tasks.append((meta_name, meta_deck, seed))

    wins = 0
    total = 0
    key_games: list[dict] = []

    with ThreadPoolExecutor(max_workers=_WORKERS) as ex:
        futs = {
            ex.submit(_run_tracked, genome_cards, school, meta_deck, meta_name, seed): (meta_name, i)
            for i, (meta_name, meta_deck, seed) in enumerate(tasks)
        }
        for fut in as_completed(futs):
            try:
                res = fut.result()
            except Exception:
                continue
            total += 1
            won = res["winner"] == 1
            if won:
                wins += 1
            # 關鍵對局：結局緊張（局差 ≤ 1）且回合 ≥ 3
            if abs(res["p1_sets"] - res["p2_sets"]) <= 1 and res["turns"] >= 3:
                key_games.append(res)

    win_rate = wins / total if total else 0.0

    # 卡牌初始貢獻分 = 整體勝率（族群層面聚合在 EvoEngine._compute_card_scores() 完成）
    card_scores: dict[str, float] = {cno: win_rate for cno in genome_cards}

    return {
        "win_rate": win_rate,
        "card_scores": card_scores,
        "key_games": key_games[:3],
        "total_games": total,
    }
