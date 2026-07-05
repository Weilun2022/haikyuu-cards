"""
game_engine/effects/handlers/opponent.py
效果處理器：針對對手的各種效果

覆蓋 EffectType:
  OPP_DISCARD_FROM_EVENT  — 棄置對手 Event 區牌
  OPP_STAT_REDUCE         — 降低對手角色數值
  OPP_STAT_SET            — 設定對手角色數值
  OPP_BLK_ZERO            — 對手下回合 MB 攔網歸零
  OPP_ZONE_LOCK           — 限制對手下回合出場 / 技能
  OPP_SKILL_NULLIFY       — 無效化對手特定技能
  OPP_PHASE_MODIFY        — 修改對手下回合階段數值
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game_engine.schema import Effect, GameState, PlayerState


# ─── helpers ────────────────────────────────────────────────

def _get_zone_state(opponent: "PlayerState", zone_name: str):
    """按名稱取得對手 ZoneState（block 取第一個有牌的格）。"""
    zone_map = {
        "serve":   opponent.serve_zone,
        "toss":    opponent.toss_zone,
        "attack":  opponent.attack_zone,
        "receive": opponent.receive_zone,
    }
    if zone_name in zone_map:
        return zone_map[zone_name]
    if zone_name == "block":
        # 取第一個有角色的 block slot
        for slot in opponent.block_zones:
            if slot.card is not None:
                return slot
    return None


def _resolve_stat_attr(stat_str: str) -> str | None:
    """將 Stat 字串對應到 PlayerState 上的 _bonus 屬性名稱。"""
    mapping = {
        "atk": "atk_bonus",
        "rcv": "rcv_bonus",
        "blk": "blk_bonus",
        "tos": "tos_bonus",
        "srv": "srv_bonus",
    }
    return mapping.get(stat_str.lower() if stat_str else "")


# ─── OPP_DISCARD_FROM_EVENT ─────────────────────────────────

def apply_opp_discard_from_event(
    effect: "Effect",
    state: "GameState",
    actor: "PlayerState",
    opponent: "PlayerState",
    *,
    chosen_indices: list[int] | None = None,
) -> list[str]:
    """
    從對手 Event 區棄置 N 張牌，由發動玩家選擇目標。

    Parameters
    ----------
    chosen_indices : list[int] | None
        呼叫方傳入的選擇索引（0-based）。
        若為 None 或空，自動棄置最前面的 N 張（AI fallback）。

    Returns
    -------
    list[str]
        被棄置的 card_no 列表。
    """
    n = max(0, effect.amount)
    if n == 0 or not opponent.event_zone:
        return []

    available = list(range(len(opponent.event_zone)))
    if chosen_indices:
        # 只取合法索引，並限定最多 n 張
        valid = [i for i in chosen_indices if 0 <= i < len(opponent.event_zone)]
        to_discard_idx = valid[:n]
    else:
        to_discard_idx = available[:n]

    # 從後往前刪，避免索引位移
    discarded: list[str] = []
    for idx in sorted(to_discard_idx, reverse=True):
        card_no = opponent.event_zone.pop(idx)
        opponent.grave.append(card_no)
        discarded.append(card_no)

    state.log(
        f"對手 Event 區棄置 {len(discarded)} 張: {discarded}"
    )
    return discarded


# ─── OPP_STAT_REDUCE ────────────────────────────────────────

def apply_opp_stat_reduce(
    effect: "Effect",
    state: "GameState",
    actor: "PlayerState",
    opponent: "PlayerState",
) -> None:
    """
    降低對手指定區域角色的數值。

    effect.stat      : 要降低的數值 (Stat enum / str)
    effect.amount    : 降低量（正整數）
    effect.duration  : "this_turn" 本回合 | "next_turn" 下回合 | "permanent"
    effect.zone      : 受影響的對手區域（字串，如 "attack"）

    目前實作將 bonus 套在 PlayerState 的 *_bonus 欄位，
    「next_turn」則推入 opponent.counters["pending_stat_reduce"]，
    由 turn_flow 在對手回合開始時套用。
    """
    stat_str = effect.stat.value if effect.stat else "atk"
    amount   = max(0, effect.amount)
    duration = effect.duration or "this_turn"

    if duration == "next_turn":
        # 延遲：存入 counters，由 turn_flow 在對手回合開始套用
        pending = opponent.counters.setdefault("pending_stat_reduce", [])
        pending.append({
            "stat":   stat_str,
            "amount": amount,
            "zone":   str(effect.zone) if effect.zone else None,
        })
        state.log(
            f"對手下回合 {stat_str.upper()} -{amount}"
            + (f"（{effect.zone}）" if effect.zone else "")
        )
    else:
        # 立即套用（this_turn / permanent）
        attr = _resolve_stat_attr(stat_str)
        if attr and hasattr(opponent, attr):
            current = getattr(opponent, attr)
            setattr(opponent, attr, current - amount)
            state.log(
                f"對手 {stat_str.upper()} -{amount}"
                + (f"（{duration}）" if duration != "permanent" else "")
            )
        else:
            state.log(f"[WARN] OPP_STAT_REDUCE: 未知 stat={stat_str}")


# ─── OPP_STAT_SET ───────────────────────────────────────────

def apply_opp_stat_set(
    effect: "Effect",
    state: "GameState",
    actor: "PlayerState",
    opponent: "PlayerState",
) -> None:
    """
    將對手指定角色的數值強制設為特定值。

    常見用例：
      - 對手舉球手 TOS = 0
      - 對手攔網手 BLK = 0

    實作方式：計算「目前有效值 → 目標值」的差，再調整 *_bonus。
    若 card_db 可取，可直接查卡片基礎值；此處保守地以 bonus 調整。

    effect.stat   : 目標數值
    effect.amount : 設定為的值
    effect.zone   : 受影響的對手區域（字串）
    """
    stat_str = effect.stat.value if effect.stat else "blk"
    target   = effect.amount
    duration = effect.duration or "this_turn"

    if duration == "next_turn":
        pending = opponent.counters.setdefault("pending_stat_set", [])
        pending.append({
            "stat":   stat_str,
            "target": target,
            "zone":   str(effect.zone) if effect.zone else None,
        })
        state.log(
            f"對手下回合 {stat_str.upper()} 設為 {target}"
            + (f"（{effect.zone}）" if effect.zone else "")
        )
    else:
        # 立即：將 bonus 調成使有效值 = target
        # 有效值 = base + bonus；此處保守地記錄「絕對覆蓋」flag
        attr = _resolve_stat_attr(stat_str)
        override_key = f"stat_override_{stat_str}"
        opponent.counters[override_key] = target
        state.log(
            f"對手 {stat_str.upper()} 強制設為 {target}"
            + (f"（{duration}）" if duration != "permanent" else "")
        )


# ─── OPP_BLK_ZERO ───────────────────────────────────────────

def apply_opp_blk_zero(
    effect: "Effect",
    state: "GameState",
    actor: "PlayerState",
    opponent: "PlayerState",
) -> None:
    """
    對手下回合 MB（中間攔網手）攔網值視為 0。
    設定 opponent.next_turn_blk_zero = True。
    """
    opponent.next_turn_blk_zero = True
    state.log("對手下回合 MB 攔網無效（BLK=0）")


# ─── OPP_ZONE_LOCK ──────────────────────────────────────────

def apply_opp_zone_lock(
    effect: "Effect",
    state: "GameState",
    actor: "PlayerState",
    opponent: "PlayerState",
) -> None:
    """
    限制對手下回合特定區域的出場規則。
    將限制規則寫入 opponent.next_turn_zone_lock。

    effect.zone        : 受限制的區域名稱（"block" / "receive" / "attack" 等）
    effect.card_filter : 用於指定更細的篩選條件
    effect.amount      : max_count 或門檻值 N（依 card_filter 語意決定）

    next_turn_zone_lock 結構（由 turn_flow.py 讀取）:
      {
          "block":   {"max_count": 2},
          "receive": {"rcv_ge": 5, "forbidden": True},
          ...
      }

    內建支援的限制語意：
      max_count  — 最多可出場 N 名
      forbidden  — 滿足 card_filter 條件的角色禁止出場
      rcv_ge     — 接球值 ≥ N 的角色禁止出場（配合 forbidden）
      atk_ge     — 攻擊值 ≥ N 的角色禁止出場
    """
    zone_name = str(effect.zone) if effect.zone else "block"

    rule: dict = {}

    cf = effect.card_filter
    # max_count 語意：effect.amount 直接作為上限
    if effect.amount > 0:
        rule["max_count"] = effect.amount

    # 透過 card_filter 推斷額外限制
    if cf:
        # 接球值 ≥ N → 禁止出場
        if cf.rarity and cf.rarity.startswith("rcv_ge:"):
            rule["rcv_ge"]   = int(cf.rarity.split(":")[-1])
            rule["forbidden"] = True
        # 也可以用 name 欄位傳遞特殊限制 key=value 字串
        # e.g. card_filter.name = "rcv_ge:5"
        if cf.name and ":" in cf.name:
            key, val = cf.name.split(":", 1)
            try:
                rule[key] = int(val)
            except ValueError:
                rule[key] = val

    if rule:
        # 若同一區域已有 lock，合併（AND 語意）
        existing = opponent.next_turn_zone_lock.get(zone_name, {})
        existing.update(rule)
        opponent.next_turn_zone_lock[zone_name] = existing
        state.log(f"對手下回合 [{zone_name}] 出場限制: {existing}")
    else:
        state.log(f"[WARN] OPP_ZONE_LOCK: zone={zone_name} 無有效規則，effect 被忽略")


# ─── OPP_SKILL_NULLIFY ──────────────────────────────────────

def apply_opp_skill_nullify(
    effect: "Effect",
    state: "GameState",
    actor: "PlayerState",
    opponent: "PlayerState",
) -> None:
    """
    無效化對手特定技能（下回合生效）。

    effect.phase : 要無效化的技能標籤字串
                   e.g. "[=一觸(N)]", "[=接球階段][=手牌]"
                   也可用逗號分隔多個標籤。

    將標籤追加至 opponent.next_turn_skill_nullify（list[str]）。
    turn_flow.py 在對手技能觸發時查此列表進行攔截。
    """
    tags_raw = effect.phase or ""
    # 支援逗號分隔多標籤
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    if not tags:
        state.log("[WARN] OPP_SKILL_NULLIFY: phase 為空，無效果")
        return

    for tag in tags:
        if tag not in opponent.next_turn_skill_nullify:
            opponent.next_turn_skill_nullify.append(tag)

    state.log(f"對手下回合以下技能無效: {tags}")


# ─── OPP_PHASE_MODIFY ───────────────────────────────────────

def apply_opp_phase_modify(
    effect: "Effect",
    state: "GameState",
    actor: "PlayerState",
    opponent: "PlayerState",
) -> None:
    """
    修改對手下回合某階段的數值（如舉球手部署後對手 TOS -2）。

    effect.stat   : 受影響的數值
    effect.amount : 修改量（負數 = 降低，正數 = 提升）
    effect.phase  : 生效階段名稱（e.g. "toss"，由 turn_flow 識別）
    effect.duration : "next_turn"（幾乎固定）

    推入 opponent.counters["pending_phase_modify"]，
    由 turn_flow.py 在進入對應階段時套用。
    """
    stat_str  = effect.stat.value if effect.stat else ""
    amount    = effect.amount
    phase_str = effect.phase or ""
    duration  = effect.duration or "next_turn"

    if not stat_str:
        state.log("[WARN] OPP_PHASE_MODIFY: 未指定 stat")
        return

    entry = {
        "stat":     stat_str,
        "amount":   amount,
        "phase":    phase_str,
        "duration": duration,
    }
    pending = opponent.counters.setdefault("pending_phase_modify", [])
    pending.append(entry)

    state.log(
        f"對手下回合【{phase_str or '？'}】階段 {stat_str.upper()}"
        f" {'+'  if amount >= 0 else ''}{amount}"
    )


# ─── 主調度器 ────────────────────────────────────────────────

def dispatch_opponent_effect(
    effect: "Effect",
    state: "GameState",
    actor: "PlayerState",
    opponent: "PlayerState",
    **kwargs,
) -> None:
    """
    依 effect.effect_type 調度對應的對手效果函式。
    由上層 effect dispatcher 呼叫。
    """
    from game_engine.schema import EffectType

    handler_map = {
        EffectType.OPP_DISCARD_FROM_EVENT: apply_opp_discard_from_event,
        EffectType.OPP_STAT_REDUCE:        apply_opp_stat_reduce,
        EffectType.OPP_STAT_SET:           apply_opp_stat_set,
        EffectType.OPP_BLK_ZERO:           apply_opp_blk_zero,
        EffectType.OPP_ZONE_LOCK:          apply_opp_zone_lock,
        EffectType.OPP_SKILL_NULLIFY:      apply_opp_skill_nullify,
        EffectType.OPP_PHASE_MODIFY:       apply_opp_phase_modify,
    }

    handler = handler_map.get(effect.effect_type)
    if handler is None:
        state.log(
            f"[WARN] dispatch_opponent_effect: 未知 effect_type={effect.effect_type}"
        )
        return

    handler(effect, state, actor, opponent, **kwargs)
