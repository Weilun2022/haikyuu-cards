"""
game_engine/spectator.py — 觀戰模組

功能：
  1. 終端機即時彩色輸出（使用 ANSI escape codes，不需要額外套件）
  2. 自動儲存 HTML replay 至 replays/ 目錄

整合方式：
    from game_engine.spectator import Spectator
    spec = Spectator(speed=1.0, html_out="replays/game_001.html")
    spec.on_game_start(p1_name, p2_name, d1_name, d2_name)
    spec.on_turn_start(turn_no, player_num, player_name)
    spec.on_deploy(player_num, card_no, card_name, zone, notes)
    spec.on_skill(player_num, card_no, skill_summary, triggered)
    spec.on_action(player_num, action_type, atk_val, def_val)
    spec.on_set_result(winner_player, p1_sets, p2_sets)
    spec.on_turn_end(p1_board, p2_board)
    spec.on_game_end(winner_player, total_turns)
"""
from __future__ import annotations

import datetime
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── ANSI 顏色碼 ───────────────────────────────────────────────────────────────
_R  = "\033[0m"        # reset
_B  = "\033[1m"        # bold
_DIM= "\033[2m"        # dim
_P1 = "\033[38;5;208m" # P1 orange
_P2 = "\033[38;5;39m"  # P2 blue
_OK = "\033[38;5;82m"  # green (skill triggered)
_NO = "\033[38;5;240m" # grey (skill blocked/missed)
_HL = "\033[38;5;226m" # yellow (highlight score)
_ERR= "\033[38;5;196m" # red (error/important)
_W  = "\033[37m"       # white

# ── 學校顏色對應 ──────────────────────────────────────────────────────────────
SCHOOL_ANSI = {
    "稲荷崎": "\033[38;5;208m",   # orange
    "烏野":   "\033[38;5;231m",   # white
    "音駒":   "\033[38;5;196m",   # red
    "白鳥沢": "\033[38;5;21m",    # royal blue
    "青葉城西": "\033[38;5;28m",  # dark green
    "伊達工業": "\033[38;5;130m", # brown
    "条善寺": "\033[38;5;93m",    # purple
}

def _p_color(player_num: int) -> str:
    return _P1 if player_num == 1 else _P2

def _pname(player_num: int, name: str) -> str:
    c = _p_color(player_num)
    return f"{c}{_B}P{player_num} {name}{_R}"


# ── 事件資料結構 ──────────────────────────────────────────────────────────────

@dataclass
class GameEvent:
    kind: str            # "game_start","turn_start","deploy","skill","action",
                         # "set_result","board_snapshot","game_end","log"
    player: int = 0      # 0=system, 1 or 2
    data: dict = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.datetime.now().strftime("%H:%M:%S.%f")[:12])


@dataclass
class BoardSnapshot:
    """一回合結束後的場地快照（用於終端機顯示和 HTML）。"""
    player: int
    toss:   str | None
    attack: str | None
    receive: str | None
    blocks: list[str]
    serve:  str | None
    hand_count: int
    pile_count: int
    grave_count: int
    unique_grave: int     # 六種類計數
    atk_bonus: int = 0
    rcv_bonus: int = 0
    blk_bonus: int = 0
    tos_bonus: int = 0
    srv_bonus: int = 0
    set_score: int = 0
    set_cards: int = 2


# ── 主要 Spectator 類別 ───────────────────────────────────────────────────────

