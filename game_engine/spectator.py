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
        title = f"P1 {self._p1_name}[{d1}] vs P2 {self._p2_name}[{d2}]"

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
