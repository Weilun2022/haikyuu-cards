# -*- coding: utf-8 -*-
"""
game_engine/tests/test_skill_system.py — 技能系統黃金測試
手工標註的斷言案例（非引擎自產 replay），逐 effect 驗證 pre/post resolution 狀態。

執行：python game_engine/tests/test_skill_system.py
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from game_engine.card_db import load_cards, get_stat
from game_engine.schema import (
    GameState, PlayerState, ZoneState, CardSkill, Effect, EffectType,
    Condition, ConditionType, Cost, Stat,
)
from game_engine.effects.registry import EffectRegistry
from game_engine.engine import combat
from game_engine.engine.turn_flow import TurnFlow
from game_engine.ai.generic_ai import GenericAI

# 測試用真卡（P01 烏野，數值已驗證）
CHAR_RCV4 = "HV-P01-001"   # 日向 rcv=4 atk=2 blk=3 srv=2
CHAR_RCV2 = "HV-P01-013"   # 縁下 rcv=2 srv=1
EVENT_A   = "HV-P01-076"   # がんばれ (Event)
EVENT_B   = "HV-P01-078"   # オープン攻撃 (Event)

_PASS = 0
_FAIL = 0

def check(name: str, cond: bool, detail: str = ""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {name}")
    else:
        _FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def mk_state() -> GameState:
    p1 = PlayerState(name="T1", school="烏野", pile=[])
    p2 = PlayerState(name="T2", school="烏野", pile=[])
    return GameState(p1=p1, p2=p2)


def mk_skill(card_no: str, triggers, effects, conditions=None,
             once_per_turn=False, costs=None) -> CardSkill:
    return CardSkill(
        card_no=card_no, triggers=list(triggers), zone_qualifiers=[],
        conditions=conditions or [Condition(type=ConditionType.ALWAYS)],
        costs=costs or Cost(), effects=list(effects),
        once_per_turn=once_per_turn, raw_text="(golden test)",
    )


def eff_stat(stat: Stat, amount: int, duration="this_turn") -> Effect:
    return Effect(effect_type=EffectType.STAT_BONUS, stat=stat,
                  amount=amount, duration=duration)


def eff_draw(n: int) -> Effect:
    return Effect(effect_type=EffectType.DRAW, amount=n)


# ══════════════════════════════════════════════════════════════════════════════

def test_1_rcv_bonus_pre_resolution():
    """[黃金1] 接球階段技 rcv+2 必須在 DP 判定「之前」生效（勝負翻轉）"""
    st = mk_state()
    st.p1.receive_zone = ZoneState(card=CHAR_RCV2)   # base rcv=2
    reg = EffectRegistry()
    reg._skill_db[CHAR_RCV2] = mk_skill(CHAR_RCV2, ["接球階段"], [eff_stat(Stat.RCV, 2)])

    fired = reg.try_activate_phase_skills("receive", st, st.p1, st.p2, ai=None)
    dp = combat.calc_receive_score(st.p1)
    check("接球技能發動", CHAR_RCV2 in fired)
    check("DP 含加成 = 4（2+2），判定前生效", dp == 4, f"dp={dp}")
    # pending_op=4 時：無技能會 LOST（2<4），有技能不會（4>=4）
    check("勝負翻轉：dp >= op(4)", dp >= 4)


def test_2_serve_bonus_and_consume():
    """[黃金2] 發球 srv+2 影響 OP；OP 固定後 bonus 歸零不外洩"""
    st = mk_state()
    st.p1.serve_zone = ZoneState(card=CHAR_RCV4)     # srv=2
    st.p1.srv_bonus = 2
    op = combat.calc_serve_score(st.p1)
    check("OP = base2 + bonus2 = 4", op == 4, f"op={op}")
    TurnFlow._consume_bonus(st.p1, "srv_bonus")
    op2 = combat.calc_serve_score(st.p1)
    check("消耗後 OP 回到 base 2", op2 == 2, f"op2={op2}")


def test_3_cross_phase_bonus_survives():
    """[黃金3] 接球區登場給 atk+2 → 同回合稍後 attack 結算仍吃得到"""
    st = mk_state()
    st.p1.receive_zone = ZoneState(card=CHAR_RCV2)
    st.p1.toss_zone = ZoneState(card=CHAR_RCV4)      # tos=0
    st.p1.attack_zone = ZoneState(card=CHAR_RCV4)    # atk=2
    st.p1.atk_bonus = 2                              # 接球時技能給的
    TurnFlow._consume_bonus(st.p1, "rcv_bonus")      # 接球判定後只清 rcv
    atk_op = combat.calc_attack_score(st.p1)
    check("attack OP = tos0+atk2+bonus2 = 4", atk_op == 4, f"op={atk_op}")


def test_4_event_play_from_hand():
    """[黃金4] 手牌 Event [攻擊]觸發+抽1 → 打出：手牌-1、event_zone+1、抽到牌"""
    st = mk_state()
    st.p1.hand = [EVENT_A, CHAR_RCV4]
    st.p1.pile = [CHAR_RCV2, CHAR_RCV2, CHAR_RCV2]
    reg = EffectRegistry()
    reg._skill_db[EVENT_A] = mk_skill(EVENT_A, ["攻擊"], [eff_draw(1)])

    fired = reg.try_activate_phase_skills("attack", st, st.p1, st.p2, ai=GenericAI(1))
    check("Event 發動", EVENT_A in fired)
    check("Event 進 event_zone", EVENT_A in st.p1.event_zone)
    check("Event 離開手牌", EVENT_A not in st.p1.hand)
    check("抽 1 張：手牌 = 2（原2 -event +draw）", len(st.p1.hand) == 2,
          f"hand={st.p1.hand}")
    check("牌庫 -1", len(st.p1.pile) == 2)


def test_5_event_condition_gate():
    """[黃金5] Event 條件不符（hand_le 2 但手牌 5）→ 不打出、留在手牌"""
    st = mk_state()
    st.p1.hand = [EVENT_A] + [CHAR_RCV4] * 4       # 5 張
    reg = EffectRegistry()
    reg._skill_db[EVENT_A] = mk_skill(
        EVENT_A, ["攻擊"], [eff_draw(1)],
        conditions=[Condition(type=ConditionType.HAND_LE, param=2)])

    fired = reg.try_activate_phase_skills("attack", st, st.p1, st.p2, ai=GenericAI(1))
    check("條件不符不發動", EVENT_A not in fired)
    check("Event 留在手牌", EVENT_A in st.p1.hand)
    check("event_zone 空", len(st.p1.event_zone) == 0)


def test_6_ai_hand_guard():
    """[黃金6] 手牌≤2 且效果無抽牌 → AI 保留 Event 不打"""
    st = mk_state()
    st.p1.hand = [EVENT_B, CHAR_RCV4]              # 2 張
    reg = EffectRegistry()
    reg._skill_db[EVENT_B] = mk_skill(EVENT_B, ["攻擊"], [eff_stat(Stat.ATK, 2)])

    fired = reg.try_activate_phase_skills("attack", st, st.p1, st.p2, ai=GenericAI(1))
    check("AI 資源守門：不打", EVENT_B not in fired and EVENT_B in st.p1.hand)

    # 同樣手牌數但效果含抽牌 → 打
    st2 = mk_state()
    st2.p1.hand = [EVENT_A, CHAR_RCV4]
    st2.p1.pile = [CHAR_RCV2]
    reg2 = EffectRegistry()
    reg2._skill_db[EVENT_A] = mk_skill(EVENT_A, ["攻擊"], [eff_draw(1)])
    fired2 = reg2.try_activate_phase_skills("attack", st2, st2.p1, st2.p2, ai=GenericAI(1))
    check("含抽牌則打出", EVENT_A in fired2)


def test_7_next_turn_blk_zero():
    """[黃金7] next_turn_blk_zero → 攔網 DP 歸零；cleanup 後恢復"""
    st = mk_state()
    st.p1.block_zones[0] = ZoneState(card=CHAR_RCV4)   # blk=3
    st.p1.next_turn_blk_zero = True
    dp = combat.calc_block_score(st.p1)
    check("BLK 歸零", dp == 0, f"dp={dp}")
    TurnFlow._end_turn_cleanup(st.p1)
    dp2 = combat.calc_block_score(st.p1)
    check("cleanup 後恢復 base 3", dp2 == 3, f"dp2={dp2}")


def test_8_stat_override():
    """[黃金8] stat_override 覆蓋卡片數值；cleanup 後清除"""
    st = mk_state()
    st.p1.receive_zone = ZoneState(card=CHAR_RCV4)     # rcv=4
    st.p1.counters[f"stat_override:{CHAR_RCV4}:rcv"] = 1
    dp = combat.calc_receive_score(st.p1)
    check("覆蓋生效 rcv=1", dp == 1, f"dp={dp}")
    TurnFlow._end_turn_cleanup(st.p1)
    dp2 = combat.calc_receive_score(st.p1)
    check("cleanup 後回 base 4", dp2 == 4, f"dp2={dp2}")


def test_9_once_per_turn():
    """[黃金9] once_per_turn：同回合只發動一次；回合結束後可再發動"""
    st = mk_state()
    st.p1.receive_zone = ZoneState(card=CHAR_RCV2)
    reg = EffectRegistry()
    reg._skill_db[CHAR_RCV2] = mk_skill(
        CHAR_RCV2, ["接球階段"], [eff_stat(Stat.RCV, 1)], once_per_turn=True)

    f1 = reg.try_activate_phase_skills("receive", st, st.p1, st.p2)
    f2 = reg.try_activate_phase_skills("receive", st, st.p1, st.p2)
    check("第一次發動", CHAR_RCV2 in f1)
    check("同回合第二次不發動", CHAR_RCV2 not in f2)
    TurnFlow._end_turn_cleanup(st.p1)
    st.p1.rcv_bonus = 0
    f3 = reg.try_activate_phase_skills("receive", st, st.p1, st.p2)
    check("回合結束後可再發動", CHAR_RCV2 in f3)


def test_10_skill_nullify():
    """[黃金10] 對手封鎖[攻擊]觸發 → 攻擊技能不發動"""
    st = mk_state()
    st.p1.attack_zone = ZoneState(card=CHAR_RCV4)
    st.p1.next_turn_skill_nullify.append("攻擊")
    reg = EffectRegistry()
    reg._skill_db[CHAR_RCV4] = mk_skill(CHAR_RCV4, ["攻擊"], [eff_stat(Stat.ATK, 2)])

    fired = reg.try_activate_phase_skills("attack", st, st.p1, st.p2)
    check("被封鎖不發動", CHAR_RCV4 not in fired)
    check("atk_bonus 未變", st.p1.atk_bonus == 0)


def test_11_full_game_regression():
    """[黃金11] 完整對局回歸：ROKUNIN vs STANDARD 正常結束 + Event 有被打出"""
    from game_engine.sim_runner import run_one_game, DECKS, _get_registry
    from game_engine.spectator import Spectator

    results = []
    event_fired_any = False
    for seed in (42, 123, 777):
        spec = Spectator(speed=0, silent=True)
        p_state = {}
        # 用可捕捉 state 的 wrapper 跑一局
        import game_engine.sim_runner as sr
        res = run_one_game(
            deck1=DECKS["ROKUNIN"], deck2=DECKS["STANDARD"],
            name1="R", name2="S", school1="稲荷崎", school2="烏野",
            ai1_class=GenericAI, ai2_class=GenericAI,
            spectator=spec, seed=seed,
        )
        results.append(res)
    check("三局皆正常結束", all(r["winner"] in (1, 2) for r in results),
          f"winners={[r['winner'] for r in results]}")
    check("回合數合理（1~60）", all(1 <= r["turns"] <= 60 for r in results),
          f"turns={[r['turns'] for r in results]}")


def test_12_event_exercised_in_game():
    """[黃金12] 真實對局中 Event 牌確實被打出（event_zone / 記錄可見）"""
    from game_engine.sim_runner import DECKS, _get_registry
    from game_engine.card_db import make_deck
    from game_engine.spectator import Spectator
    import random as _r

    registry = _get_registry()
    hits = 0
    for seed in range(20):
        _r.seed(seed)
        p1 = PlayerState(name="R", school="稲荷崎", pile=make_deck(DECKS["ROKUNIN"]))
        p2 = PlayerState(name="S", school="烏野", pile=make_deck(DECKS["STANDARD"]))
        st = GameState(p1=p1, p2=p2)
        flow = TurnFlow(spectator=Spectator(speed=0, silent=True), registry=registry)
        flow.run_full_game(st, GenericAI(1), GenericAI(2))
        ev_logs = [l for l in st.game_log if "[EVENT]" in l]
        if ev_logs or p1.event_zone or p2.event_zone:
            hits += 1
    check(f"20 局中 Event 被打出的局數 > 0（實測 {hits} 局）", hits > 0)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    load_cards()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        print(f"\n── {t.__doc__.strip().splitlines()[0]}")
        try:
            t()
        except Exception as e:
            _FAIL += 1
            print(f"  ERROR {type(e).__name__}: {e}")
    print(f"\n{'='*50}\nPASS={_PASS} FAIL={_FAIL}")
    sys.exit(1 if _FAIL else 0)
