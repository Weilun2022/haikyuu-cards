"""deck_evo/persistence.py — 進化結果持久化（純標準庫 sqlite3）。"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent / "evo_history.db"
_LOCK = threading.Lock()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    with _LOCK:
        with _conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id      TEXT PRIMARY KEY,
                    started_at  REAL,
                    school_lock TEXT,
                    meta_names  TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS generations (
                    run_id          TEXT,
                    generation      INTEGER,
                    best_win_rate   REAL,
                    avg_win_rate    REAL,
                    best_deck_json  TEXT,
                    timestamp       REAL,
                    PRIMARY KEY (run_id, generation)
                )
            """)
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_gen_best ON generations(best_win_rate)"
            )


def start_run(run_id: str, school_lock: str | None, meta_names: list[str]) -> None:
    init_db()
    with _LOCK:
        with _conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO runs(run_id, started_at, school_lock, meta_names) VALUES (?,?,?,?)",
                (run_id, time.time(), str(school_lock), json.dumps(meta_names, ensure_ascii=False)),
            )


def save_generation(run_id: str, gen_stats: dict) -> None:
    """gen_stats 需含: generation, best_win_rate, avg_win_rate, best_deck(dict)。"""
    init_db()
    best_deck = gen_stats.get("best_deck") or {}
    # best_deck 可能是 DeckGenome.to_dict()（含 cards 子鍵）或直接 {card_no: count}
    if isinstance(best_deck, dict) and "cards" in best_deck:
        best_deck = best_deck["cards"]
    with _LOCK:
        with _conn() as c:
            c.execute(
                """INSERT OR REPLACE INTO generations
                   (run_id, generation, best_win_rate, avg_win_rate, best_deck_json, timestamp)
                   VALUES (?,?,?,?,?,?)""",
                (
                    run_id,
                    int(gen_stats.get("generation", 0)),
                    float(gen_stats.get("best_win_rate", 0.0)),
                    float(gen_stats.get("avg_win_rate", 0.0)),
                    json.dumps(best_deck, ensure_ascii=False),
                    time.time(),
                ),
            )


def get_hall_of_fame(limit: int = 20) -> list[dict]:
    """歷史最高勝率 Top-N。"""
    init_db()
    with _LOCK:
        with _conn() as c:
            rows = c.execute(
                """SELECT g.run_id, g.generation, g.best_win_rate, g.avg_win_rate,
                          g.best_deck_json, g.timestamp, r.school_lock, r.meta_names
                   FROM generations g
                   LEFT JOIN runs r ON r.run_id = g.run_id
                   ORDER BY g.best_win_rate DESC, g.timestamp DESC
                   LIMIT ?""",
                (int(limit),),
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_run_history(run_id: str) -> list[dict]:
    """取得某次進化的逐代歷史。"""
    init_db()
    with _LOCK:
        with _conn() as c:
            rows = c.execute(
                """SELECT run_id, generation, best_win_rate, avg_win_rate,
                          best_deck_json, timestamp
                   FROM generations WHERE run_id = ?
                   ORDER BY generation ASC""",
                (run_id,),
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    if "best_deck_json" in d and d["best_deck_json"]:
        try:
            d["best_deck"] = json.loads(d["best_deck_json"])
        except (TypeError, json.JSONDecodeError):
            d["best_deck"] = {}
        del d["best_deck_json"]
    if "meta_names" in d and d["meta_names"]:
        try:
            d["meta_names"] = json.loads(d["meta_names"])
        except (TypeError, json.JSONDecodeError):
            pass
    return d
