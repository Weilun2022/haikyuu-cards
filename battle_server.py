#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, unquote
from pathlib import Path

ROOT = r"C:\Users\evils\Documents\Claude\Claude Code\排球少年"
sys.path.insert(0, ROOT)

from game_engine.sim_runner import run_battle_from_deck_dicts, load_cards

load_cards()

class BattleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = unquote(parsed_path.path)

        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/battle_from_qr.html")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return

        if path == "/battle_from_qr.html":
            file_path = os.path.join(ROOT, "battle_from_qr.html")
            if os.path.exists(file_path):
                self.serve_file(file_path, "text/html")
            else:
                self.send_error(404, "File not found")
            return

        if path == "/lz-string.min.js":
            file_path = os.path.join(ROOT, "node_modules", "lz-string", "libs", "lz-string.min.js")
            if os.path.exists(file_path):
                self.serve_file(file_path, "application/javascript")
            else:
                self.send_error(404, "File not found")
            return

        if path.startswith("/replays/"):
            filename = path[9:]
            file_path = os.path.join(ROOT, "replays", filename)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                mime_type, _ = mimetypes.guess_type(file_path)
                if mime_type is None:
                    mime_type = "application/octet-stream"
                self.serve_file(file_path, mime_type)
            else:
                self.send_error(404, "File not found")
            return

        if path.startswith("/images/"):
            filename = path[8:]
            file_path = os.path.join(ROOT, "images", filename)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                mime_type, _ = mimetypes.guess_type(file_path)
                if mime_type is None:
                    mime_type = "application/octet-stream"
                self.serve_file(file_path, mime_type)
            else:
                self.send_error(404, "File not found")
            return

        if path == "/cards_data.js":
            file_path = os.path.join(ROOT, "cards_data.js")
            if os.path.exists(file_path):
                self.serve_file(file_path, "application/javascript")
            else:
                self.send_error(404, "File not found")
            return

        if path == "/cards_zh.json":
            file_path = os.path.join(ROOT, "cards_zh.json")
            if os.path.exists(file_path):
                self.serve_file(file_path, "application/json")
            else:
                self.send_error(404, "File not found")
            return

        self.send_error(404, "Not found")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = unquote(parsed_path.path)

        if path == "/battle":
            content_length = int(self.headers.get("Content-Length", 0))
            try:
                body = self.rfile.read(content_length).decode("utf-8")
                request_data = json.loads(body)
            except Exception as e:
                self.send_json_response({"ok": False, "error": f"Invalid request: {str(e)}"}, 400)
                return

            try:
                deck1_name = request_data.get("deck1", {}).get("name", "P1牌組")
                deck1_cards = request_data.get("deck1", {}).get("cards", {})
                deck2_name = request_data.get("deck2", {}).get("name", "P2牌組")
                deck2_cards = request_data.get("deck2", {}).get("cards", {})
                seed = request_data.get("seed")

                if not deck1_cards or not deck2_cards:
                    self.send_json_response({"ok": False, "error": "Both decks must have cards"}, 400)
                    return

                result = run_battle_from_deck_dicts(
                    deck1_cards,
                    deck1_name,
                    deck2_cards,
                    deck2_name,
                    seed=seed,
                )

                if not result:
                    self.send_json_response({"ok": False, "error": "Simulation failed"}, 500)
                    return

                visual_replay_path = result.get("visual_replay_path")
                if visual_replay_path:
                    filename = os.path.basename(visual_replay_path)
                    visual_replay_url = f"/replays/{filename}"
                else:
                    visual_replay_url = None

                response = {
                    "ok": True,
                    "winner": result.get("winner"),
                    "turns": result.get("turns"),
                    "p1_sets": result.get("p1_sets"),
                    "p2_sets": result.get("p2_sets"),
                    "visual_replay_url": visual_replay_url
                }

                self.send_json_response(response, 200)

            except Exception as e:
                self.send_json_response({"ok": False, "error": str(e)}, 500)

            return

        self.send_error(404, "Not found")

    def serve_file(self, file_path, mime_type):
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", len(content))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error serving file: {str(e)}")

    def send_json_response(self, data, status_code):
        response = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(response))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format, *args):
        pass


def run_server():
    server_address = ("", 7777)
    httpd = HTTPServer(server_address, BattleHandler)
    print("伺服器啟動於 http://localhost:7777")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n伺服器已停止")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
