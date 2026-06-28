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
from deck_evo.evolution_engine import EvoEngine

# ── 全域狀態 ──────────────────────────────────────────────────────────────────
_engine: EvoEngine | None = None
_update_queue: queue.Queue = queue.Queue(maxsize=500)
_latest_stats: dict = {}
_lock = threading.Lock()


def _push(data: dict):
    with _lock:
        global _latest_stats
        _latest_stats = data
    try:
        _update_queue.put_nowait(data)
    except queue.Full:
        try:
            _update_queue.get_nowait()
        except queue.Empty:
            pass
        _update_queue.put_nowait(data)


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class EvoHandler(BaseHTTPRequestHandler):

    # ── GET ──────────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in ("/", "/index.html"):
            self._serve_file(ROOT / "evo_dashboard.html", "text/html")
        elif path == "/evo_arena.html":
            self._serve_file(ROOT / "evo_arena.html", "text/html")
        elif path == "/events":
            self._sse_stream()
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
        elif path.startswith("/replays/"):
            fname = path[9:]
            self._serve_file(ROOT / "replays" / fname)
        elif path.startswith("/images/"):
            fname = path[8:]
            self._serve_file(ROOT / "images" / fname)
        elif path == "/cards_data.js":
            self._serve_file(ROOT / "cards_data.js", "application/javascript")
        elif path == "/lz-string.min.js":
            self._serve_file(ROOT / "node_modules" / "lz-string" / "libs" / "lz-string.min.js",
                             "application/javascript")
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

        # 只取資料庫中存在的 meta 牌組
        meta_decks = {n: DECKS[n] for n in meta_names if n in DECKS}
        if not meta_decks:
            meta_decks = {"STANDARD": DECKS["STANDARD"]}

        # 清空更新佇列
        while not _update_queue.empty():
            try: _update_queue.get_nowait()
            except queue.Empty: break

        _engine = EvoEngine(
            seed_deck=seed_deck,
            meta_decks=meta_decks,
            cfg=cfg or None,
            on_generation=_push,
        )
        _engine.start()
        self._json({"ok": True, "message": "進化已啟動", "meta_decks": list(meta_decks)})

    def _handle_stop(self):
        global _engine
        if _engine:
            _engine.stop()
        self._json({"ok": True, "message": "進化已停止"})

    def _handle_replays_list(self):
        """GET /api/replays_list - 列出所有 replay HTML 檔案"""
        replays_dir = ROOT / "replays"
        replays = []

        if replays_dir.exists() and replays_dir.is_dir():
            # 掃描 visual_replay_*.html 檔案
            for fpath in replays_dir.glob("visual_replay_*.html"):
                replays.append(fpath.name)

        # 按時間戳倒序排列（新的在前）
        replays.sort(reverse=True)

        latest = replays[0] if replays else None
        self._json({
            "replays": replays,
            "latest": latest
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

    def _status_dict(self) -> dict:
        return {
            "running": bool(_engine and _engine.running),
            "generation": _engine.generation if _engine else 0,
            "best_win_rate": _latest_stats.get("best_win_rate", 0),
            "available_meta_decks": list(DECKS.keys()),
        }

    # ── SSE 串流 ─────────────────────────────────────────────────────────────

    def _sse_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors()
        self.end_headers()

        # 立即發送目前狀態
        if _latest_stats:
            self._sse_write(_latest_stats)

        # 持續等待新更新
        while True:
            try:
                data = _update_queue.get(timeout=30)
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
