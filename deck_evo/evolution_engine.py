"""
deck_evo/evolution_engine.py — Evolution Agent Coordinator（牌組進化協調器）
遺傳演算法核心：初始族群 → 評估 → 選擇 → 突變/交叉 → 收斂檢測
"""
from __future__ import annotations
import random
import threading
import time
from typing import Callable
from pathlib import Path
from deck_evo.genome import DeckGenome
from deck_evo.card_pool import mutate, crossover, is_legal
from deck_evo import fitness as sim_agent
from deck_evo.analytics import Analytics
import deck_evo.replay_saver as _replay_saver

# ── 預設配置 ──────────────────────────────────────────────────────────────────
DEFAULT_CFG = {
    "population_size": 16,     # 族群規模
    "elite_count": 3,          # 精英直接保留
    "games_per_eval": 60,      # 每副牌評估局數
    "mutation_swaps": 3,       # 每次突變替換幾張
    "crossover_rate": 0.35,    # 新世代中交叉的比例
    "convergence_window": 6,   # 收斂判斷世代數
    "convergence_delta": 0.005,# 勝率改善閾值
    "max_generations": 200,    # 最多跑幾代
}


class EvoEngine:
    """
    四大 Agent 協調中心：
      - 本身: Evolution Agent（配種/突變/選擇）
      - sim_agent（Simulator Agent）: fitness.evaluate()
      - Analytics: Strategy & Analytics Agent
      - Replay 選擇由呼叫端（evo_server）處理
    """

    def __init__(
        self,
        seed_deck: dict[str, int],
        meta_decks: dict[str, dict],
        cfg: dict | None = None,
        on_generation: Callable[[dict], None] | None = None,
    ):
        self.cfg = {**DEFAULT_CFG, **(cfg or {})}
        self.meta_decks = meta_decks
        self.on_generation = on_generation    # SSE 回調

        self.generation = 0
        self.population: list[DeckGenome] = []
        self.history: list[dict] = []         # 每代最佳勝率紀錄
        self.best: DeckGenome | None = None
        self.analytics = Analytics()
        self._stop_event = threading.Event()
        self._running = False

        # 種子牌組
        self._seed_deck = seed_deck

        # replay 管理
        _rdir = Path(__file__).parent.parent / "replays"
        self._run_id: str = _replay_saver.init_run(_rdir)
        self._replays_dir: Path = _rdir
        self._latest_replay_url: str | None = None

    # ── 公開 API ──────────────────────────────────────────────────────────────

    def start(self):
        """在背景執行緒啟動進化循環。"""
        if self._running:
            return
        self._stop_event.clear()
        t = threading.Thread(target=self._run_loop, daemon=True)
        t.start()

    def stop(self):
        self._stop_event.set()

    @property
    def running(self) -> bool:
        return self._running

    # ── 內部邏輯 ──────────────────────────────────────────────────────────────

    def _run_loop(self):
        self._running = True
        try:
            self._initialize()
            for _ in range(self.cfg["max_generations"]):
                if self._stop_event.is_set():
                    break
                self._evaluate_all()
                self._sort_population()
                self._update_best()
                self.analytics.update(self.population)
                stats = self._gen_stats()
                self.history.append(stats)
                if self.on_generation:
                    self.on_generation(stats)
                if self._check_convergence():
                    break
                self._breed_next_generation()
                # 代末為最佳 genome 產生展示用 showcase replay
                self._save_showcase_replay()
                self.generation += 1
        finally:
            self._running = False

    def _initialize(self):
        """種子牌組 + N-1 個突變版本組成初始族群。"""
        pop_size = self.cfg["population_size"]
        seed = DeckGenome(cards=dict(self._seed_deck), name="seed", generation=0)
        self.population = [seed]
        while len(self.population) < pop_size:
            n_swaps = random.randint(2, 6)
            mutated = mutate(self._seed_deck, n_swaps=n_swaps)
            g = DeckGenome(cards=mutated, name=f"init-{len(self.population)}", generation=0)
            self.population.append(g)

    def _evaluate_all(self):
        """並行評估族群中每副牌組的勝率，再聚合族群層面卡牌貢獻分。"""
        n_games = self.cfg["games_per_eval"]
        for i, genome in enumerate(self.population):
            if genome.is_elite:
                continue  # 精英不重複評估
            seed_base = self.generation * 1000 + i
            result = sim_agent.evaluate(
                genome.cards, self.meta_decks,
                n_games=n_games, seed_base=seed_base,
            )
            genome.win_rate = result["win_rate"]
            genome.games_played += result["total_games"]
            genome.card_scores = result["card_scores"]
            genome.key_replays = result.get("key_games", [])
        self._compute_card_scores()

    def _compute_card_scores(self):
        """
        族群層面卡牌貢獻分：
        某張牌的貢獻分 = 含此牌的牌組平均勝率。
        分數高的牌在突變時被保留；分數低的優先被替換。
        """
        wr_sum: dict[str, float] = {}
        wr_cnt: dict[str, int] = {}
        for g in self.population:
            for cno in g.cards:
                wr_sum[cno] = wr_sum.get(cno, 0.0) + g.win_rate
                wr_cnt[cno] = wr_cnt.get(cno, 0) + 1
        for g in self.population:
            for cno in g.cards:
                cnt = wr_cnt.get(cno, 1)
                g.card_scores[cno] = wr_sum.get(cno, 0.0) / cnt

    def _sort_population(self):
        self.population.sort(key=lambda g: g.win_rate, reverse=True)

    def _update_best(self):
        top = self.population[0]
        if self.best is None or top.win_rate > self.best.win_rate:
            self.best = top.clone()
            self.best.win_rate = top.win_rate
            self.best.card_scores = dict(top.card_scores)

    def _gen_stats(self) -> dict:
        wr_list = [g.win_rate for g in self.population]
        top = self.population[0]
        avg_wr = round(sum(wr_list) / len(wr_list), 4)
        return {
            "generation": self.generation,
            "best_win_rate": round(top.win_rate, 4),
            "avg_win_rate": avg_wr,
            "best_deck": top.to_dict(),
            "analytics": self.analytics.to_dict(),
            "history":     [h["best_win_rate"] for h in self.history] + [round(top.win_rate, 4)],
            "history_avg": [h["avg_win_rate"]  for h in self.history] + [avg_wr],
            "run_id": self._run_id,
            "latest_replay": self._latest_replay_url,
        }

    def _check_convergence(self) -> bool:
        window = self.cfg["convergence_window"]
        delta = self.cfg["convergence_delta"]
        if len(self.history) < window:
            return False
        recent = [h["best_win_rate"] for h in self.history[-window:]]
        return max(recent) - min(recent) < delta

    def _breed_next_generation(self):
        """選擇 → 精英保留 → 突變 + 交叉 填充新世代。"""
        cfg = self.cfg
        elite_n = cfg["elite_count"]
        pop_size = cfg["population_size"]
        n_swaps = cfg["mutation_swaps"]
        cx_rate = cfg["crossover_rate"]

        # 精英直接保留
        elites = self.population[:elite_n]
        for e in elites:
            e.is_elite = True

        new_pop: list[DeckGenome] = list(elites)

        # 交叉子代
        n_cross = int((pop_size - elite_n) * cx_rate)
        for _ in range(n_cross):
            p1, p2 = random.choices(elites + self.population[elite_n:elite_n+4], k=2)
            child_cards = crossover(p1.cards, p2.cards,
                                    p1.card_scores, p2.card_scores)
            g = DeckGenome(cards=child_cards,
                           name=f"cross-{self.generation}",
                           generation=self.generation + 1)
            new_pop.append(g)

        # 突變子代
        while len(new_pop) < pop_size:
            parent = random.choice(self.population[:max(4, elite_n + 2)])
            low = parent.low_score_cards(n=5)
            child_cards = mutate(parent.cards, n_swaps=n_swaps, low_score_cards=low)
            g = DeckGenome(cards=child_cards,
                           name=f"mut-{self.generation}",
                           generation=self.generation + 1)
            new_pop.append(g)

        # 清除精英標記（新一代評估時會重設）
        for g in new_pop[elite_n:]:
            g.is_elite = False

        self.population = new_pop[:pop_size]

    def _save_showcase_replay(self):
        """為當代最佳 genome 產生 1 局精選展示 replay，失敗不中斷 evolution。"""
        try:
            from deck_evo.fitness import run_showcase_replay
            from deck_evo.card_pool import detect_school
            top = self.population[0]
            meta_name, meta_deck = next(iter(self.meta_decks.items()))
            school = detect_school(top.cards)
            out_path = _replay_saver.showcase_path(
                self._replays_dir, self._run_id, self.generation
            )
            result = run_showcase_replay(
                genome_cards=top.cards,
                genome_school=school,
                meta_name=meta_name,
                meta_deck=meta_deck,
                output_path=str(out_path),
                seed=self.generation * 7 + 42,
            )
            if result.get("saved"):
                _replay_saver.cleanup_old_showcases(self._replays_dir)
                self._latest_replay_url = _replay_saver.latest_showcase_url(
                    self._replays_dir, self._run_id
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"showcase replay 失敗: {e}")
