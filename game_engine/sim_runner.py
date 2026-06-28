"""
game_engine/sim_runner.py — AI 對戰模擬器入口

指令範例:
  # 觀戰模式（終端機即時 + 存 HTML）
  python game_engine/sim_runner.py watch --deck1 ROKUNIN --deck2 STANDARD

  # 批次模擬（無顯示，只統計）
  python game_engine/sim_runner.py sim --deck1 ROKUNIN --deck2 STANDARD --n 1000

  # 快速測試（觀戰但快速，存 HTML）
  python game_engine/sim_runner.py watch --deck1 ROKUNIN --deck2 STANDARD --speed 0.3

  # 列出所有牌組
  python game_engine/sim_runner.py --list
"""
from __future__ import annotations
import argparse
import datetime
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ── 加入 project root 到 path ──────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from game_engine.card_db import load_cards, make_deck
from game_engine.schema import GameState, PlayerState
from game_engine.engine.turn_flow import TurnFlow
from game_engine.effects.registry import EffectRegistry
from game_engine.spectator import Spectator
from game_engine.ai.generic_ai import GenericAI, AggressiveAI, DefensiveAI

_REGISTRY: EffectRegistry | None = None

def _get_registry() -> EffectRegistry | None:
    global _REGISTRY
    if _REGISTRY is None:
        r = EffectRegistry()
        count = r.load_skill_db()
        if count > 0:
            print(f"  [技能資料庫] 載入 {count} 張卡技能")
            _REGISTRY = r
    return _REGISTRY

# ══════════════════════════════════════════════════════════════════════════════
# 內建牌組 (card_no → count)
# ══════════════════════════════════════════════════════════════════════════════

DECKS: dict[str, dict[str, int]] = {
    # ── 稲荷崎 六種類 ───────────────────────────────────────────────────────
    "ROKUNIN": {
        "HV-P02-087": 1, "HV-P02-085": 3, "HV-P02-089": 3,
        "HV-P02-077": 2, "HV-P02-024": 5, "HV-P02-034": 3,
        "HV-P02-032": 1, "HV-P02-035": 3, "HV-PR-049":  1,
        "HV-P02-017": 3, "HV-P02-027": 4, "HV-PR-034":  3,
        "HV-PR-048":  3, "HV-P02-029": 1, "HV-P02-033": 1,
        "HV-P02-022": 3,
    },
    "ROKUNIN_V1": {
        "HV-P02-087": 1, "HV-P02-085": 3, "HV-P02-089": 2, "HV-P03-093": 2,
        "HV-P02-077": 2, "HV-P02-024": 5, "HV-P02-034": 2,
        "HV-P02-032": 1, "HV-P02-035": 3, "HV-PR-049":  1,
        "HV-P02-017": 2, "HV-P02-027": 3, "HV-PR-034":  2,
        "HV-PR-048":  2, "HV-P02-029": 1, "HV-P02-033": 1,
        "HV-P02-022": 2, "HV-P03-045": 3, "HV-P03-041": 2,
    },
    # ── 通用對手牌組（烏野風格，40 張均衡）──────────────────────────────────
    "STANDARD": {
        # 烏野系列牌（實際存在於資料庫的卡號）
        "HV-P01-001": 3, "HV-P01-002": 3, "HV-P01-003": 3, "HV-P01-004": 3,
        "HV-P01-005": 3, "HV-P01-006": 3, "HV-P01-007": 3, "HV-P01-008": 3,
        "HV-P01-009": 3, "HV-P01-010": 3, "HV-P01-011": 3, "HV-P01-012": 3,
        "HV-P01-013": 4,
    },
}

AI_CLASSES = {
    "generic":    GenericAI,
    "aggressive": AggressiveAI,
    "defensive":  DefensiveAI,
}


# ══════════════════════════════════════════════════════════════════════════════
# 模擬統計
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SimStats:
    n_games: int = 0
    p1_wins: int = 0
    p2_wins: int = 0
    draws:   int = 0
    total_turns: int = 0
    p1_total_sets: int = 0
    p2_total_sets: int = 0

    @property
    def p1_win_rate(self) -> float:
        return self.p1_wins / self.n_games if self.n_games else 0

    @property
    def p2_win_rate(self) -> float:
        return self.p2_wins / self.n_games if self.n_games else 0

    @property
    def avg_turns(self) -> float:
        return self.total_turns / self.n_games if self.n_games else 0

    def summary(self, d1: str, d2: str) -> str:
        lines = [
            "",
            "═" * 58,
            f"  {d1} vs {d2}  N={self.n_games:,}",
            "═" * 58,
            f"  P1 勝率: {self.p1_win_rate:.1%}  |  P2 勝率: {self.p2_win_rate:.1%}",
            f"  平均回合數: {self.avg_turns:.1f}",
            f"  平均局數 P1: {self.p1_total_sets/self.n_games:.1f}  "
            f"P2: {self.p2_total_sets/self.n_games:.1f}",
            "═" * 58,
            "",
        ]
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# 一局遊戲
# ══════════════════════════════════════════════════════════════════════════════

