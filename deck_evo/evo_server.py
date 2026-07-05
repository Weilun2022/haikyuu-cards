"""
deck_evo/evo_server.py — Replay & Dashboard Agent HTTP 伺服器
port 7778 | SSE 串流進化狀態 | REST API 控制進化
"""
from __future__ import annotations
import json
import mimetypes
import os
import queue
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """每個請求在獨立執行緒，允許 SSE 長連線與 REST API 並行。"""
    daemon_threads = True

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from game_engine.sim_runner import DECKS, load_cards
from game_engine.card_db import get_card
from deck_evo.evolution_engine import EvoEngine
from deck_evo import deck_validator, persistence

# ── 全域狀態 ──────────────────────────────────────────────────────────────────
_engine: EvoEngine | None = None
_update_queue: queue.Queue = queue.Queue(maxsize=500)
_latest_stats: dict = {}
_lock = threading.Lock()

# PK 競技場（獨立於進化引擎的狀態）
_pk_engine = None
_pk_queue: queue.Queue = queue.Queue(maxsize=500)
_pk_latest: dict = {}
_pk_lock = threading.Lock()


def _pk_push(data: dict):
    with _pk_lock:
        global _pk_latest
        _pk_latest = data
    try:
        _pk_queue.put_nowait(data)
    except queue.Full:
        try:
            _pk_queue.get_nowait()
        except queue.Empty:
            pass
        _pk_queue.put_nowait(data)


def _card_display_name(card_no: str) -> str:
    """查卡片顯示名稱，找不到 fallback 回 card_no。"""
    try:
        c = get_card(card_no)
        return c.get("name", card_no) if c else card_no
    except Exception:
        return card_no


def _enrich_analytics(analytics: dict) -> dict:
    """在 analytics dict 補卡片名稱欄位（不改動原有欄位）。"""
    if not analytics:
        return analytics
    result = dict(analytics)

    # top_cards：加 name
    if "top_cards" in result:
        result["top_cards"] = [
            {**card, "name": _card_display_name(card.get("card_no", ""))}
            for card in result["top_cards"]
        ]

    # top_combos：加 display_name / name_a / name_b
    if "top_combos" in result:
        enriched = []
        for combo in result["top_combos"]:
            # analytics.py 回傳 card_a/card_b key，不是 cards list
            cards = combo.get("cards") or [
                c for c in [combo.get("card_a"), combo.get("card_b")] if c
            ]
            names = [_card_display_name(c) for c in cards]
            enriched.append({
                **combo,
                "names": names,
                "name_a": names[0] if len(names) > 0 else "",
                "name_b": names[1] if len(names) > 1 else "",
                "display_name": " × ".join(names),
            })
        result["top_combos"] = enriched

    return result


def _enrich_best_deck(best_deck: dict) -> dict:
    """在 best_deck 補 card_list（含名稱/數量/貢獻分）。"""
    if not best_deck:
        return best_deck
    cards = best_deck.get("cards", {})
    scores = best_deck.get("card_scores", {})
    card_list = [
        {
            "card_no": cno,
            "name": _card_display_name(cno),
            "count": cnt,
            "score": round(scores.get(cno, 0.0), 4),
        }
        for cno, cnt in cards.items()
    ]
    card_list.sort(key=lambda x: x["score"], reverse=True)
    return {**best_deck, "card_list": card_list}


