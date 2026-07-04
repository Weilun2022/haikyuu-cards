"""
deck_evo/pk_engine.py — PK 競技場引擎
兩副指定牌組 AI 對戰，每場產生 visual replay，可各自啟用「敗方突變」演化。
"""
from __future__ import annotations
import random
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).parent.parent

from game_engine.sim_runner import run_one_game
from game_engine.spectator import Spectator
from game_engine.ai.generic_ai import GenericAI
from game_engine.card_db import get_card
from deck_evo.card_pool import mutate, detect_school

_KEEP_REPLAYS = 60   # visual_replay_pk_* 保留數量


def _card_name(card_no: str) -> str:
    try:
        c = get_card(card_no)
        return c.get("name", card_no) if c else card_no
    except Exception:
        return card_no


def _deck_card_list(deck: dict[str, int]) -> list[dict]:
    lst = [
        {"card_no": cno, "name": _card_name(cno), "count": cnt}
        for cno, cnt in deck.items()
    ]
    lst.sort(key=lambda x: (-x["count"], x["card_no"]))
    return lst


def _deck_diff(old: dict[str, int], new: dict[str, int]) -> list[dict]:
    """回傳異動清單 [{card_no, name, delta}]，delta>0 加入 / <0 移除。"""
    diff = []
    for cno in set(old) | set(new):
        d = new.get(cno, 0) - old.get(cno, 0)
        if d:
            diff.append({"card_no": cno, "name": _card_name(cno), "delta": d})
    diff.sort(key=lambda x: x["delta"], reverse=True)
    return diff


def _cleanup_pk_replays(replays_dir: Path, keep: int = _KEEP_REPLAYS):
    """清理舊 PK replay（visual html + json sidecar + 原始 html）。"""
    try:
        visuals = sorted(replays_dir.glob("visual_replay_pk_*.html"))
        for f in visuals[:-keep] if len(visuals) > keep else []:
            stem = f.stem            # visual_replay_pk_...
            for victim in (f, f.with_suffix(".json"),
                           replays_dir / (stem.removeprefix("visual_") + ".html")):
                try:
                    victim.unlink(missing_ok=True)
                except OSError:
                    pass
    except Exception:
        pass


class PKEngine:
    """
    PK 對戰循環：
      mode="watch" — 每場打完後等待前端 next()（播放完 replay 再開下一場）
      mode="fast"  — 連續對戰不等待，適合大量統計
    演化規則：敗方若啟用 evolve，於該場結束後突變 mutation_swaps 張（鎖定原學校）。
    """

    def __init__(
        self,
        deck1: dict[str, int], deck2: dict[str, int],
        name1: str = "我方", name2: str = "對方",
        evolve1: bool = False, evolve2: bool = False,
        max_games: int = 50, mode: str = "watch",
        mutation_swaps: int = 2,
        on_update: Callable[[dict], None] | None = None,
    ):
        self.deck1 = dict(deck1)
        self.deck2 = dict(deck2)
        self.name1, self.name2 = name1, name2
        self.evolve1, self.evolve2 = evolve1, evolve2
        self.max_games = max(1, int(max_games))
        self.mode = mode if mode in ("watch", "fast") else "watch"
        self.mutation_swaps = mutation_swaps
        self.on_update = on_update

        self.run_id = "pk_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        self.game_no = 0
        self.wins1 = 0
        self.wins2 = 0
        self.history: list[dict] = []      # [{game_no, winner, wr1}]
        self.finished = False

        self._school1 = detect_school(self.deck1)
        self._school2 = detect_school(self.deck2)
        self._stop_event = threading.Event()
        self._next_event = threading.Event()
        self._running = False
        self._replays_dir = ROOT / "replays"
        self._replays_dir.mkdir(parents=True, exist_ok=True)

    # ── 公開 API ──────────────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        self._stop_event.clear()
        _cleanup_pk_replays(self._replays_dir)
        t = threading.Thread(target=self._run_loop, daemon=True)
        t.start()

    def stop(self):
        self._stop_event.set()
        self._next_event.set()   # 喚醒 watch 模式等待

    def next_game(self):
        """watch 模式：前端播放完畢後觸發下一場。"""
        self._next_event.set()

    def status(self) -> dict:
        return self._payload()

    # ── 內部 ─────────────────────────────────────────────────────────────────

    def _run_loop(self):
        self._running = True
        try:
            for i in range(1, self.max_games + 1):
                if self._stop_event.is_set():
                    break
                if self.mode == "watch" and i > 1:
                    # 等待前端 next；每 0.5s 檢查 stop
                    while not self._next_event.wait(timeout=0.5):
                        if self._stop_event.is_set():
                            return
                    self._next_event.clear()
                    if self._stop_event.is_set():
                        break
                self._play_one(i)
        finally:
            self._running = False
            self.finished = True
            self._push()

    def _play_one(self, game_no: int):
        seed = random.randint(0, 999_999)
        html_path = self._replays_dir / f"replay_{self.run_id}_g{game_no:04d}.html"
        spec = Spectator(speed=0, html_out=str(html_path), silent=True)

        result = run_one_game(
            deck1=self.deck1, deck2=self.deck2,
            name1=self.name1, name2=self.name2,
            school1=self._school1, school2=self._school2,
            ai1_class=GenericAI, ai2_class=GenericAI,
            spectator=spec, seed=seed,
        )

        self.game_no = game_no
        winner = result.get("winner")
        if winner == 1:
            self.wins1 += 1
        elif winner == 2:
            self.wins2 += 1

        # 演化：敗方突變（學校鎖定 = 自己原本的主學校）
        diff1 = diff2 = None
        if winner == 2 and self.evolve1:
            new = mutate(self.deck1, n_swaps=self.mutation_swaps,
                         school_lock=self._school1)
            diff1 = _deck_diff(self.deck1, new)
            self.deck1 = new
        if winner == 1 and self.evolve2:
            new = mutate(self.deck2, n_swaps=self.mutation_swaps,
                         school_lock=self._school2)
            diff2 = _deck_diff(self.deck2, new)
            self.deck2 = new

        total = self.wins1 + self.wins2
        self.history.append({
            "game_no": game_no,
            "winner": winner,
            "wr1": round(self.wins1 / total, 4) if total else 0.5,
        })

        self._last = {
            "winner": winner,
            "turns": result.get("turns"),
            "p1_sets": result.get("p1_sets"),
            "p2_sets": result.get("p2_sets"),
            "replay_id": "visual_" + html_path.stem,
            "diff1": diff1,
            "diff2": diff2,
        }
        self._push()

    def _payload(self) -> dict:
        total = self.wins1 + self.wins2
        return {
            "type": "pk_update",
            "run_id": self.run_id,
            "mode": self.mode,
            "running": self._running,
            "finished": self.finished,
            "game_no": self.game_no,
            "max_games": self.max_games,
            "wins1": self.wins1,
            "wins2": self.wins2,
            "win_rate1": round(self.wins1 / total, 4) if total else 0,
            "last": getattr(self, "_last", None),
            "history": self.history[-500:],
            "deck1": {
                "name": self.name1, "school": self._school1,
                "evolve": self.evolve1, "total": sum(self.deck1.values()),
                "card_list": _deck_card_list(self.deck1),
            },
            "deck2": {
                "name": self.name2, "school": self._school2,
                "evolve": self.evolve2, "total": sum(self.deck2.values()),
                "card_list": _deck_card_list(self.deck2),
            },
        }

    def _push(self):
        if self.on_update:
            try:
                self.on_update(self._payload())
            except Exception:
                pass