class Spectator:
    def __init__(
        self,
        speed: float = 1.0,          # 每回合暫停秒數（0=不暫停）
        html_out: str | None = None, # HTML 輸出路徑
        silent: bool = False,        # 不輸出終端機（只存 HTML）
        verbose: bool = False,       # 更詳細的 debug 輸出
    ) -> None:
        self.speed = speed
        self.html_out = html_out
        self.silent = silent
        self.verbose = verbose
        self._events: list[GameEvent] = []
        self._turn_no = 0
        self._p1_name = "P1"
        self._p2_name = "P2"
        self._d1_name = ""
        self._d2_name = ""
        self._p1_sets = 0
        self._p2_sets = 0

    # ── 事件 API ─────────────────────────────────────────────────────────────

    def on_game_start(
        self,
        p1_name: str, p2_name: str,
        d1_name: str = "", d2_name: str = "",
    ) -> None:
        self._p1_name = p1_name
        self._p2_name = p2_name
        self._d1_name = d1_name
        self._d2_name = d2_name
        ev = GameEvent("game_start", data={
            "p1": p1_name, "p2": p2_name,
            "d1": d1_name, "d2": d2_name,
        })
        self._events.append(ev)
        if not self.silent:
            self._print_game_start(p1_name, p2_name, d1_name, d2_name)

    def on_turn_start(self, turn_no: int, player_num: int, player_name: str) -> None:
        self._turn_no = turn_no
        ev = GameEvent("turn_start", player=player_num,
                       data={"turn": turn_no, "name": player_name})
        self._events.append(ev)
        if not self.silent:
            self._print_turn_header(turn_no, player_num, player_name)
        if self.speed > 0:
            time.sleep(self.speed * 0.3)

    def on_draw(self, player_num: int, card_no: str, card_name: str) -> None:
        ev = GameEvent("draw", player=player_num,
                       data={"card_no": card_no, "card_name": card_name})
        self._events.append(ev)
        if not self.silent and self.verbose:
            c = _p_color(player_num)
            print(f"  {c}抽牌{_R}: {card_name} ({card_no})")

    def on_deploy(
        self,
        player_num: int,
        card_no: str,
        card_name: str,
        zone: str,
        stats: dict | None = None,
        notes: str = "",
    ) -> None:
        ev = GameEvent("deploy", player=player_num,
                       data={"card_no": card_no, "card_name": card_name,
                             "zone": zone, "stats": stats or {}, "notes": notes})
        self._events.append(ev)
        if not self.silent:
            c = _p_color(player_num)
            stat_str = ""
            if stats:
                parts = []
                for k, v in stats.items():
                    if v:
                        parts.append(f"{k.upper()}:{v}")
                if parts:
                    stat_str = f" [{' '.join(parts)}]"
            note_str = f" {_DIM}← {notes}{_R}" if notes else ""
            print(f"  {c}▶ 出場{_R}: {_B}{card_name}{_R}{stat_str} → {zone}{note_str}")

    def on_skill(
        self,
        player_num: int,
        card_no: str,
        skill_summary: str,
        triggered: bool,
        reason_blocked: str = "",
    ) -> None:
        ev = GameEvent("skill", player=player_num,
                       data={"card_no": card_no, "summary": skill_summary,
                             "triggered": triggered, "blocked": reason_blocked})
        self._events.append(ev)
        if not self.silent:
            if triggered:
                print(f"    {_OK}✓ 技能{_R}: {skill_summary}")
            else:
                reason = f" ({reason_blocked})" if reason_blocked else ""
                print(f"    {_NO}✗ 技能未觸發{reason}{_R}: {_DIM}{skill_summary}{_R}")

    def on_guts(self, player_num: int, zone: str, card_no: str, card_name: str) -> None:
        ev = GameEvent("guts", player=player_num,
                       data={"zone": zone, "card_no": card_no, "card_name": card_name})
        self._events.append(ev)
        if not self.silent and self.verbose:
            c = _p_color(player_num)
            print(f"  {c}{_DIM}Guts{_R}: {card_name} → {zone} Guts 池")

    def on_action(
        self,
        actor_player: int,
        action_type: str,         # "attack","receive","serve","block","toss"
        p1_score: int = 0,
        p2_score: int = 0,
        notes: str = "",
    ) -> None:
        ev = GameEvent("action", player=actor_player,
                       data={"action": action_type,
                             "p1_score": p1_score, "p2_score": p2_score,
                             "notes": notes})
        self._events.append(ev)
        if not self.silent:
            self._print_action(actor_player, action_type, p1_score, p2_score, notes)

    def on_set_result(
        self, winner_player: int, p1_sets: int, p2_sets: int
    ) -> None:
        self._p1_sets = p1_sets
        self._p2_sets = p2_sets
        ev = GameEvent("set_result",
                       data={"winner": winner_player, "p1_sets": p1_sets, "p2_sets": p2_sets})
        self._events.append(ev)
        if not self.silent:
            self._print_set_result(winner_player, p1_sets, p2_sets)
        if self.speed > 0:
            time.sleep(self.speed * 0.8)

    def on_board_snapshot(self, snap: BoardSnapshot) -> None:
        ev = GameEvent("board_snapshot", player=snap.player,
                       data=snap.__dict__.copy())
        self._events.append(ev)
        if not self.silent:
            self._print_board(snap)

    def on_log(self, player_num: int, message: str) -> None:
        ev = GameEvent("log", player=player_num, data={"msg": message})
        self._events.append(ev)
        if not self.silent and self.verbose:
            c = _p_color(player_num) if player_num else _DIM
            print(f"  {c}{_DIM}[log]{_R} {message}")

    def on_phase(self, player_num: int, phase_name: str) -> None:
        phase_zh = {
            "serve": "發球", "block": "攔網", "receive": "接球",
            "toss": "舉球", "attack": "攻擊", "start": "START",
        }.get(phase_name, phase_name)
        ev = GameEvent("phase", player=player_num,
                       data={"phase": phase_name, "phase_zh": phase_zh})
        self._events.append(ev)
        if not self.silent:
            c = _p_color(player_num)
            print(f"  {c}〔{phase_zh}階段〕{_R}")

    def on_judge(
        self, player_num: int, phase: str, dp: int, op: int, did_lose: bool
    ) -> None:
        ev = GameEvent("judge", player=player_num,
                       data={"phase": phase, "dp": dp, "op": op, "lost": did_lose})
        self._events.append(ev)
        if not self.silent:
            result = f"{_ERR}失敗！LOST →{_R}" if did_lose else f"{_OK}成功！{_R}"
            print(f"    判定 DP={dp} vs OP={op}  {result}")

    def on_lost(self, loser_num: int, set_cards_remaining: int) -> None:
        ev = GameEvent("lost", player=loser_num,
                       data={"set_cards": set_cards_remaining})
        self._events.append(ev)
        if not self.silent:
            c = _p_color(loser_num)
            w_name = self._p1_name if loser_num == 1 else self._p2_name
            if set_cards_remaining == 0:
                print(f"\n  {_ERR}{_B}☠ P{loser_num} {w_name} LOST！SET ZONE 0 枚 → 敗北！{_R}")
            else:
                print(f"\n  {c}● P{loser_num} {w_name} LOST（SET ZONE 剩 {set_cards_remaining} 枚）{_R}")

    def on_interval(
        self, winner_num: int, p1_sets: int, p2_sets: int
    ) -> None:
        ev = GameEvent("interval", player=winner_num,
                       data={"p1_sets": p1_sets, "p2_sets": p2_sets})
        self._events.append(ev)
        if not self.silent:
            c = _p_color(winner_num)
            w_name = self._p1_name if winner_num == 1 else self._p2_name
            print(f"\n  {c}── INTERVAL：P{winner_num} {w_name} 獲得發球權 ──{_R}")
        if self.speed > 0:
            time.sleep(self.speed * 0.6)

    def on_game_end(self, winner_player: int, total_turns: int) -> None:
        ev = GameEvent("game_end",
                       data={"winner": winner_player, "total_turns": total_turns,
                             "p1_sets": self._p1_sets, "p2_sets": self._p2_sets})
        self._events.append(ev)
        if not self.silent:
            self._print_game_end(winner_player, total_turns)
        if self.html_out:
            self._save_html()

    # ── 終端機輸出函式 ────────────────────────────────────────────────────────

    def _print_game_start(self, p1: str, p2: str, d1: str, d2: str) -> None:
        w = 60
        print()
        print(f"{_B}{'═'*w}{_R}")
        line1 = f"  {_P1}{_B}P1 {p1}{_R}"
        if d1: line1 += f" {_DIM}[{d1}]{_R}"
        line2 = f"    VS"
        line3 = f"  {_P2}{_B}P2 {p2}{_R}"
        if d2: line3 += f" {_DIM}[{d2}]{_R}"
        print(line1)
        print(line2)
        print(line3)
        print(f"{_B}{'═'*w}{_R}")
        print()

    def _print_turn_header(self, turn: int, player: int, name: str) -> None:
        c = _p_color(player)
        bar = "─" * 56
        score = f"  {_HL}局分: {self._p1_sets}–{self._p2_sets}{_R}"
        print(f"\n{c}{bar}{_R}")
        print(f"{c}Turn {turn:>3} │ P{player} {name}{_R}{score}")
        print(f"{c}{bar}{_R}")

    def _print_action(
        self, actor: int, action: str,
        p1_score: int, p2_score: int, notes: str,
    ) -> None:
        c = _p_color(actor)
        action_zh = {
            "attack": "攻擊", "serve": "發球", "receive": "接球",
            "block": "攔網", "toss": "舉球",
        }.get(action, action)

        # P1 vs P2 in the relevant phase
        if actor == 1:
            atk_s, def_s = p1_score, p2_score
            atk_label = f"{_P1}P1 ATK{_R}"
            def_label = f"{_P2}P2 DEF{_R}"
        else:
            atk_s, def_s = p2_score, p1_score
            atk_label = f"{_P2}P2 ATK{_R}"
            def_label = f"{_P1}P1 DEF{_R}"

        result = f"{_OK}攻擊成功 →{_R}" if atk_s > def_s else (
                 f"{_ERR}守備成功 →{_R}" if def_s > atk_s else
                 f"{_HL}平局{_R}")

        print(f"\n  {c}⚡ {action_zh}階段{_R}  {atk_label}:{_B}{atk_s}{_R} vs {def_label}:{_B}{def_s}{_R}  {result}")
        if notes:
            print(f"  {_DIM}{notes}{_R}")

    def _print_set_result(
        self, winner: int, p1_sets: int, p2_sets: int
    ) -> None:
        c = _p_color(winner)
        w_name = self._p1_name if winner == 1 else self._p2_name
        print(f"\n  {_HL}{'★'*5} P{winner} {w_name} 得分！局分 {p1_sets}–{p2_sets} {'★'*5}{_R}")

    def _print_board(self, snap: BoardSnapshot) -> None:
        c = _p_color(snap.player)
        name = self._p1_name if snap.player == 1 else self._p2_name

        def _slot(card: str | None, bonus: int = 0) -> str:
            if card is None:
                return f"{_DIM}（空）{_R}"
            b = f"{_OK}+{bonus}{_R}" if bonus > 0 else ""
            return f"{_B}{card}{_R}{b}"

        blocks_str = ", ".join(
            _slot(b) for b in snap.blocks if b
        ) or f"{_DIM}（空）{_R}"

        grave_str = f"棄牌:{snap.grave_count}張 {_DIM}({snap.unique_grave}/6種類){_R}"
        hand_str  = f"手牌:{snap.hand_count}張 | 牌庫:{snap.pile_count}張"
        set_str   = f"SET:{snap.set_cards} 剩"

        print(f"  {c}場地 P{snap.player} {name}{_R} {_DIM}{set_str}{_R}")
        print(f"    發球: {_slot(snap.serve,  snap.srv_bonus)}")
        print(f"    舉球: {_slot(snap.toss,   snap.tos_bonus)}")
        print(f"    攻擊: {_slot(snap.attack, snap.atk_bonus)}")
        print(f"    接球: {_slot(snap.receive,snap.rcv_bonus)}")
        print(f"    攔網: {blocks_str}")
        print(f"    {hand_str}  {grave_str}")

    def _print_game_end(self, winner: int, total_turns: int) -> None:
        c = _p_color(winner)
        w_name = self._p1_name if winner == 1 else self._p2_name
        print()
        print(f"{_B}{'═'*60}{_R}")
        print(f"{c}{_B}  ▶ 遊戲結束！P{winner} {w_name} 獲勝{_R}")
        print(f"  最終局分: {_HL}{self._p1_sets}–{self._p2_sets}{_R} | 共 {total_turns} 回合")
        if self.html_out:
            print(f"  HTML replay 已儲存: {self.html_out}")
        print(f"{_B}{'═'*60}{_R}\n")

    # ── HTML Replay 生成 ──────────────────────────────────────────────────────

    def _save_html(self) -> None:
        if not self.html_out:
            return
        path = Path(self.html_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        html = self._build_html()
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    def _build_html(self) -> str:
        events_json = json.dumps(self._events, default=lambda o: o.__dict__,
                                 ensure_ascii=False, indent=2)
        d1 = self._d1_name or "deck"
        d2 = self._d2_name or "deck"
        title = "P1 " + self._p1_name + "[" + d1 + "] vs P2 " + self._p2_name + "[" + d2 + "]"

        # ── 字串拼接避免 f-string 與 JS 大括號衝突 ──────────────────────────
        head = (
            '<!DOCTYPE html>\n<html lang="zh-TW">\n<head>\n'
            '<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<title>🏐 ' + title + '</title>\n'
        )

        css = """<style>
:root{--p1:#f97316;--p2:#38bdf8;--ok:#4ade80;--err:#f87171;
      --bg:#0f172a;--surface:#1e293b;--border:#334155;
      --text:#e2e8f0;--dim:#64748b;--hl:#fbbf24;}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'SF Mono',monospace;background:var(--bg);color:var(--text);padding:12px;max-width:1100px;margin:0 auto;}
.p1c{color:var(--p1);font-weight:bold;} .p2c{color:var(--p2);font-weight:bold;}
.ok{color:var(--ok);} .err{color:var(--err);} .hl{color:var(--hl);}
.dim{color:var(--dim);}

/* ── Mode bar ── */
.mode-bar{display:flex;gap:8px;margin:10px 0 14px;}
.mode-btn{padding:7px 20px;border-radius:8px;border:1px solid var(--border);
          background:transparent;color:var(--text);cursor:pointer;font-size:.85rem;}
.mode-btn.active{background:var(--p1);color:#000;border-color:var(--p1);}

/* ── Shared score header ── */
.score-header{display:flex;gap:12px;align-items:center;background:var(--surface);
              padding:10px 16px;border-radius:8px;margin-bottom:12px;}
.score-sets{color:var(--hl);font-size:1.4rem;font-weight:bold;}

/* ══ STEP VIEW ══ */
#step-view{}
.boards-row{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;}
.board{background:var(--surface);border-radius:10px;padding:14px;border:1px solid var(--border);}
.board-hdr{font-weight:bold;font-size:.9rem;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;}
.sz{display:flex;justify-content:space-between;align-items:center;
    padding:5px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:.84rem;min-height:30px;}
.sz:last-of-type{border-bottom:none;}
.sz-lbl{color:var(--dim);font-size:.75rem;width:38px;flex-shrink:0;}
.sz-val{font-weight:bold;text-align:right;flex:1;}
.sz-val.empty{color:var(--dim);font-weight:normal;}
.sz-highlight{color:var(--hl) !important;font-weight:bold;}
.sz-stats{font-size:.72rem;color:var(--dim);margin-top:8px;display:flex;gap:8px;}

/* Event description box */
.step-event{background:var(--surface);border-radius:10px;padding:20px 24px;
            min-height:90px;border:1px solid var(--border);margin-bottom:10px;}
.ev-title{font-size:1.25rem;font-weight:bold;margin-bottom:6px;line-height:1.4;}
.ev-card{font-size:1.05rem;font-weight:bold;color:var(--hl);margin-bottom:4px;}
.ev-stat{font-size:.82rem;color:var(--dim);margin-bottom:6px;}
.ev-sub{font-size:.9rem;color:var(--dim);line-height:1.5;}
.ev-judge{font-size:1.15rem;font-weight:bold;margin:8px 0;}

/* History chips */
.step-history{display:flex;gap:3px;overflow-x:auto;padding:4px 0;
              flex-wrap:wrap;max-height:76px;margin-bottom:8px;}
.chip{width:28px;height:28px;border-radius:6px;display:flex;align-items:center;
      justify-content:center;font-size:.78rem;cursor:pointer;
      border:1px solid var(--border);background:var(--surface);flex-shrink:0;
      transition:transform .1s;}
.chip:hover{border-color:var(--hl);transform:scale(1.1);}
.chip.active{background:var(--hl);color:#000;border-color:var(--hl);}
.chip.cp1{border-color:rgba(249,115,22,.5);}
.chip.cp2{border-color:rgba(56,189,248,.5);}

/* Navigation */
.step-nav{display:flex;gap:8px;align-items:center;flex-wrap:wrap;}
.nav-btn{padding:8px 16px;border-radius:7px;border:1px solid var(--border);
         background:transparent;color:var(--text);cursor:pointer;font-size:.83rem;}
.nav-btn:hover{background:var(--surface);}
.nav-btn.primary{background:var(--hl);color:#000;border-color:var(--hl);font-weight:bold;}
.nav-btn:disabled{opacity:.3;cursor:default;}
#step-counter{color:var(--dim);font-size:.83rem;min-width:60px;text-align:center;}
.step-prog{height:4px;background:var(--border);border-radius:2px;flex:1;min-width:60px;}
.step-prog-bar{height:100%;background:var(--hl);border-radius:2px;transition:width .15s;}
.kbd-hint{color:var(--dim);font-size:.72rem;margin-left:4px;}

/* SET dots */
.set-dot{font-size:.9rem;}
.set-dot.filled{color:var(--hl);}
.set-dot.empty{color:var(--dim);}

/* ══ LOG VIEW ══ */
#log-view{display:none;}
.filter-bar{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;}
.filter-btn{padding:4px 12px;border-radius:999px;border:1px solid var(--border);
            background:transparent;color:var(--text);cursor:pointer;font-size:.8rem;}
.filter-btn.active{background:var(--hl);color:#000;border-color:var(--hl);}
.events{display:flex;flex-direction:column;gap:4px;}
.ev{border-radius:6px;padding:6px 12px;border-left:3px solid var(--border);
    font-size:.82rem;line-height:1.6;cursor:pointer;}
.ev:hover{background:var(--surface);}
.ev.phase{border-color:#6366f1;color:#a5b4fc;font-size:.8rem;}
.ev.deploy{border-color:#8b5cf6;}
.ev.judge{border-color:#0ea5e9;font-size:.82rem;}
.ev.action{border-color:var(--hl);background:rgba(30,41,59,.5);}
.ev.lost{border-color:var(--err);background:rgba(248,113,113,.08);font-weight:bold;}
.ev.set_result{border-color:var(--hl);background:rgba(251,191,36,.1);font-size:1rem;font-weight:bold;text-align:center;}
.ev.game_end{border-color:var(--ok);background:rgba(74,222,128,.1);font-size:1.1rem;font-weight:bold;text-align:center;}
.ev.interval{border-color:var(--dim);background:rgba(30,41,59,.9);font-style:italic;}
.ev.board_snapshot{border-color:var(--border);font-size:.78rem;color:var(--dim);}
.ev.draw{border-color:#334155;font-size:.78rem;color:var(--dim);}
.ts{color:var(--dim);font-size:.72rem;float:right;}
</style>
"""

        body_html = """</head>
<body>

<!-- ── Shared header ── -->
<div class="score-header">
  <span class="p1c" id="p1label">P1</span>
  <span class="score-sets" id="final-score">0–0</span>
  <span class="dim">vs</span>
  <span class="p2c" id="p2label">P2</span>
</div>
<div class="mode-bar">
  <button class="mode-btn active" data-mode="step" onclick="setMode('step')">▶ 步驟回放</button>
  <button class="mode-btn" data-mode="log" onclick="setMode('log')">📋 事件記錄</button>
</div>

<!-- ══ STEP VIEW ══ -->
<div id="step-view">
  <div class="boards-row">
    <div class="board" id="board1"></div>
    <div class="board" id="board2"></div>
  </div>
  <div class="step-event" id="step-event"><div class="ev-sub dim">載入中...</div></div>
  <div class="step-history" id="step-history"></div>
  <div class="step-nav">
    <button class="nav-btn" id="btn-prev" onclick="goTo(SI-1)">◀ Prev</button>
    <span id="step-counter">–</span>
    <button class="nav-btn primary" id="btn-next" onclick="goTo(SI+1)">Next ▶</button>
    <button class="nav-btn" onclick="jumpTo('lost')">→ LOST</button>
    <button class="nav-btn" onclick="jumpTo('set_result')">→ 局</button>
    <button class="nav-btn" onclick="goTo(STEPS.length-1)">⏭ 終局</button>
    <div class="step-prog"><div class="step-prog-bar" id="step-prog-bar"></div></div>
    <span class="kbd-hint">鍵盤 ← →</span>
  </div>
</div>

<!-- ══ LOG VIEW ══ -->
<div id="log-view">
  <div class="filter-bar">
    <button class="filter-btn active" onclick="filterEvs('all')">全部</button>
    <button class="filter-btn" onclick="filterEvs('phase')">階段</button>
    <button class="filter-btn" onclick="filterEvs('deploy')">出場</button>
    <button class="filter-btn" onclick="filterEvs('judge')">判定</button>
    <button class="filter-btn" onclick="filterEvs('action')">OP/DP</button>
    <button class="filter-btn" onclick="filterEvs('lost')">LOST</button>
    <button class="filter-btn" onclick="filterEvs('set_result')">得分</button>
  </div>
  <div class="events" id="events"></div>
</div>

<script>
const RAW = """

        script_tail = """;

// ─────────────────────────────────────────────────────
// Shared init
// ─────────────────────────────────────────────────────
const _gs = RAW.find(e=>e.kind==='game_start');
const P1NAME = _gs ? _gs.data.p1 : 'P1';
const P2NAME = _gs ? _gs.data.p2 : 'P2';
const D1NAME = _gs ? (_gs.data.d1||'') : '';
const D2NAME = _gs ? (_gs.data.d2||'') : '';
const _ge = [...RAW].reverse().find(e=>e.kind==='game_end');

document.getElementById('p1label').textContent = 'P1 '+P1NAME+(D1NAME?' ['+D1NAME+']':'');
document.getElementById('p2label').textContent = 'P2 '+P2NAME+(D2NAME?' ['+D2NAME+']':'');
if (_ge) document.getElementById('final-score').textContent = _ge.data.p1_sets+'–'+_ge.data.p2_sets;

function setMode(m) {
  document.getElementById('step-view').style.display  = m==='step' ? '' : 'none';
  document.getElementById('log-view').style.display   = m==='log'  ? '' : 'none';
  document.querySelectorAll('.mode-btn').forEach(b=>{
    b.classList.toggle('active', b.dataset.mode===m);
  });
  if (m==='step') renderStep();
}

// ─────────────────────────────────────────────────────
// ══ STEP VIEWER ══
// ─────────────────────────────────────────────────────

function buildSteps() {
  const SKIP = new Set(['board_snapshot','log','turn_start','guts']);
  const steps = [];
  const EMPTY = () => ({serve:null,toss:null,attack:null,receive:null,blocks:[],
                         hand_count:6,pile_count:34,grave_count:0,
                         set_score:0,set_cards:2,unique_grave:0});
  const b = {1:EMPTY(), 2:EMPTY()};
  let lastDeploy = null; // {player, zone, card_name}

  for (const ev of RAW) {
    if (ev.kind === 'board_snapshot') {
      const d = ev.data, pn = ev.player;
      Object.assign(b[pn], {
        serve:d.serve, toss:d.toss, attack:d.attack, receive:d.receive,
        blocks:d.blocks||[], hand_count:d.hand_count, pile_count:d.pile_count,
        grave_count:d.grave_count, set_score:d.set_score, set_cards:d.set_cards,
        unique_grave:d.unique_grave
      });
      if (steps.length > 0) {
        steps[steps.length-1].b1 = JSON.parse(JSON.stringify(b[1]));
        steps[steps.length-1].b2 = JSON.parse(JSON.stringify(b[2]));
      }
      continue;
    }
    if (SKIP.has(ev.kind)) continue;

    // Update zone/stats immediately for real-time board display
    if (ev.kind === 'deploy') {
      const pn = ev.player, z = ev.data.zone;
      if (z === 'block') {
        b[pn].blocks = [...(b[pn].blocks||[]), ev.data.card_name].slice(-3);
      } else if (['serve','toss','attack','receive'].includes(z)) {
        b[pn][z] = ev.data.card_name;
      }
      b[pn].hand_count = Math.max(0, (b[pn].hand_count||0) - 1);
      lastDeploy = {player:pn, zone:z, card:ev.data.card_name};
    }
    if (ev.kind === 'draw') {
      const pn = ev.player;
      b[pn].hand_count = (b[pn].hand_count||0) + 1;
      b[pn].pile_count = Math.max(0, (b[pn].pile_count||0) - 1);
    }
    if (ev.kind === 'lost') b[ev.player].set_cards = ev.data.set_cards;
    if (ev.kind === 'set_result') { b[1].set_score=ev.data.p1_sets; b[2].set_score=ev.data.p2_sets; }

    steps.push({
      ev,
      b1: JSON.parse(JSON.stringify(b[1])),
      b2: JSON.parse(JSON.stringify(b[2])),
      highlight: (ev.kind==='deploy' && lastDeploy) ? {...lastDeploy} : null
    });
    if (ev.kind !== 'deploy') lastDeploy = null;
  }
  return steps;
}

const STEPS = buildSteps();
let SI = 0;

function goTo(i) {
  SI = Math.max(0, Math.min(STEPS.length-1, i));
  renderStep();
}

function jumpTo(kind) {
  for (let i=SI+1; i<STEPS.length; i++) {
    if (STEPS[i].ev.kind===kind) { goTo(i); return; }
  }
  // wrap around
  for (let i=0; i<SI; i++) {
    if (STEPS[i].ev.kind===kind) { goTo(i); return; }
  }
}

function renderStep() {
  if (!STEPS.length) return;
  const s = STEPS[SI];
  renderBoard('board1', s.b1, 1, s.highlight);
  renderBoard('board2', s.b2, 2, s.highlight);
  document.getElementById('step-event').innerHTML = describeStep(s);
  document.getElementById('step-counter').textContent = (SI+1)+' / '+STEPS.length;
  const pct = ((SI+1)/STEPS.length*100).toFixed(1)+'%';
  document.getElementById('step-prog-bar').style.width = pct;
  document.getElementById('btn-prev').disabled = (SI===0);
  document.getElementById('btn-next').disabled = (SI===STEPS.length-1);
  renderHistory();
  // Scroll current chip into view
  setTimeout(()=>{
    const chip = document.querySelector('.chip.active');
    if (chip) chip.scrollIntoView({block:'nearest',behavior:'smooth'});
  }, 50);
}

function setDots(n) {
  let s = '';
  for (let i=0;i<2;i++) s += '<span class="set-dot '+(i<n?'filled':'empty')+'">●</span>';
  return s;
}

function renderBoard(id, b, pnum, highlight) {
  const el = document.getElementById(id);
  if (!el) return;
  const pc = pnum===1 ? 'p1c' : 'p2c';
  const col = pnum===1 ? 'var(--p1)' : 'var(--p2)';
  const name = pnum===1 ? P1NAME : P2NAME;

  const zrow = (lbl, card, zone) => {
    const isHl = highlight && highlight.player===pnum && highlight.zone===zone && highlight.card===card;
    const cls = card ? (isHl ? 'sz-val sz-highlight' : 'sz-val') : 'sz-val empty';
    return '<div class="sz"><span class="sz-lbl">'+lbl+'</span>'
         + '<span class="'+cls+'">'+(card||'—')+'</span></div>';
  };

  const blocks = (b.blocks||[]).filter(Boolean);
  const blkHl = highlight && highlight.player===pnum && highlight.zone==='block';
  const blkCls = blkHl ? 'sz-val sz-highlight' : (blocks.length ? 'sz-val' : 'sz-val empty');
  const blkTxt = blocks.length ? blocks.join(' / ') : '—';

  el.innerHTML =
    '<div class="board-hdr"><span class="'+pc+'">'+name+'</span>'
    + '<span>'+setDots(b.set_cards||0)+'</span></div>'
    + zrow('発球',b.serve,'serve')
    + zrow('接球',b.receive,'receive')
    + zrow('舉球',b.toss,'toss')
    + zrow('攻擊',b.attack,'attack')
    + '<div class="sz"><span class="sz-lbl">攔網</span><span class="'+blkCls+'">'+blkTxt+'</span></div>'
    + '<div class="sz-stats">'
    + '<span>手:'+b.hand_count+'</span>'
    + '<span>庫:'+b.pile_count+'</span>'
    + '<span>棄:'+b.grave_count+'</span>'
    + '<span style="color:'+col+'">局'+b.set_score+'</span>'
    + '</div>';
}

const PHASE_ZH = {serve:'⬆ 發球',block:'🤜 攔網',receive:'🖐 接球',
                  toss:'🏐 舉球',attack:'💥 攻擊',start:'▶ START'};
const ZONE_ZH  = {serve:'発球區',block:'攔網區',receive:'接球區',toss:'舉球區',attack:'攻擊區'};

function describeStep(s) {
  const ev = s.ev;
  const d  = ev.data || {};
  const pn = ev.player;
  const pc = pn===1 ? 'p1c' : 'p2c';

  switch(ev.kind) {
    case 'game_start':
      return '<div class="ev-title">🏐 遊戲開始</div>'
           + '<div class="ev-sub"><span class="p1c">P1 '+d.p1+'</span> vs <span class="p2c">P2 '+d.p2+'</span></div>';

    case 'phase': {
      const ph = PHASE_ZH[d.phase]||d.phase;
      return '<div class="ev-title"><span class="'+pc+'">'+ph+' 階段</span></div>'
           + '<div class="ev-sub">P'+pn+' ('+P1NAME+P2NAME.slice(-2)+') 行動</div>';
    }

    case 'draw':
      return '<div class="ev-title">🃏 <span class="'+pc+'">P'+pn+'</span> 從牌庫抽牌</div>'
           + '<div class="ev-card">'+d.card_name+'</div>'
           + '<div class="ev-stat dim">'+d.card_no+'</div>';

    case 'deploy': {
      const stats = d.stats||{};
      const sp = Object.entries(stats).filter(([k,v])=>v!==null&&v!==undefined)
                       .map(([k,v])=>k.toUpperCase()+'=<b>'+v+'</b>').join('  ');
      const zn = ZONE_ZH[d.zone]||d.zone;
      return '<div class="ev-title">▶ <span class="'+pc+'">P'+pn+'</span> 出場角色</div>'
           + '<div class="ev-card">'+d.card_name+'</div>'
           + (sp?'<div class="ev-stat">'+sp+'</div>':'')
           + '<div class="ev-sub">→ <b>'+zn+'</b></div>';
    }

    case 'judge': {
      const ok = !d.lost;
      const c  = ok ? 'var(--ok)' : 'var(--err)';
      const ic = ok ? '✅' : '❌';
      const phZh = {block:'攔網',receive:'接球',attack:'攻擊',serve:'發球',toss:'舉球'}[d.phase]||d.phase;
      return '<div class="ev-title" style="color:'+c+'">'+ic+' '+phZh+'判定</div>'
           + '<div class="ev-judge">DP = '+d.dp+'  vs  OP = '+d.op+'</div>'
           + '<div class="ev-sub" style="color:'+c+'">'+(ok?'防守成功！':'LOST 宣告！')+'</div>';
    }

    case 'action': {
      const ah = {attack:'💥 攻擊',serve:'⬆ 發球',receive:'🖐 接球',block:'🤜 攔網'}[d.action]||d.action;
      const win = d.p1_score>d.p2_score?'P1':d.p2_score>d.p1_score?'P2':'平局';
      const wc  = d.p1_score>d.p2_score?'var(--p1)':d.p2_score>d.p1_score?'var(--p2)':'var(--hl)';
      return '<div class="ev-title">'+ah+' 結算</div>'
           + '<div class="ev-judge"><span class="p1c">P1: '+d.p1_score+'</span>'
           +   '  vs  <span class="p2c">P2: '+d.p2_score+'</span></div>'
           + '<div class="ev-sub">→ <span style="color:'+wc+'">'+win+'</span>'
           + (d.notes ? '  <span class="dim">('+d.notes+')</span>' : '')+'</div>';
    }

    case 'lost': {
      const c   = d.set_cards===0 ? 'var(--err)' : (pn===1?'var(--p1)':'var(--p2)');
      const msg = d.set_cards===0 ? '☠ P'+pn+' 敗北！SET ZONE 已耗盡'
                                  : '● P'+pn+' LOST（SET ZONE 剩 '+d.set_cards+' 枚）';
      return '<div class="ev-title" style="color:'+c+'">'+msg+'</div>';
    }

    case 'interval':
      return '<div class="ev-title">🔄 INTERVAL</div>'
           + '<div class="ev-sub"><span class="'+pc+'">P'+pn+'</span> 獲得發球權'
           + '　局分 <span class="hl">'+d.p1_sets+'–'+d.p2_sets+'</span></div>';

    case 'set_result': {
      const wpc = d.winner===1?'p1c':'p2c';
      return '<div class="ev-title">🌟 <span class="'+wpc+'">P'+d.winner+'</span> 得分！</div>'
           + '<div class="ev-judge hl">'+d.p1_sets+' – '+d.p2_sets+'</div>';
    }

    case 'game_end': {
      const wpc = d.winner===1?'p1c':'p2c';
      return '<div class="ev-title">🏆 遊戲結束！<span class="'+wpc+'">P'+d.winner+' 獲勝</span></div>'
           + '<div class="ev-judge hl">'+d.p1_sets+' – '+d.p2_sets+'</div>'
           + '<div class="ev-sub dim">共 '+d.total_turns+' 回合</div>';
    }

    default:
      return '<div class="ev-sub dim">'+ev.kind+': '+JSON.stringify(d).slice(0,80)+'</div>';
  }
}

const CHIP_ICON = {
  game_start:'🏐',phase:'◉',draw:'🃏',deploy:'▶',judge:'⚖',
  action:'⚡',lost:'💀',interval:'🔄',set_result:'🌟',game_end:'🏆'
};

function renderHistory() {
  const hist = document.getElementById('step-history');
  hist.innerHTML = STEPS.map((s,i) => {
    const k  = s.ev.kind;
    const ic = CHIP_ICON[k]||'·';
    const pn = s.ev.player;
    const pc = pn===1?'cp1':pn===2?'cp2':'';
    const ac = i===SI ? ' active' : '';
    const ph = k==='phase' ? ' title="'+s.ev.data.phase+'"' : '';
    return '<div class="chip'+ac+' '+pc+'"'+ph+' onclick="goTo('+i+')">'+ic+'</div>';
  }).join('');
}

// Keyboard navigation
document.addEventListener('keydown', e => {
  if (document.getElementById('step-view').style.display==='none') return;
  if (e.target.tagName==='INPUT'||e.target.tagName==='BUTTON') return;
  if (e.key==='ArrowRight'||e.key===' ') { e.preventDefault(); goTo(SI+1); }
  else if (e.key==='ArrowLeft') { e.preventDefault(); goTo(SI-1); }
  else if (e.key==='l'||e.key==='L') jumpTo('lost');
  else if (e.key==='s'||e.key==='S') jumpTo('set_result');
  else if (e.key==='End') goTo(STEPS.length-1);
  else if (e.key==='Home') goTo(0);
});

// ─────────────────────────────────────────────────────
// ══ LOG VIEW ══
// ─────────────────────────────────────────────────────
function pc(n) { return n===1?'p1c':'p2c'; }

function renderEv(ev) {
  const d = ev.data||{};
  const pc_ = pc(ev.player);
  let cls = ev.kind, inner = '';

  if (ev.kind==='game_start') {
    inner='🏐 遊戲開始 <span class="p1c">P1 '+d.p1+'</span> vs <span class="p2c">P2 '+d.p2+'</span>';
  } else if (ev.kind==='phase') {
    const phZ=(PHASE_ZH[d.phase]||d.phase);
    inner='<span class="'+pc_+'">〔'+phZ+' 階段〕</span>';
  } else if (ev.kind==='judge') {
    const res=d.lost?'<span style="color:var(--err)">✗ LOST</span>':'<span style="color:var(--ok)">✓ 成功</span>';
    inner='判定 DP='+d.dp+' vs OP='+d.op+'  '+res;
  } else if (ev.kind==='lost') {
    if (d.set_cards===0) inner='<b style="color:var(--err)">☠ P'+ev.player+' LOST — 敗北！</b>';
    else inner='<span class="'+pc_+'">● P'+ev.player+' LOST（SET ZONE 剩 '+d.set_cards+' 枚）</span>';
  } else if (ev.kind==='interval') {
    inner='<span class="'+pc_+'">── INTERVAL  局分 '+d.p1_sets+'–'+d.p2_sets+' ──</span>';
  } else if (ev.kind==='deploy') {
    const sp=d.stats?Object.entries(d.stats).filter(([k,v])=>v).map(([k,v])=>k.toUpperCase()+':'+v).join(' '):'';
    inner='<span class="'+pc_+'">▶ 出場</span> <b>'+d.card_name+'</b> → '+d.zone+(sp?' <span class="dim">['+sp+']</span>':'');
  } else if (ev.kind==='action') {
    const ah={attack:'攻擊',serve:'發球',receive:'接球',block:'攔網'}[d.action]||d.action;
    inner='⚡ '+ah+' — <span class="p1c">P1:'+d.p1_score+'</span> vs <span class="p2c">P2:'+d.p2_score+'</span>'
         +(d.notes?' <span class="dim">'+d.notes+'</span>':'');
  } else if (ev.kind==='set_result') {
    document.getElementById('final-score').textContent=d.p1_sets+'–'+d.p2_sets;
    inner='★ P'+d.winner+' 得分！局分 '+d.p1_sets+'–'+d.p2_sets+' ★';
  } else if (ev.kind==='board_snapshot') {
    inner='<span class="'+pc_+' dim">場地 P'+ev.player+'</span> 手:'+d.hand_count+' 庫:'+d.pile_count+' 棄:'+d.grave_count;
  } else if (ev.kind==='draw') {
    inner='<span class="'+pc_+' dim">抽牌</span> '+d.card_name;
  } else if (ev.kind==='game_end') {
    document.getElementById('final-score').textContent=d.p1_sets+'–'+d.p2_sets;
    inner='🏆 P'+d.winner+' 獲勝　'+d.p1_sets+'–'+d.p2_sets+'　共'+d.total_turns+'回合';
  } else {
    inner=ev.kind+': '+JSON.stringify(d).slice(0,60);
  }
  return '<div class="ev '+cls+'" data-kind="'+ev.kind+'"><span class="ts">'+ev.ts+'</span>'+inner+'</div>';
}

let _filter='all';
function filterEvs(kind) {
  _filter=kind;
  document.querySelectorAll('.filter-btn').forEach(b=>{
    b.classList.toggle('active', b.textContent===kind||(kind==='all'&&b.textContent==='全部'));
  });
  document.querySelectorAll('#events .ev').forEach(e=>{
    e.style.display=(kind==='all'||e.dataset.kind===kind)?'':'none';
  });
}

// ─────────────────────────────────────────────────────
// Init
// ─────────────────────────────────────────────────────
function init() {
  // Render log view
  document.getElementById('events').innerHTML = RAW.map(renderEv).join('');
  // Start in step mode at step 0
  setMode('step');
  goTo(0);
}

init();
</script>
</body>
</html>"""

        return head + css + body_html + events_json + script_tail

    def _build_html_old(self) -> str:
        """舊版 HTML（備份，不再使用）"""
        return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Haikyuu TCG Replay — {title}</title>
<style>
:root {{
  --p1:#f97316; --p2:#38bdf8; --ok:#4ade80; --err:#f87171;
  --bg:#0f172a; --surface:#1e293b; --border:#334155;
  --text:#e2e8f0; --dim:#64748b; --hl:#fbbf24;
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:'SF Mono',monospace; background:var(--bg); color:var(--text); padding:16px; }}
h1 {{ font-size:1.2rem; color:var(--hl); margin-bottom:16px; }}
.score-bar {{ display:flex; gap:16px; align-items:center; margin-bottom:20px;
             background:var(--surface); padding:10px 16px; border-radius:8px; }}
.p1c {{ color:var(--p1); font-weight:bold; }}
.p2c {{ color:var(--p2); font-weight:bold; }}
.vs {{ color:var(--dim); }}
.sets {{ color:var(--hl); font-size:1.4rem; font-weight:bold; }}

.events {{ display:flex; flex-direction:column; gap:4px; }}
.ev {{ border-radius:6px; padding:6px 12px; border-left:3px solid var(--border);
       font-size:0.82rem; line-height:1.6; cursor:pointer; }}
.ev:hover {{ background:var(--surface); }}
.ev.turn_start {{ border-color:var(--dim); background:rgba(30,41,59,.7);
                  font-weight:bold; font-size:0.9rem; margin-top:8px; }}
.ev.deploy {{ border-color:#8b5cf6; }}
.ev.skill.ok {{ border-color:var(--ok); }}
.ev.skill.blocked {{ border-color:var(--dim); color:var(--dim); }}
.ev.action {{ border-color:var(--hl); background:rgba(30,41,59,.5); }}
.ev.set_result {{ border-color:var(--hl); background:rgba(251,191,36,.1);
                  font-size:1rem; font-weight:bold; text-align:center; }}
.ev.game_end {{ border-color:var(--ok); background:rgba(74,222,128,.1);
               font-size:1.1rem; font-weight:bold; text-align:center; }}
.ev.board_snapshot {{ border-color:var(--border); font-size:0.78rem; color:var(--dim); }}
.ev.board_snapshot.expanded {{ color:var(--text); }}
.ev.phase {{ border-color:#6366f1; color:#a5b4fc; font-size:0.8rem; }}
.ev.judge {{ border-color:#0ea5e9; font-size:0.82rem; }}
.ev.lost {{ border-color:var(--err); background:rgba(248,113,113,.08); font-weight:bold; }}
.ev.interval {{ border-color:var(--dim); background:rgba(30,41,59,.9); font-style:italic; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:4px; }}
.zone {{ background:rgba(255,255,255,.05); border-radius:4px; padding:4px 8px; }}
.zone-name {{ color:var(--dim); font-size:0.72rem; }}
.zone-card {{ font-weight:bold; }}
.p1 {{ color:var(--p1); }}
.p2 {{ color:var(--p2); }}
.bonus {{ color:var(--ok); }}
.ts {{ color:var(--dim); font-size:0.72rem; float:right; }}
.filter-bar {{ display:flex; gap:8px; margin-bottom:12px; flex-wrap:wrap; }}
.filter-btn {{ padding:4px 12px; border-radius:999px; border:1px solid var(--border);
              background:transparent; color:var(--text); cursor:pointer; font-size:0.8rem; }}
.filter-btn.active {{ background:var(--hl); color:#000; border-color:var(--hl); }}
</style>
</head>
<body>
<h1>🏐 Haikyuu TCG Replay</h1>
<div class="score-bar">
  <span class="p1c" id="p1label">P1</span>
  <span class="sets" id="final-score">0–0</span>
  <span class="vs">vs</span>
  <span class="p2c" id="p2label">P2</span>
</div>
<div class="filter-bar">
  <button class="filter-btn active" onclick="filterEvs('all')">全部</button>
  <button class="filter-btn" onclick="filterEvs('phase')">階段</button>
  <button class="filter-btn" onclick="filterEvs('deploy')">出場</button>
  <button class="filter-btn" onclick="filterEvs('judge')">判定</button>
  <button class="filter-btn" onclick="filterEvs('action')">OP/DP</button>
  <button class="filter-btn" onclick="filterEvs('lost')">LOST</button>
  <button class="filter-btn" onclick="filterEvs('set_result')">得分</button>
</div>
<div class="events" id="events"></div>

<script>
const RAW = {events_json};
let currentFilter = 'all';

function pc(n) {{ return n===1?'p1':'p2'; }}

function renderEv(ev) {{
  const d = ev.data || {{}};
  const pc_ = pc(ev.player);
  let cls = ev.kind;
  let inner = '';

  if (ev.kind==='game_start') {{
    inner = `🏐 遊戲開始 <span class="p1c">P1 ${{d.p1}}</span> vs <span class="p2c">P2 ${{d.p2}}</span>`;
    document.getElementById('p1label').textContent = `P1 ${{d.p1}} [${{d.d1||''}}]`;
    document.getElementById('p2label').textContent = `P2 ${{d.p2}} [${{d.d2||''}}]`;
  }} else if (ev.kind==='phase') {{
    const phZh = {{serve:'⬆発球',block:'🤜攔網',receive:'🖐接球',toss:'🏐舉球',attack:'💥攻擊',start:'▶START'}}[d.phase]||d.phase;
    inner = `<span class="${{pc_}}">〔${{phZh}}階段〕</span>`;
  }} else if (ev.kind==='judge') {{
    const phZh = d.phase;
    const res = d.lost ? `<span style="color:var(--err)">✗ LOST</span>` : `<span style="color:var(--ok)">✓ 成功</span>`;
    inner = `判定 DP=${{d.dp}} vs OP=${{d.op}}  ${{res}}`;
  }} else if (ev.kind==='lost') {{
    const nm = ev.player===1 ? document.getElementById('p1label').textContent : document.getElementById('p2label').textContent;
    if (d.set_cards===0) {{
      inner = `<b style="color:var(--err)">☠ P${{ev.player}} LOST — SET ZONE 0枚 → 敗北！</b>`;
    }} else {{
      inner = `<span class="${{pc_}}">● P${{ev.player}} LOST（SET ZONE 剩 ${{d.set_cards}} 枚）</span>`;
    }}
  }} else if (ev.kind==='interval') {{
    inner = `<span class="${{pc_}}">── INTERVAL  局分 ${{d.p1_sets}}–${{d.p2_sets}} ──</span>`;
  }} else if (ev.kind==='turn_start') {{
    const pn = ev.player;
    inner = `<span class="${{pc_}}">Turn ${{d.turn}} │ P${{pn}} ${{d.name}}</span>`;
  }} else if (ev.kind==='deploy') {{
    inner = `<span class="${{pc_}}">▶ 出場</span> <b>${{d.card_name}}</b> (${{d.card_no}}) → ${{d.zone}}`;
    if (d.notes) inner += ` <span style="color:var(--dim)">← ${{d.notes}}</span>`;
    if (d.stats && Object.keys(d.stats).length) {{
      const sp = Object.entries(d.stats).filter(([k,v])=>v).map(([k,v])=>`${{k.toUpperCase()}}:${{v}}`).join(' ');
      inner += ` <span style="color:var(--dim)">[${{sp}}]</span>`;
    }}
  }} else if (ev.kind==='skill') {{
    cls += d.triggered ? ' ok' : ' blocked';
    const icon = d.triggered ? '✓' : '✗';
    const c = d.triggered ? 'var(--ok)' : 'var(--dim)';
    inner = `<span style="color:${{c}}">${{icon}} 技能</span> ${{d.summary}}`;
    if (!d.triggered && d.blocked) inner += ` <span style="color:var(--dim)">(${{d.blocked}})</span>`;
  }} else if (ev.kind==='action') {{
    const act_zh = {{attack:'攻擊',serve:'發球',receive:'接球',block:'攔網',toss:'舉球'}}[d.action]||d.action;
    const win = d.p1_score > d.p2_score ? 'P1' : (d.p2_score > d.p1_score ? 'P2' : '平局');
    const wc = d.p1_score > d.p2_score ? 'var(--p1)' : (d.p2_score > d.p1_score ? 'var(--p2)' : 'var(--hl)');
    inner = `⚡ ${{act_zh}} — <span class="p1c">P1:${{d.p1_score}}</span> vs <span class="p2c">P2:${{d.p2_score}}</span>`;
    inner += ` <span style="color:${{wc}}">→ ${{win}} 得分</span>`;
    if (d.notes) inner += ` <span style="color:var(--dim)">${{d.notes}}</span>`;
  }} else if (ev.kind==='set_result') {{
    document.getElementById('final-score').textContent = `${{d.p1_sets}}–${{d.p2_sets}}`;
    const wn = d.winner===1 ? document.getElementById('p1label').textContent.split(' ').slice(1).join(' ')
                            : document.getElementById('p2label').textContent.split(' ').slice(1).join(' ');
    inner = `★ P${{d.winner}} ${{wn}} 得分！局分 ${{d.p1_sets}}–${{d.p2_sets}} ★`;
  }} else if (ev.kind==='board_snapshot') {{
    const pn = ev.player;
    const snap = d;
    const card = (c,b=0) => c ? `<b>${{c}}</b>${{b?' <span class="bonus">+'+b+'</span>':''}}` : '<span style="color:var(--dim)">空</span>';
    const blocks = (snap.blocks||[]).filter(Boolean).map(b=>card(b)).join(', ') || '<span style="color:var(--dim)">空</span>';
    inner = `<span class="${{pc_}}">場地 P${{pn}}</span> 手牌${{snap.hand_count}} 牌庫${{snap.pile_count}} 棄牌${{snap.grave_count}}(${{snap.unique_grave}}/6)`;
    inner += `<div class="grid" style="display:none" class="board-grid">`;
    inner += `<div class="zone"><div class="zone-name">發球</div><div class="zone-card">${{card(snap.serve,snap.srv_bonus)}}</div></div>`;
    inner += `<div class="zone"><div class="zone-name">舉球</div><div class="zone-card">${{card(snap.toss,snap.tos_bonus)}}</div></div>`;
    inner += `<div class="zone"><div class="zone-name">攻擊</div><div class="zone-card">${{card(snap.attack,snap.atk_bonus)}}</div></div>`;
    inner += `<div class="zone"><div class="zone-name">接球</div><div class="zone-card">${{card(snap.receive,snap.rcv_bonus)}}</div></div>`;
    inner += `<div class="zone" style="grid-column:1/-1"><div class="zone-name">攔網</div><div class="zone-card">${{blocks}}</div></div>`;
    inner += `</div>`;
    cls += ' board_snapshot';
  }} else if (ev.kind==='game_end') {{
    const wn = d.winner===1 ? document.getElementById('p1label').textContent.split(' ').slice(1).join(' ')
                            : document.getElementById('p2label').textContent.split(' ').slice(1).join(' ');
    inner = `🏆 遊戲結束！P${{d.winner}} ${{wn}} 獲勝　局分 ${{d.p1_sets}}–${{d.p2_sets}}　共 ${{d.total_turns}} 回合`;
    document.getElementById('final-score').textContent = `${{d.p1_sets}}–${{d.p2_sets}}`;
  }} else if (ev.kind==='log') {{
    inner = `<span style="color:var(--dim)">[log] ${{d.msg}}</span>`;
    cls = 'ev log';
  }} else {{
    inner = JSON.stringify(d);
  }}

  return `<div class="ev ${{cls}}" data-kind="${{ev.kind}}" onclick="toggleBoard(this)">
    ${{inner}}<span class="ts">${{ev.ts}}</span>
  </div>`;
}}

function toggleBoard(el) {{
  const grid = el.querySelector('.board-grid, [style*="display:none"]');
  if (grid) {{
    grid.style.display = grid.style.display==='none'?'grid':'none';
    el.classList.toggle('expanded');
  }}
}}

function filterEvs(kind) {{
  currentFilter = kind;
  document.querySelectorAll('.filter-btn').forEach(b=>{{
    b.classList.toggle('active', b.textContent.includes(kind) || (kind==='all' && b.textContent==='全部'));
  }});
  document.querySelectorAll('.ev').forEach(ev=>{{
    if (kind==='all') {{ ev.style.display=''; return; }}
    ev.style.display = ev.dataset.kind===kind ? '' : 'none';
  }});
}}

function init() {{
  const container = document.getElementById('events');
  container.innerHTML = RAW.map(renderEv).join('');
}}

init();
</script>
</body>
</html>"""