def _build_player(name: str, school: str, deck: dict[str, int]) -> PlayerState:
    pile = make_deck(deck)
    return PlayerState(name=name, school=school, pile=pile)


def run_one_game(
    deck1: dict[str, int], deck2: dict[str, int],
    name1: str, name2: str,
    school1: str, school2: str,
    ai1_class, ai2_class,
    spectator: Spectator | None = None,
    seed: int | None = None,
) -> dict:
    if seed is not None:
        random.seed(seed)

    p1 = _build_player(name1, school1, deck1)
    p2 = _build_player(name2, school2, deck2)
    state = GameState(p1=p1, p2=p2)

    spec = spectator or Spectator(speed=0, silent=True)
    registry = _get_registry()
    flow = TurnFlow(spectator=spec, registry=registry)

    ai1 = ai1_class(player_num=1, name=name1)
    ai2 = ai2_class(player_num=2, name=name2)

    winner = flow.run_full_game(state, ai1, ai2)
    total_turns = state.round_num

    # on_game_end 已在 run_full_game 內部呼叫，不重複

    return {
        "winner": winner,
        "turns": total_turns,
        "p1_sets": state.p1.set_score,
        "p2_sets": state.p2.set_score,
    }


def run_simulation(
    deck1_name: str, deck2_name: str,
    ai1_name: str = "generic", ai2_name: str = "generic",
    n: int = 1000,
) -> SimStats:
    deck1 = DECKS[deck1_name]
    deck2 = DECKS[deck2_name]
    ai1_cls = AI_CLASSES[ai1_name]
    ai2_cls = AI_CLASSES[ai2_name]

    stats = SimStats()

    def _run_one(seed: int) -> dict:
        return run_one_game(
            deck1, deck2,
            deck1_name, deck2_name,
            "稲荷崎", "烏野",
            ai1_cls, ai2_cls,
            seed=seed,
        )

    with ThreadPoolExecutor(max_workers=min(8, n)) as ex:
        futures = [ex.submit(_run_one, i) for i in range(n)]
        for i, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            stats.n_games += 1
            if res["winner"] == 1:
                stats.p1_wins += 1
            elif res["winner"] == 2:
                stats.p2_wins += 1
            else:
                stats.draws += 1
            stats.total_turns += res["turns"]
            stats.p1_total_sets += res["p1_sets"]
            stats.p2_total_sets += res["p2_sets"]

            if i % 100 == 0 or i == n:
                print(f"  進度: {i}/{n} ({i/n:.0%}) P1勝率: {stats.p1_wins/stats.n_games:.1%}",
                      end="\r", flush=True)

    print()
    return stats


# ══════════════════════════════════════════════════════════════════════════════
# 公開 API（供 battle_server.py import）
# ══════════════════════════════════════════════════════════════════════════════

