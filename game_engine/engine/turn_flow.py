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

            # 規則：INTERVAL 後各 zone 不清場，卡牌留在場地（下次強制登場時覆蓋）

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

        # 每個 rally 重置 ABA 追蹤
        state.last_deployed_name = None

        # SERVE PHASE（發球方固定只發球）
        self.spec.on_phase(server_num, "serve")
        loser = self._serve_phase(state, pl_map[server_num], ai_map[server_num], server_num)
        if loser:
            return loser

        # 規則：發球後對方只能 RECEIVE（不能選 BLOCK）
        current_num = defender_num
        state.current_player = current_num
        self.spec.on_phase(current_num, "start")
        loser = self._receive_sequence(state, pl_map[current_num], ai_map[current_num], current_num, state.pending_op)
        if loser is not None:
            return loser
        current_num = 3 - current_num

        # 後續回合：可選 BLOCK 或 RECEIVE
        for _ in range(_MAX_TURNS_PER_RALLY - 1):
            state.current_player = current_num
            self.spec.on_phase(current_num, "start")
            loser = self._respond_turn(state, pl_map[current_num], ai_map[current_num], current_num)
            if loser is not None:
                return loser
            current_num = 3 - current_num  # 換手

        # 超過安全上限 → 發球方判負
        return server_num

    def _try_skill(
        self, card_no: str, zone: str,
        state: GameState, actor: PlayerState, passive: PlayerState, ai=None,
    ) -> bool:
        """部署後嘗試觸發 [登場] 技能。例外靜默記錄。"""
        if not self.registry:
            return False
        try:
            fired = self.registry.try_activate_deploy_skill(
                card_no=card_no, deploy_zone=zone, deploy_via_skill=False,
                state=state, actor=actor, passive=passive, ai=ai,
            )
            if fired:
                state.log(f"[SKILL] {card_no}@{zone}")
            return fired
        except Exception as e:
            state.log(f"[SKILL ERR] {card_no}@{zone}: {e}")
            return False

    def _serve_phase(
        self, state: GameState, server: PlayerState, ai, pnum: int
    ) -> int | None:
        """發球階段。回傳 None=成功；pnum=該方 LOST。"""
        existing_srv = server.serve_zone.card

        new_card = ai.decide_serve_char(server, state)

        if new_card and new_card in server.hand and _can_deploy(new_card, "serve"):
            if self._aba_ok(new_card, state):
                server.hand.remove(new_card)
                self._deploy_to_zone(server, new_card, "serve")
                state.last_deployed_name = get_name(new_card)
                self.spec.on_deploy(pnum, new_card, get_name(new_card), "serve",
                                   stats={"srv": get_stat(new_card, "srv")})
                passive = state.p2 if pnum == 1 else state.p1
                state.current_player = pnum
                self._try_skill(new_card, "serve", state, server, passive, ai)
            # ABA 違規：保留現有卡，不更新 last_deployed_name
        elif not existing_srv:
            return pnum  # 場地空且無可部署 → LOST

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

        chars_to_deploy = ai.decide_block_chars(player, state, pending_op)

        # 攔網唯一性：收集場上已有的攔網角色名（center 會持續留場）
        in_zone_names: set[str] = set()
        for bz in player.block_zones:
            if bz.card:
                in_zone_names.add(get_name(bz.card))

        deployed_count = 0
        passive = state.p2 if pnum == 1 else state.p1
        state.current_player = pnum
        for card_no in chars_to_deploy[:_ZONE_SLOTS]:
            if card_no not in player.hand:
                continue
            if not _can_deploy(card_no, "block"):
                continue
            name = get_name(card_no)
            if name in in_zone_names:
                continue  # 攔網唯一性：同名角色已在場上
            if not self._aba_ok(card_no, state):
                continue  # ABA規則
            player.hand.remove(card_no)
            self._deploy_to_zone(player, card_no, "block")
            in_zone_names.add(name)
            state.last_deployed_name = name
            self.spec.on_deploy(pnum, card_no, name, "block",
                               stats={"blk": get_stat(card_no, "blk")})
            self._try_skill(card_no, "block", state, player, passive, ai)
            deployed_count += 1

        # 規則 5-7-2②：登場步驟若未部署任何角色 → 宣告 LOST
        if deployed_count == 0:
            self._drop_side_blockers(player)
            return pnum

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
        """RECEIVE → TOSS → ATTACK 序列。各步驟均強制從手牌部署，否則 LOST。"""
        # ドローフェイズ（抽 1 張）
        drawn = self._draw(player, 1, state)
        for c in drawn:
            self.spec.on_draw(pnum, c, get_name(c))

        passive = state.p2 if pnum == 1 else state.p1
        state.current_player = pnum

        # RECEIVE PHASE（強制部署，ABA合規）
        self.spec.on_phase(pnum, "receive")
        rcv_card = self._select_deploy(ai.decide_receive_char(player, state, pending_op),
                                       player.hand, "receive", state)
        if not rcv_card:
            return pnum  # 無合規接球角色 → LOST
        player.hand.remove(rcv_card)
        self._deploy_to_zone(player, rcv_card, "receive")
        state.last_deployed_name = get_name(rcv_card)
        self.spec.on_deploy(pnum, rcv_card, get_name(rcv_card), "receive",
                           stats={"rcv": get_stat(rcv_card, "rcv")})
        self._try_skill(rcv_card, "receive", state, player, passive, ai)

        dp = _calc_receive_dp(player)
        did_lose = dp < pending_op
        self.spec.on_judge(pnum, "receive", dp, pending_op, did_lose)
        if did_lose:
            return pnum

        # TOSS PHASE（強制部署，ABA合規）
        self.spec.on_phase(pnum, "toss")
        tos_card = self._select_deploy(ai.decide_toss_char(player, state),
                                       player.hand, "toss", state)
        if not tos_card:
            return pnum  # 無合規舉球角色 → LOST
        player.hand.remove(tos_card)
        self._deploy_to_zone(player, tos_card, "toss")
        state.last_deployed_name = get_name(tos_card)
        self.spec.on_deploy(pnum, tos_card, get_name(tos_card), "toss",
                           stats={"tos": get_stat(tos_card, "tos")})
        self._try_skill(tos_card, "toss", state, player, passive, ai)

        # ATTACK PHASE（強制部署，ABA合規）
        self.spec.on_phase(pnum, "attack")
        atk_card = self._select_deploy(ai.decide_attack_char(player, state),
                                       player.hand, "attack", state)
        if not atk_card:
            return pnum  # 無合規攻擊角色 → LOST
        player.hand.remove(atk_card)
        self._deploy_to_zone(player, atk_card, "attack")
        state.last_deployed_name = get_name(atk_card)
        self.spec.on_deploy(pnum, atk_card, get_name(atk_card), "attack",
                           stats={"atk": get_stat(atk_card, "atk")})
        self._try_skill(atk_card, "attack", state, player, passive, ai)

        new_op = _calc_attack_op(player)
        state.pending_op = new_op
        self.spec.on_action(pnum, "attack", new_op, 0, notes=f"TOS+ATK={new_op}")
        self.spec.on_board_snapshot(self._make_snapshot(player, pnum))
        return None

    # ── ABA / 部署選擇 helper ──────────────────────────────────────────────────

    def _aba_ok(self, card_no: str, state: GameState) -> bool:
        """ABA規則：出場角色名稱不得與上一位出場角色相同。"""
        if state.last_deployed_name is None:
            return True
        return get_name(card_no) != state.last_deployed_name

    def _select_deploy(
        self, ai_choice: str | None, hand: list[str], zone: str, state: GameState
    ) -> str | None:
        """
        強制部署用：從手牌找 ABA 合規且可出場的角色。
        優先採 ai_choice；若違反 ABA 或不在手中，改選 stat 最高的合規角色。
        無合規角色時回傳 None（→ LOST）。
        """
        stat_key = _ZONE_STAT.get(zone, "atk")
        eligible = [c for c in hand if _can_deploy(c, zone) and self._aba_ok(c, state)]
        if not eligible:
            return None
        if ai_choice in eligible:
            return ai_choice
        return max(eligible, key=lambda c: get_stat(c, stat_key))

    # ── 工具函式 ──────────────────────────────────────────────────────────────

    def _draw(self, player: PlayerState, count: int, state: GameState) -> list[str]:
        drawn: list[str] = []
        for _ in range(count):
            if player.pile:  # 牌庫空 → 無法抽牌（規則 ドロップエリア 不洗回牌庫）
                card = player.pile.pop()
                player.hand.append(card)
                drawn.append(card)
        return drawn

    def _deploy_to_zone(self, player: PlayerState, card_no: str, zone: str) -> None:
        """部署角色到指定區域。被替換的角色壓入該區 Guts（不進棄牌）。"""
        zone = zone.lower()
        if zone == "serve":
            old = player.serve_zone
            new_guts = old.guts[:]
            if old.card:
                new_guts.insert(0, old.card)  # 舊角色 → guts 頂
            player.serve_zone = ZoneState(card=card_no, guts=new_guts)
            player.g_serve = len(new_guts)
        elif zone == "toss":
            old = player.toss_zone
            new_guts = old.guts[:]
            if old.card:
                new_guts.insert(0, old.card)
            player.toss_zone = ZoneState(card=card_no, guts=new_guts)
            player.g_toss = len(new_guts)
        elif zone == "attack":
            old = player.attack_zone
            new_guts = old.guts[:]
            if old.card:
                new_guts.insert(0, old.card)
            player.attack_zone = ZoneState(card=card_no, guts=new_guts)
            player.g_attack = len(new_guts)
        elif zone == "receive":
            old = player.receive_zone
            new_guts = old.guts[:]
            if old.card:
                new_guts.insert(0, old.card)
            player.receive_zone = ZoneState(card=card_no, guts=new_guts)
            player.g_receive = len(new_guts)
        elif zone == "block":
            # center (0) 先填，再填側邊
            if not player.block_zones[0].card:
                player.block_zones[0] = ZoneState(card=card_no)
            else:
                for i in range(1, 3):
                    if not player.block_zones[i].card:
                        player.block_zones[i] = ZoneState(card=card_no)
                        player.g_block = sum(len(bz.guts) for bz in player.block_zones)
                        return
                # 全滿：覆蓋 side[1]，舊角色壓入 guts
                old = player.block_zones[1]
                new_guts = old.guts[:]
                if old.card:
                    new_guts.insert(0, old.card)
                player.block_zones[1] = ZoneState(card=card_no, guts=new_guts)
                player.g_block = sum(len(bz.guts) for bz in player.block_zones)

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
        """BLOCK PHASE 後：側翼攔網手連同其 Guts 一起退場至棄牌區。"""
        for i in range(1, 3):
            if player.block_zones[i].card:
                # 先清 Guts → 棄牌
                for g in player.block_zones[i].guts:
                    self._to_grave(player, g)
                # 角色本身 → 棄牌
                self._to_grave(player, player.block_zones[i].card)
                player.block_zones[i] = ZoneState()
        player.g_block = sum(len(bz.guts) for bz in player.block_zones)

    def _interval_draw(self, state: GameState) -> None:
        """INTERVAL：雙方補到 6 張手牌。"""
        for pnum, player in [(1, state.p1), (2, state.p2)]:
            need = max(0, _INTERVAL_HAND_TARGET - len(player.hand))
            if need > 0:
                drawn = self._draw(player, need, state)
                for c in drawn:
                    self.spec.on_draw(pnum, c, get_name(c))

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
            serve_guts=len(actor.serve_zone.guts),
            receive_guts=len(actor.receive_zone.guts),
            toss_guts=len(actor.toss_zone.guts),
            attack_guts=len(actor.attack_zone.guts),
            block_guts=sum(len(bz.guts) for bz in actor.block_zones),
            serve_no=actor.serve_zone.card,
            receive_no=actor.receive_zone.card,
            toss_no=actor.toss_zone.card,
            attack_no=actor.attack_zone.card,
            block_nos=[bz.card for bz in actor.block_zones],
            serve_guts_nos=list(actor.serve_zone.guts),
            receive_guts_nos=list(actor.receive_zone.guts),
            toss_guts_nos=list(actor.toss_zone.guts),
            attack_guts_nos=list(actor.attack_zone.guts),
            block_guts_nos=[list(bz.guts) for bz in actor.block_zones],
        )


_ZONE_SLOTS = 3  # 攔網最多 3 格