def _push(data: dict):
    # Enrich 名稱欄位
    enriched = dict(data)
    if "analytics" in enriched:
        enriched["analytics"] = _enrich_analytics(enriched["analytics"])
    if "best_deck" in enriched:
        enriched["best_deck"] = _enrich_best_deck(enriched["best_deck"])
    enriched["schema_version"] = 2

    with _lock:
        global _latest_stats
        _latest_stats = enriched
    try:
        _update_queue.put_nowait(enriched)
    except queue.Full:
        try:
            _update_queue.get_nowait()
        except queue.Empty:
            pass
        _update_queue.put_nowait(enriched)


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class EvoHandler(BaseHTTPRequestHandler):

    # ── GET ──────────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in ("/", "/index.html", "/deck_forge.html"):
            self._serve_file(ROOT / "deck_forge.html", "text/html")
        elif path == "/evo_arena.html":
            self._serve_file(ROOT / "evo_arena.html", "text/html")
        elif path in ("/pk", "/pk_arena.html"):
            self._serve_file(ROOT / "pk_arena.html", "text/html")
        elif path == "/evo_dashboard.html":
            self._serve_file(ROOT / "evo_dashboard.html", "text/html")
        elif path == "/events":
            self._sse_stream()
        elif path == "/pk/events":
            self._sse_stream(pk=True)
        elif path == "/pk/status":
            self._json(_pk_latest or {"running": False, "game_no": 0})
        elif path == "/status":
            self._json(self._status_dict())
        elif path == "/best_deck":
            self._json(_latest_stats.get("best_deck", {}))
        elif path == "/analytics":
            self._json(_latest_stats.get("analytics", {}))
        elif path == "/api/replays_list":
            self._handle_replays_list()
        elif path == "/api/config":
            self._handle_config()
        elif path == "/api/hall_of_fame":
            self._handle_hall_of_fame()
        elif path == "/api/replay_events":
            self._handle_replay_events()
        elif path == "/api/replay_list":
            self._handle_replay_list()
        elif path == "/api/find_replay_with_combo":
            self._handle_find_replay_with_combo()
        elif path.startswith("/replays/"):
            fname = path[9:]
            self._serve_file(ROOT / "replays" / fname)
        elif path.startswith("/images/"):
            fname = path[8:]
            img_path = ROOT / "images" / fname
            if not img_path.exists():
                # card_no+'.jpg' fallback: strip ext, find first HV-XXXX-*.webp
                base = fname.rsplit('.', 1)[0]
                matches = sorted((ROOT / "images").glob(f"{base}-*.webp"))
                if matches:
                    self._serve_file(matches[0], "image/webp")
                    return
            self._serve_file(img_path)
        elif path == "/lz-string.min.js":
            self._serve_file(ROOT / "node_modules" / "lz-string" / "libs" / "lz-string.min.js",
                             "application/javascript")
        elif path.endswith(".js") and "/" not in path[1:]:
            # 根目錄靜態 JS 檔（buildSteps.js, createReplayViewer.js, cards_data.js 等）
            self._serve_file(ROOT / path[1:], "application/javascript")
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self._cors(); self.end_headers()

    # ── POST ─────────────────────────────────────────────────────────────────

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        body = self._read_body()

        if path == "/start":
            self._handle_start(body)
        elif path == "/stop":
            self._handle_stop()
        elif path == "/api/validate_deck":
            self._handle_validate_deck(body)
        elif path == "/api/detect_school":
            self._handle_detect_school(body)
        elif path == "/api/control":
            self._handle_control(body)
        elif path == "/api/battle/practice":
            self._handle_practice(body)
        elif path == "/pk/start":
            self._handle_pk_start(body)
        elif path == "/pk/stop":
            self._handle_pk_stop()
        elif path == "/pk/next":
            self._handle_pk_next()
        else:
            self.send_error(404)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _handle_start(self, body: dict):
        global _engine
        if _engine and _engine.running:
            self._json({"ok": False, "error": "已在運行中，請先 /stop"}, 400)
            return

        seed_deck = body.get("seed_deck")         # {card_no: count}
        meta_names = body.get("meta_decks", ["ROKUNIN", "STANDARD"])
        cfg = body.get("config", {})

        if not seed_deck:
            # 從 seed_deck_name 取得內建牌組
            seed_name = body.get("seed_deck_name", "ROKUNIN")
            seed_deck = dict(DECKS.get(seed_name, DECKS["ROKUNIN"]))

        # 單一 meta → 自動補全所有 preset 以避免過擬合
        if isinstance(meta_names, list) and len(meta_names) <= 1:
            meta_names = list(DECKS.keys())

        # 只取資料庫中存在的 meta 牌組
        meta_decks = {n: DECKS[n] for n in meta_names if n in DECKS}
        if not meta_decks:
            meta_decks = {"STANDARD": DECKS["STANDARD"]}

        # 清空更新佇列
        while not _update_queue.empty():
            try: _update_queue.get_nowait()
            except queue.Empty: break

        # school_lock: "auto"(預設)=從種子偵測, null=自由進化, 字串=指定學校
        school_lock = body.get("school_lock", "auto")

        _engine = EvoEngine(
            seed_deck=seed_deck,
            meta_decks=meta_decks,
            cfg=cfg or None,
            on_generation=_push,
            school_lock=school_lock,
        )
        _engine.start()
        self._json({"ok": True, "message": "進化已啟動", "meta_decks": list(meta_decks)})

    def _handle_stop(self):
        global _engine
        if _engine:
            _engine.stop()
        self._json({"ok": True, "message": "進化已停止"})

    def _handle_validate_deck(self, body: dict):
        cards = (body or {}).get("cards", {})
        result = deck_validator.validate(cards)
        self._json(result)

    def _handle_detect_school(self, body: dict):
        """POST /api/detect_school {cards:{card_no:count}} → {school, total}"""
        from deck_evo.card_pool import detect_school
        cards = (body or {}).get("cards", {})
        if not isinstance(cards, dict) or not cards:
            self._json({"school": None, "total": 0, "error": "cards 不可為空"}, 400)
            return
        try:
            self._json({
                "school": detect_school(cards),
                "total": sum(int(v) for v in cards.values()),
            })
        except Exception as e:
            self._json({"school": None, "total": 0, "error": str(e)}, 500)

    def _handle_control(self, body: dict):
        global _engine
        if _engine is None:
            self._json({"error": "目前無進化引擎"}, 409)
            return
        action = (body or {}).get("action")
        if action == "pause":
            _engine.pause()
            self._json({"status": "paused"})
        elif action == "resume":
            _engine.resume()
            self._json({"status": "running"})
        else:
            self._json({"error": "action 須為 'pause' 或 'resume'"}, 400)

    def _handle_hall_of_fame(self):
        qs = parse_qs(urlparse(self.path).query)
        try:
            limit = int(qs.get("limit", ["20"])[0])
        except (ValueError, IndexError):
            limit = 20
        try:
            data = persistence.get_hall_of_fame(limit=limit)
            self._json({"hall_of_fame": data, "count": len(data)})
        except Exception as e:
            self._json({"error": str(e), "hall_of_fame": []}, 500)

    def _handle_practice(self, body: dict):
        """
        POST /api/battle/practice
        body: {
          "player_deck": {card_no: count},
          "ai_deck":     {card_no: count},   # 可選，預設 STANDARD
          "difficulty":  "easy"|"normal"|"hard",
          "seed":        int
        }
        回傳: { ok, winner, turns, log }
        """
        from game_engine.ai.greedy_ai import GreedyAI
        from game_engine.ai.generic_ai import GenericAI
        from game_engine.sim_runner import run_one_game
        from deck_evo.card_pool import detect_school

        difficulty = (body or {}).get("difficulty", "normal")
        seed_val = int((body or {}).get("seed", 42))

        # player_deck / ai_deck 支援 dict（自訂）或 str（preset 名稱）
        def _resolve_deck(raw, fallback_key: str) -> dict:
            if isinstance(raw, str) and raw:
                return dict(DECKS.get(raw, DECKS.get(fallback_key, {})))
            if isinstance(raw, dict) and raw:
                return raw
            return dict(DECKS.get(fallback_key, {}))

        player_deck = _resolve_deck((body or {}).get("player_deck"), "ROKUNIN")
        ai_deck     = _resolve_deck((body or {}).get("ai_deck"),     "STANDARD")

        if not player_deck:
            self._json({"ok": False, "error": "player_deck 不可為空，請確認牌組或 preset 名稱"}, 400)
            return

        # 建立有難度設定的 AI class（run_one_game 期待 class，不是實例）
        def _make_ai_class(diff: str):
            class _DiffAI(GreedyAI):
                def __init__(self, player_num: int, name: str = "AI"):
                    super().__init__(player_num, difficulty=diff, name=name)
                    self.seed(seed_val)
            return _DiffAI

        try:
            school1 = detect_school(player_deck)
            school2 = detect_school(ai_deck)
            result = run_one_game(
                deck1=player_deck, deck2=ai_deck,
                name1="Player", name2=f"AI({difficulty})",
                school1=school1, school2=school2,
                ai1_class=GenericAI,
                ai2_class=_make_ai_class(difficulty),
                seed=seed_val,
            )
            self._json({
                "ok":     True,
                "winner": result.get("winner"),
                "turns":  result.get("turns"),
                "p1_sets": result.get("p1_sets"),
                "p2_sets": result.get("p2_sets"),
            })
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, 500)

    # ── PK 競技場 ─────────────────────────────────────────────────────────────

    def _handle_pk_start(self, body: dict):
        """
        POST /pk/start
        body: {
          "deck1": {card_no: count} | "PRESET名",
          "deck2": {card_no: count} | "PRESET名",
          "name1": "我方", "name2": "對方",
          "evolve1": bool, "evolve2": bool,
          "max_games": int, "mode": "watch"|"fast"
        }
        """
        global _pk_engine
        from deck_evo.pk_engine import PKEngine

        if _pk_engine and _pk_engine.running:
            self._json({"ok": False, "error": "PK 已在進行中，請先結束"}, 400)
            return

        def _resolve(raw) -> dict:
            if isinstance(raw, str) and raw:
                return dict(DECKS.get(raw, {}))
            if isinstance(raw, dict):
                return dict(raw)
            return {}

        deck1 = _resolve((body or {}).get("deck1"))
        deck2 = _resolve((body or {}).get("deck2"))
        if not deck1 or not deck2:
            self._json({"ok": False, "error": "deck1 / deck2 不可為空"}, 400)
            return

        warnings = []
        for label, d in (("我方", deck1), ("對方", deck2)):
            n = sum(d.values())
            if n != 40:
                warnings.append(f"{label}牌組共 {n} 張（標準為 40 張）")

        # 清空 PK 更新佇列
        while not _pk_queue.empty():
            try:
                _pk_queue.get_nowait()
            except queue.Empty:
                break

        _pk_engine = PKEngine(
            deck1=deck1, deck2=deck2,
            name1=str((body or {}).get("name1") or "我方")[:20],
            name2=str((body or {}).get("name2") or "對方")[:20],
            evolve1=bool((body or {}).get("evolve1")),
            evolve2=bool((body or {}).get("evolve2")),
            max_games=int((body or {}).get("max_games", 50)),
            mode=(body or {}).get("mode", "watch"),
            on_update=_pk_push,
        )
        _pk_engine.start()
        self._json({"ok": True, "run_id": _pk_engine.run_id, "warnings": warnings})

    def _handle_pk_stop(self):
        global _pk_engine
        if _pk_engine:
            _pk_engine.stop()
        self._json({"ok": True, "message": "PK 已停止"})

    def _handle_pk_next(self):
        if _pk_engine and _pk_engine.running:
            _pk_engine.next_game()
            self._json({"ok": True})
        else:
            self._json({"ok": False, "error": "PK 未在進行中"}, 409)

    def _handle_replays_list(self):
        """GET /api/replays_list?run_id=<id> — 列出 visual_replay 檔案"""
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        run_id = qs.get("run_id", [None])[0]

        replays_dir = ROOT / "replays"
        replays = []

        if replays_dir.exists() and replays_dir.is_dir():
            if run_id:
                # 優先回傳本輪 evo showcase
                pattern = f"visual_replay_evo_{run_id}_*.html"
                replays = sorted(
                    [f.name for f in replays_dir.glob(pattern)],
                    reverse=True,
                )
            if not replays:
                # fallback：所有 visual_replay_evo_
                replays = sorted(
                    [f.name for f in replays_dir.glob("visual_replay_evo_*.html")],
                    reverse=True,
                )

        self._json({
            "replays": replays,
            "latest": replays[0] if replays else None,
        })

    def _handle_config(self):
        """GET /api/config - 回傳前端初始化設定"""
        available_decks = list(DECKS.keys())
        self._json({
            "available_seed_decks": available_decks,
            "available_meta_decks": available_decks,
            "default_config": {
                "population_size": 16,
                "max_generations": 50,
                "games_per_eval": 30,
                "elite_count": 3,
                "mutation_swaps": 3,
                "crossover_rate": 0.35
            }
        })

    def _handle_replay_events(self):
        """GET /api/replay_events?replay_id=<id>
        回傳 visual replay 的 JSON sidecar（Phase 3 arena viewer 用）。
        replay_id 可含或不含 .json 副檔名。
        """
        qs = parse_qs(urlparse(self.path).query)
        replay_id = qs.get("replay_id", [None])[0]
        if not replay_id:
            self._json({"error": "需要 replay_id 參數"}, 400)
            return

        # 支援有無副檔名
        if replay_id.endswith(".html"):
            replay_id = replay_id[:-5]
        if replay_id.endswith(".json"):
            replay_id = replay_id[:-5]

        replays_dir = ROOT / "replays"
        json_path = replays_dir / (replay_id + ".json")

        if not json_path.exists():
            self._json({"error": f"找不到 replay: {replay_id}"}, 404)
            return

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self._json(data)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _handle_find_replay_with_combo(self):
        """GET /api/find_replay_with_combo?card_a=X&card_b=Y
        掃 replays/*.json，找到兩張牌都曾出現的最新 replay。
        """
        qs = parse_qs(urlparse(self.path).query)
        card_a = qs.get("card_a", [None])[0]
        card_b = qs.get("card_b", [None])[0]
        if not card_a or not card_b:
            self._json({"replay_id": None, "error": "需要 card_a 和 card_b 參數"}, 400)
            return

        replays_dir = ROOT / "replays"
        found_replay_id = None

        if replays_dir.exists():
            json_files = sorted(
                replays_dir.glob("visual_replay_evo_*.json"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            for jf in json_files[:60]:
                try:
                    data = json.loads(jf.read_text(encoding="utf-8"))
                    events = data.get("events", [])
                    has_a = has_b = False
                    for event in events:
                        ev_data = event.get("data") or {}
                        cands = [
                            ev_data.get("serve_no"),
                            ev_data.get("receive_no"),
                            ev_data.get("toss_no"),
                            ev_data.get("attack_no"),
                            ev_data.get("card_no"),
                        ]
                        for bn in (ev_data.get("block_nos") or []):
                            cands.append(bn)
                        for c in cands:
                            if c == card_a:
                                has_a = True
                            if c == card_b:
                                has_b = True
                        if has_a and has_b:
                            break
                    if has_a and has_b:
                        found_replay_id = data.get("replay_id", jf.stem)
                        break
                except Exception:
                    pass

        self._json({"replay_id": found_replay_id})

    def _handle_replay_list(self):
        """GET /api/replay_list?limit=<n> — 列出 visual replay JSON sidecar 的 metadata
        掃 replays/ 目錄的 visual_replay_evo_*.json，依 mtime desc 排序。
        單筆 parse 失敗略過，不讓整支 API 500。
        """
        qs = parse_qs(urlparse(self.path).query)
        limit = int(qs.get("limit", [30])[0])
        limit = max(1, min(limit, 200))

        replays_dir = ROOT / "replays"
        items = []

        if replays_dir.exists():
            json_files = sorted(
                replays_dir.glob("visual_replay_evo_*.json"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )[:limit]

            for jf in json_files:
                try:
                    d = json.loads(jf.read_text(encoding="utf-8"))
                    meta = d.get("meta", {})
                    events = d.get("events", [])
                    # 從檔名解析世代（gen{NNNN}）
                    import re as _re
                    _gen_m = _re.search(r'_gen(\d+)_', jf.stem)
                    _generation = int(_gen_m.group(1)) if _gen_m else None
                    items.append({
                        "replay_id": d.get("replay_id", jf.stem),
                        "mtime": jf.stat().st_mtime,
                        "generation": _generation,
                        "p1_name": meta.get("p1_name", "P1"),
                        "p2_name": meta.get("p2_name", "P2"),
                        "d1_name": meta.get("d1_name", ""),
                        "d2_name": meta.get("d2_name", ""),
                        "p1_sets": meta.get("p1_sets", 0),
                        "p2_sets": meta.get("p2_sets", 0),
                        "steps": len(events),
                    })
                except Exception:
                    pass  # 單筆失敗略過

        self._json({"items": items, "total": len(items)})

    def _status_dict(self) -> dict:
        return {
            "running": bool(_engine and _engine.running),
            "generation": _engine.generation if _engine else 0,
            "best_win_rate": _latest_stats.get("best_win_rate", 0),
            "available_meta_decks": list(DECKS.keys()),
        }

    # ── SSE 串流 ─────────────────────────────────────────────────────────────

    def _sse_stream(self, pk: bool = False):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors()
        self.end_headers()

        src_queue = _pk_queue if pk else _update_queue
        latest = _pk_latest if pk else _latest_stats

        # 立即發送目前狀態
        if latest:
            self._sse_write(latest)

        # 持續等待新更新
        while True:
            try:
                data = src_queue.get(timeout=30)
                self._sse_write(data)
            except queue.Empty:
                # 心跳
                try:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                except Exception:
                    break
            except Exception:
                break

    def _sse_write(self, data: dict):
        payload = json.dumps(data, ensure_ascii=False)
        msg = f"data: {payload}\n\n".encode("utf-8")
        self.wfile.write(msg)
        self.wfile.flush()

    # ── 工具 ─────────────────────────────────────────────────────────────────

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path, mime: str | None = None):
        if not path.exists():
            self.send_error(404); return
        if mime is None:
            mime, _ = mimetypes.guess_type(str(path))
            mime = mime or "application/octet-stream"
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", len(content))
        self._cors()
        self.end_headers()
        self.wfile.write(content)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def log_message(self, *args):
        pass  # 靜音 access log


# ── 啟動入口 ──────────────────────────────────────────────────────────────────

def run(port: int = 7778):
    load_cards()
    print(f"[EvoServer] 牌組進化儀表板 → http://localhost:{port}")
    print(f"[EvoServer] 可用牌組: {', '.join(DECKS.keys())}")
    httpd = ThreadedHTTPServer(("", port), EvoHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[EvoServer] 已停止")
        httpd.server_close()


if __name__ == "__main__":
    run()
