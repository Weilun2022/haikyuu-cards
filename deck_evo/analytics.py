"""
deck_evo/analytics.py — Strategy & Analytics Agent（戰術分析 Agent）
跨世代累積卡牌關聯矩陣，找出最強 Combo 與貢獻卡。
"""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
from deck_evo.genome import DeckGenome
from deck_evo.card_pool import get_card as _get_card


class Analytics:
    def __init__(self):
        # card_no → 累計 (win_rate_sum, appearances)
        self._card_wr: dict[str, list] = defaultdict(lambda: [0.0, 0])
        # (card_a, card_b) → (共現分數累計, 出現次數)
        self._pair_wr: dict[tuple, list] = defaultdict(lambda: [0.0, 0])
        self._total_evals = 0

    def update(self, genomes: list[DeckGenome]):
        """每世代評估後更新統計。"""
        for g in genomes:
            if g.games_played == 0:
                continue
            wr = g.win_rate
            cards = list(g.cards.keys())
            # 單卡貢獻
            for cno in cards:
                self._card_wr[cno][0] += wr
                self._card_wr[cno][1] += 1
            # 牌對共現（取前 15 張防止 O(n²) 爆炸）
            top_cards = sorted(cards, key=lambda c: g.card_scores.get(c, 0), reverse=True)[:15]
            for i, a in enumerate(top_cards):
                for b in top_cards[i+1:]:
                    key = (min(a, b), max(a, b))
                    self._pair_wr[key][0] += wr
                    self._pair_wr[key][1] += 1
        self._total_evals += len(genomes)

    def top_cards(self, n: int = 10) -> list[dict]:
        """傳回平均貢獻最高的 n 張卡。"""
        result = []
        for cno, (wr_sum, cnt) in self._card_wr.items():
            if cnt < 2:
                continue
            avg = wr_sum / cnt
            c = _get_card(cno) or {}
            result.append({
                "card_no": cno,
                "name": c.get("name", cno),
                "school": c.get("school", ""),
                "avg_win_rate": round(avg, 4),
                "appearances": cnt,
            })
        return sorted(result, key=lambda x: x["avg_win_rate"], reverse=True)[:n]

    def top_combos(self, n: int = 8, min_appearances: int = 3) -> list[dict]:
        """傳回共現勝率最高的牌對（Combo）。"""
        result = []
        for (a, b), (wr_sum, cnt) in self._pair_wr.items():
            if cnt < min_appearances:
                continue
            avg = wr_sum / cnt
            ca = _get_card(a) or {}
            cb = _get_card(b) or {}
            result.append({
                "cards": [a, b],
                "card_a": a,
                "card_b": b,
                "name_a": ca.get("name", a),
                "name_b": cb.get("name", b),
                "display_name": f"{ca.get('name', a)} × {cb.get('name', b)}",
                "combo_win_rate": round(avg, 4),
                "appearances": cnt,
            })
        return sorted(result, key=lambda x: x["combo_win_rate"], reverse=True)[:n]

    def to_dict(self) -> dict:
        return {
            "top_cards": self.top_cards(10),
            "top_combos": self.top_combos(8),
            "total_evals": self._total_evals,
        }
