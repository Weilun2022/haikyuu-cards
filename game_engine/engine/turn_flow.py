"""
game_engine/engine/turn_flow.py — 回合流程控制器（正確規則實作）

正確遊戲流程（對應官方規則書）：
  發球方 → SERVE PHASE（OP=SRV）→ 對方輪到
  對方 → START → 選擇 BLOCK 或 RECEIVE
    BLOCK: DP=Σ BLK，判定 dp<op→LOST；成功→OP=0
    RECEIVE: 抽1→RCV判定→舉球→攻擊→OP=TOS+ATK
  交替輪流直到某方宣告 LOST
  INTERVAL: 敗者抽到6，拿1張SET牌；set_cards=0時再LOST→敗北
"""
from __future__ import annotations
import random
from game_engine.schema import GameState, PlayerState, ZoneState
from game_engine.card_db import get_card, get_stat, is_event, is_character, get_name

_INITIAL_HAND = 6           # 開局抽牌數（規則書 6 張）
_INTERVAL_HAND_TARGET = 6  # INTERVAL 後補到幾張
_MAX_TURNS_PER_RALLY = 200  # 安全上限（每 rally 最多回合數）


# ── 卡片部署能力判定 ───────────────────────────────────────────────────────────

_ZONE_STAT: dict[str, str] = {
    "serve": "srv", "block": "blk", "receive": "rcv",
    "toss": "tos", "attack": "atk",
}

def _can_deploy(card_no: str, zone: str) -> bool:
    """若該統計值為 None（非0）表示「－」不可在此區出場。"""
    if not is_character(card_no):
        return False
    card = get_card(card_no)
    if card is None:
        return False
    stat = _ZONE_STAT.get(zone)
    if stat is None:
        return True
    return card.get(stat) is not None


def _zone_stat(card_no: str, zone: str) -> int:
    """取卡片在指定區域的數值。"""
    stat = _ZONE_STAT.get(zone, "atk")
    return get_stat(card_no, stat)


# ── OP / DP 計算 ──────────────────────────────────────────────────────────────

def _calc_serve_op(player: PlayerState) -> int:
    c = player.serve_zone.card
    return max(0, get_stat(c, "srv")) if c else 0


def _calc_block_dp(player: PlayerState) -> int:
    total = 0
    for bz in player.block_zones:
        if bz.card:
            total += max(0, get_stat(bz.card, "blk"))
    return total


def _calc_receive_dp(player: PlayerState) -> int:
    c = player.receive_zone.card
    return max(0, get_stat(c, "rcv")) if c else 0


def _calc_attack_op(player: PlayerState) -> int:
    tos_c = player.toss_zone.card
    atk_c = player.attack_zone.card
    tos = max(0, get_stat(tos_c, "tos")) if tos_c else 0
    atk = max(0, get_stat(atk_c, "atk")) if atk_c else 0
    return tos + atk


# ══════════════════════════════════════════════════════════════════════════════