def run_battle_from_deck_dicts(
    deck1_cards: dict[str, int],
    deck1_name: str,
    deck2_cards: dict[str, int],
    deck2_name: str,
    ai1_name: str = "generic",
    ai2_name: str = "generic",
    seed: int | None = None,
) -> dict:
    """
    接受兩副牌組 dict 直接跑一局並生成視覺回放 HTML。

    回傳:
        {
            "winner": 1 | 2,
            "turns": int,
            "p1_sets": int,
            "p2_sets": int,
            "replay_path": str,          # 文字版 replay 絕對路徑
            "visual_replay_path": str,   # 視覺版 replay 絕對路徑
        }
    """
    load_cards()
    ai1_cls = AI_CLASSES.get(ai1_name, GenericAI)
    ai2_cls = AI_CLASSES.get(ai2_name, GenericAI)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe1 = deck1_name[:12].replace(" ", "_")
    safe2 = deck2_name[:12].replace(" ", "_")
    html_path = str(ROOT / "replays" / f"replay_{safe1}_vs_{safe2}_{timestamp}.html")

    spec = Spectator(speed=0, html_out=html_path, silent=True)
    result = run_one_game(
        deck1_cards, deck2_cards,
        deck1_name, deck2_name,
        "P1", "P2",
        ai1_cls, ai2_cls,
        spectator=spec,
        seed=seed,
    )

    visual_path = str(ROOT / "replays" / f"visual_replay_{safe1}_vs_{safe2}_{timestamp}.html")
    return {
        "winner":             result["winner"],
        "turns":              result["turns"],
        "p1_sets":            result["p1_sets"],
        "p2_sets":            result["p2_sets"],
        "replay_path":        html_path,
        "visual_replay_path": visual_path,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def cmd_watch(args):
    """觀戰模式：跑 1 局，即時顯示 + 存 HTML。"""
    deck1 = DECKS[args.deck1]
    deck2 = DECKS[args.deck2]
    ai1_cls = AI_CLASSES.get(args.ai1, GenericAI)
    ai2_cls = AI_CLASSES.get(args.ai2, GenericAI)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = str(ROOT / "replays" / f"replay_{args.deck1}_vs_{args.deck2}_{timestamp}.html")

    spec = Spectator(
        speed=args.speed,
        html_out=html_path,
        silent=False,
        verbose=args.verbose,
    )

    result = run_one_game(
        deck1, deck2,
        args.deck1, args.deck2,
        "稲荷崎", "通用",
        ai1_cls, ai2_cls,
        spectator=spec,
        seed=args.seed,
    )
    print(f"\n結果: P{result['winner']} 獲勝 | 回合: {result['turns']} | "
          f"局分 {result['p1_sets']}–{result['p2_sets']}")
    print(f"HTML replay: {html_path}")


def cmd_sim(args):
    """批次模擬模式。"""
    print(f"\n模擬 {args.deck1} vs {args.deck2} × {args.n} 局 ...")
    stats = run_simulation(
        args.deck1, args.deck2,
        args.ai1, args.ai2,
        n=args.n,
    )
    print(stats.summary(args.deck1, args.deck2))

    if args.mirror:
        print(f"\n[鏡像] {args.deck2} vs {args.deck1} × {args.n} 局 ...")
        stats2 = run_simulation(
            args.deck2, args.deck1,
            args.ai2, args.ai1,
            n=args.n,
        )
        print(stats2.summary(args.deck2, args.deck1))


def main():
    ap = argparse.ArgumentParser(description="Haikyuu TCG AI 對戰模擬器")
    ap.add_argument("--list", action="store_true", help="列出所有牌組")
    ap.add_argument("--version", action="store_true", help="顯示版本")

    sub = ap.add_subparsers(dest="command")

    # ── watch 子命令 ────────────────────────────────────────────────────────
    watcher = sub.add_parser("watch", help="觀戰模式（1 局即時顯示 + HTML）")
    watcher.add_argument("--deck1", default="ROKUNIN", choices=list(DECKS))
    watcher.add_argument("--deck2", default="STANDARD", choices=list(DECKS))
    watcher.add_argument("--ai1", default="generic", choices=list(AI_CLASSES))
    watcher.add_argument("--ai2", default="generic", choices=list(AI_CLASSES))
    watcher.add_argument("--speed", type=float, default=0.5, help="每回合暫停秒數")
    watcher.add_argument("--verbose", action="store_true", help="顯示 Guts 等詳細動作")
    watcher.add_argument("--seed", type=int, default=None, help="隨機種子（可重現）")

    # ── sim 子命令 ──────────────────────────────────────────────────────────
    simcmd = sub.add_parser("sim", help="批次模擬（無顯示，只統計）")
    simcmd.add_argument("--deck1", default="ROKUNIN", choices=list(DECKS))
    simcmd.add_argument("--deck2", default="STANDARD", choices=list(DECKS))
    simcmd.add_argument("--ai1", default="generic", choices=list(AI_CLASSES))
    simcmd.add_argument("--ai2", default="generic", choices=list(AI_CLASSES))
    simcmd.add_argument("--n", type=int, default=500, help="模擬局數")
    simcmd.add_argument("--mirror", action="store_true", help="同時跑鏡像對決")

    args = ap.parse_args()

    if args.list or args.version:
        print("Haikyuu TCG 模擬器 v0.1")
        print("\n可用牌組:")
        for name, deck in DECKS.items():
            total = sum(deck.values())
            events = sum(v for k, v in deck.items()
                         if not k.startswith("HV-P0") or "08" in k or "09" in k)
            print(f"  {name:<16} {total} 張")
        print("\n可用 AI:")
        for n in AI_CLASSES:
            print(f"  {n}")
        return

    load_cards()  # 初始化卡片資料庫

    if args.command == "watch":
        cmd_watch(args)
    elif args.command == "sim":
        cmd_sim(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