class TurnFlow:
    def __init__(self, spectator=None, registry=None):
        from game_engine.spectator import Spectator
        self.spec = spectator or Spectator(speed=0, silent=True)
        self.registry = registry

    # ── 公開入口 ──────────────────────────────────────────────────────────────

    def run_full_game(self, state: GameState, ai1, ai2) -> int:
        """執行完整遊戲。回傳獲勝 player 編號（1 或 2）。"""
        # 初始化：洗牌 + 抽6張
        for player in (state.p1, state.p2):
            random.shuffle(player.pile)
            drawn = self._draw(player, _INITIAL_HAND, state)
            # SET ZONE: 實際規則是先放2張到SET區，但我們只追蹤 set_cards 計數
            # player.set_cards 已預設為 2

        self.spec.on_game_start(
            state.p1.name, state.p2.name,
            state.p1.school, state.p2.school,
        )

        # 隨機決定先發球方
        state.server_num = random.choice([1, 2])
        server_num = state.server_num

        rally_num = 0
        while not state.is_terminal():
            rally_num += 1
            state.round_num = rally_num
            state.turn = rally_num

            # 執行一個 rally
            loser_num = self._run_one_rally(state, ai1, ai2, server_num)
            winner_num = 3 - loser_num  # 1→2, 2→1

            loser  = state.p1 if loser_num  == 1 else state.p2
            winner = state.p1 if winner_num == 1 else state.p2

            self.spec.on_lost(loser_num, loser.set_cards)

            if loser.set_cards == 0:
                # 敗北條件成立
                state.game_over   = True
                state.game_winner = winner_num
                winner.set_score += 1
                self.spec.on_set_result(winner_num, state.p1.set_score, state.p2.set_score)
                break

            # INTERVAL
            loser.set_cards -= 1
            winner.set_score += 1
            self.spec.on_set_result(winner_num, state.p1.set_score, state.p2.set_score)
            self.spec.on_interval(winner_num, state.p1.set_score, state.p2.set_score)

            # 雙方補到 6 張
            self._interval_draw(state)

            # 勝者取得發球權
            server_num = winner_num
            state.server_num = server_num

            # 清場：攔網側翼已在 _block_phase 中清，主要清場地以利新 rally
            self._clear_attack_zones(state)

        total_turns = state.round_num
        self.spec.on_game_end(state.game_winner, total_turns)
        return state.game_winner or 0

    # ── Rally 流程 ────────────────────────────────────────────────────────────

    def _run_one_rally(
        self, state: GameState, ai1, ai2, server_num: int
    ) -> int:
        """執行一個 rally 直到 LOST。回傳敗者 player 編號。"""
        defender_num = 3 - server_num
        ai_map  = {1: ai1, 2: ai2}
        pl_map  = {1: state.p1, 2: state.p2}

        # SERVE PHASE（發球方固定只發球）
        self.spec.on_phase(server_num, "serve")
        loser = self._serve_phase(state, pl_map[server_num], ai_map[server_num], server_num)
        if loser:
            return loser

        # 交替回應：defender 先行動
        current_num = defender_num
        for _ in range(_MAX_TURNS_PER_RALLY):
            state.current_player = current_num
            self.spec.on_phase(current_num, "start")
            loser = self._respond_turn(state, pl_map[current_num], ai_map[current_num], current_num)
            if loser is not None:
                return loser
            current_num = 3 - current_num  # 換手

        # 超過安全上限 → 發球方判負
        return server_num

    def _serve_phase(
        self, state: GameState, server: PlayerState, ai, pnum: int
    ) -> int | None:
        """發球階段。回傳 None=成功；pnum=該方 LOST。"""
        # 檢查場地現有發球卡
        existing_srv = server.serve_zone.card
        existing_val = get_stat(existing_srv, "srv") if existing_srv else 0

        # AI 決定是否補發球角色
        new_card = ai.decide_serve_char(server, state)

        if new_card and new_card in server.hand and _can_deploy(new_card, "serve"):
            # 部署新卡
            server.hand.remove(new_card)
            self._deploy_to_zone(server, new_card, "serve")
            self.spec.on_deploy(pnum, new_card, get_name(new_card), "serve",
                               stats={"srv": get_stat(new_card, "srv")})
        elif not existing_srv:
            # 場地空且沒牌可打 → LOST
            return pnum

        op = _calc_serve_op(server)
        state.pending_op = op
        self.spec.on_action(pnum, "serve", op, 0, notes=f"OP={op}")
        self.spec.on_board_snapshot(self._make_snapshot(server, pnum))
        return None

    def _respond_turn(
        self, state: GameState, player: PlayerState, ai, pnum: int
    ) -> int | None:
        """選擇 BLOCK 或 RECEIVE。回傳 None=成功；pnum=該方 LOST。"""
        pending_op = state.pending_op

        choice = ai.decide_start_phase(player, state, pending_op)
        if choice == "block":
            return self._block_phase(state, player, ai, pnum, pending_op)
        else:
            return self._receive_sequence(state, player, ai, pnum, pending_op)

    def _block_phase(
        self, state: GameState, player: PlayerState, ai, pnum: int, pending_op: int
    ) -> int | None:
        self.spec.on_phase(pnum, "block")

        # 保留現有 center blocker；只補空位或換掉
        chars_to_deploy = ai.decide_block_chars(player, state, pending_op)
        for card_no in chars_to_deploy[:_ZONE_SLOTS]:
            if card_no not in player.hand:
                continue
            if not _can_deploy(card_no, "block"):
                continue
            player.hand.remove(card_no)
            self._deploy_to_zone(player, card_no, "block")
            self.spec.on_deploy(pnum, card_no, get_name(card_no), "block",
                               stats={"blk": get_stat(card_no, "blk")})

        dp = _calc_block_dp(player)
        did_lose = dp < pending_op
        self.spec.on_judge(pnum, "block", dp, pending_op, did_lose)
        self.spec.on_action(pnum, "block", dp, pending_op,
                           notes=f"DP(BLK)={dp} vs OP={pending_op}")
        self.spec.on_board_snapshot(self._make_snapshot(player, pnum))

        # 側邊攔網手退場（不論成敗）
        self._drop_side_blockers(player)

        if did_lose:
            return pnum

        # 攔網成功：OP 歸零（無 ドシャット 技能則為 0）
        state.pending_op = 0
        return None

    def _receive_sequence(
        self, state: GameState, player: PlayerState, ai, pnum: int, pending_op: int
    ) -> int | None:
        """RECEIVE → TOSS → ATTACK 序列。"""
        # 抽牌（レシーブドロー）
        drawn = self._draw(player, 1, state)
        for c in drawn:
            self.spec.on_draw(pnum, c, get_name(c))

        # RECEIVE PHASE
        self.spec.on_phase(pnum, "receive")
        rcv_card = ai.decide_receive_char(player, state, pending_op)

        existing_rcv = player.receive_zone.card
        if rcv_card and rcv_card in player.hand and _can_deploy(rcv_card, "receive"):
            player.hand.remove(rcv_card)
            self._deploy_to_zone(player, rcv_card, "receive")
            self.spec.on_deploy(pnum, rcv_card, get_name(rcv_card), "receive",
                               stats={"rcv": get_stat(rcv_card, "rcv")})
        elif not existing_rcv:
            return pnum  # 無牌可接 → LOST

        dp = _calc_receive_dp(player)
        did_lose = dp < pending_op
        self.spec.on_judge(pnum, "receive", dp, pending_op, did_lose)

        if did_lose:
            return pnum

        # TOSS PHASE
        self.spec.on_phase(pnum, "toss")
        tos_card = ai.decide_toss_char(player, state)
        if tos_card and tos_card in player.hand and _can_deploy(tos_card, "toss"):
            player.hand.remove(tos_card)
            self._deploy_to_zone(player, tos_card, "toss")
            self.spec.on_deploy(pnum, tos_card, get_name(tos_card), "toss",
                               stats={"tos": get_stat(tos_card, "tos")})

        # ATTACK PHASE
        self.spec.on_phase(pnum, "attack")
        atk_card = ai.decide_attack_char(player, state)
        if atk_card and atk_card in player.hand and _can_deploy(atk_card, "attack"):
            player.hand.remove(atk_card)
            self._deploy_to_zone(player, atk_card, "attack")
            self.spec.on_deploy(pnum, atk_card, get_name(atk_card), "attack",
                               stats={"atk": get_stat(atk_card, "atk")})

        new_op = _calc_attack_op(player)
        state.pending_op = new_op
        self.spec.on_action(pnum, "attack", new_op, 0, notes=f"TOS+ATK={new_op}")
        self.spec.on_board_snapshot(self._make_snapshot(player, pnum))
        return None

    # ── 工具函式 ──────────────────────────────────────────────────────────────

    def _draw(self, player: PlayerState, count: int, state: GameState) -> list[str]:
        drawn: list[str] = []
        for _ in range(count):
            if not player.pile:
                self._reshuffle_grave_to_pile(player, state)
            if player.pile:
                card = player.pile.pop()
                player.hand.append(card)
                drawn.append(card)
        return drawn

    def _reshuffle_grave_to_pile(self, player: PlayerState, state: GameState) -> None:
        if not player.grave:
            return
        state.log(f"{player.name} 棄牌區洗牌回牌庫")
        player.pile = list(player.grave)
        player.grave.clear()
        player._grave_char_counter.clear()
        player._grave_unique_count = 0
        random.shuffle(player.pile)

    def _deploy_to_zone(self, player: PlayerState, card_no: str, zone: str) -> None:
        zone = zone.lower()
        if zone == "serve":
            if player.serve_zone.card:
                self._to_grave(player, player.serve_zone.card)
            player.serve_zone = ZoneState(card=card_no)
        elif zone == "toss":
            if player.toss_zone.card:
                self._to_grave(player, player.toss_zone.card)
            player.toss_zone = ZoneState(card=card_no)
        elif zone == "attack":
            if player.attack_zone.card:
                self._to_grave(player, player.attack_zone.card)
            player.attack_zone = ZoneState(card=card_no)
        elif zone == "receive":
            if player.receive_zone.card:
                self._to_grave(player, player.receive_zone.card)
            player.receive_zone = ZoneState(card=card_no)
        elif zone == "block":
            # center (0) 先填，再填側邊
            if not player.block_zones[0].card:
                player.block_zones[0] = ZoneState(card=card_no)
            else:
                for i in range(1, 3):
                    if not player.block_zones[i].card:
                        player.block_zones[i] = ZoneState(card=card_no)
                        return
                # 全滿：覆蓋 side[1]
                self._to_grave(player, player.block_zones[1].card)
                player.block_zones[1] = ZoneState(card=card_no)

    def _to_grave(self, player: PlayerState, card_no: str | None) -> None:
        if not card_no:
            return
        player.grave.append(card_no)
        char_id = get_name(card_no) or card_no
        prev = player._grave_char_counter.get(char_id, 0)
        player._grave_char_counter[char_id] = prev + 1
        if prev == 0:
            player._grave_unique_count += 1

    def _drop_side_blockers(self, player: PlayerState) -> None:
        """BLOCK PHASE 後：側翼攔網手退場至棄牌區。"""
        for i in range(1, 3):
            if player.block_zones[i].card:
                self._to_grave(player, player.block_zones[i].card)
                player.block_zones[i] = ZoneState()

    def _interval_draw(self, state: GameState) -> None:
        """INTERVAL：雙方補到 6 張手牌。"""
        for pnum, player in [(1, state.p1), (2, state.p2)]:
            need = max(0, _INTERVAL_HAND_TARGET - len(player.hand))
            if need > 0:
                drawn = self._draw(player, need, state)
                for c in drawn:
                    self.spec.on_draw(pnum, c, get_name(c))

    def _clear_attack_zones(self, state: GameState) -> None:
        """
        INTERVAL 後清除攻擊、舉球、接球、發球區（規則上這些不自動清，
        但簡化處理：清掉場地以利 AI 重新部署）。
        攔網 center 保留。
        """
        for player in (state.p1, state.p2):
            for attr in ("serve_zone", "toss_zone", "attack_zone", "receive_zone"):
                z = getattr(player, attr)
                if z.card:
                    self._to_grave(player, z.card)
                    setattr(player, attr, ZoneState())

    def _make_snapshot(self, actor: PlayerState, pnum: int):
        from game_engine.spectator import BoardSnapshot

        def _cn(zone) -> str | None:
            return get_name(zone.card) if zone.card else None

        return BoardSnapshot(
            player=pnum,
            toss=_cn(actor.toss_zone),
            attack=_cn(actor.attack_zone),
            receive=_cn(actor.receive_zone),
            blocks=[get_name(bz.card) for bz in actor.block_zones if bz.card],
            serve=_cn(actor.serve_zone),
            hand_count=len(actor.hand),
            pile_count=len(actor.pile),
            grave_count=len(actor.grave),
            unique_grave=actor.unique_names_in_grave(),
            set_score=actor.set_score,
            set_cards=actor.set_cards,
        )


_ZONE_SLOTS = 3  # 攔網最多 3 格
