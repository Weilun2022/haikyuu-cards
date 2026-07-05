"""game_engine/effects/registry.py — 效果分發器 + 技能載入器"""
from __future__ import annotations
import json
from pathlib import Path
from game_engine.schema import (
    Effect, EffectType, CardSkill, GameState, PlayerState, ChoiceGroup,
    Condition, ConditionType, Cost, CardFilter, TriggerTag, ZoneQualifier, Stat
)
from game_engine.effects.handlers import stat, hand, zone, opponent
from game_engine.engine.conditions import evaluate_all_conditions


class EffectRegistry:

    def __init__(self):
        self._skill_db: dict[str, CardSkill] = {}

    # ── 技能資料庫載入 ────────────────────────────────────────────────────────

    def load_skill_db(self, path: str | Path | None = None) -> int:
        """載入 cards_skills.json，回傳成功解析的卡片數。"""
        if path is None:
            path = Path(__file__).parent.parent / "cards_skills.json"
        path = Path(path)
        if not path.exists():
            return 0
        with open(path, encoding="utf-8") as f:
            raw: dict = json.load(f)

        count = 0
        for card_no, data in raw.items():
            try:
                skill = self._parse_card_skill(card_no, data)
                if skill:
                    self._skill_db[card_no] = skill
                    count += 1
            except Exception:
                pass
        return count

    def get_skill(self, card_no: str) -> CardSkill | None:
        return self._skill_db.get(card_no)

    # ── 效果套用 ─────────────────────────────────────────────────────────────

    def apply_effect(
        self,
        effect: Effect,
        state: GameState,
        actor: PlayerState,
        passive: PlayerState,
        card_no: str = "",
        ai=None,
    ) -> None:
        t = effect.effect_type
        match t:
            # stat
            case EffectType.STAT_BONUS:
                stat.apply_stat_bonus(effect, state, actor, card_no)
            case EffectType.STAT_SET:
                stat.apply_stat_set(effect, state, actor, passive, card_no)
            case EffectType.STAT_IMMUNITY:
                stat.apply_stat_immunity(effect, state, actor, card_no)
            # hand
            case EffectType.DRAW:
                hand.apply_draw(effect, state, actor)
            case EffectType.DISCARD_FROM_HAND:
                ai_fn = (lambda h, s: ai.decide_discard(h, s, actor)) if ai else None
                hand.apply_discard_from_hand(effect, state, actor, ai_fn)
            case EffectType.RECOVER_CHAR:
                hand.apply_recover_char(effect, state, actor, ai)
            case EffectType.RECOVER_EVENT:
                hand.apply_recover_event(effect, state, actor, ai)
            case EffectType.RECOVER_FROM_EVENT_ZONE:
                hand.apply_recover_from_event_zone(effect, state, actor)
            case EffectType.ADD_TO_HAND_FROM_PILE:
                hand.apply_add_to_hand_from_pile(effect, state, actor)
            # zone
            case EffectType.DEPLOY_FROM_GRAVE:
                zone.apply_deploy_from_grave(effect, state, actor, ai)
            case EffectType.DEPLOY_FROM_GUTS:
                zone.apply_deploy_from_guts(effect, state, actor, ai)
            case EffectType.RETURN_TO_HAND:
                zone.apply_return_to_hand(effect, state, actor, card_no)
            case EffectType.RETURN_TO_PILE:
                zone.apply_return_to_pile(effect, state, actor, card_no)
            case EffectType.MOVE_TO_ZONE:
                zone.apply_move_to_zone(effect, state, actor, card_no)
            case EffectType.MOVE_GUTS_TO_ZONE:
                zone.apply_move_guts_to_zone(effect, state, actor)
            case EffectType.TAP_DEPLOY:
                zone.apply_tap_deploy(effect, state, actor, card_no)
            case EffectType.SWAP_ZONE:
                zone.apply_swap_zone(effect, state, actor)
            case EffectType.PILE_PEEK:
                zone.apply_pile_peek(effect, state, actor)
            case EffectType.PILE_PEEK_AND_KEEP:
                zone.apply_pile_peek_and_keep(effect, state, actor, ai)
            case EffectType.SHUFFLE_PILE:
                zone.apply_shuffle_pile(effect, state, actor)
            case EffectType.EVENT_ZONE_PLACE:
                zone.apply_event_zone_place(effect, state, actor, card_no)
            # opponent
            case EffectType.OPP_DISCARD_FROM_EVENT:
                opponent.apply_opp_discard_from_event(effect, state, actor, passive, ai=ai)
            case EffectType.OPP_STAT_REDUCE:
                opponent.apply_opp_stat_reduce(effect, state, actor, passive)
            case EffectType.OPP_STAT_SET:
                opponent.apply_opp_stat_set(effect, state, actor, passive)
            case EffectType.OPP_BLK_ZERO:
                opponent.apply_opp_blk_zero(effect, state, actor, passive)
            case EffectType.OPP_ZONE_LOCK:
                opponent.apply_opp_zone_lock(effect, state, actor, passive)
            case EffectType.OPP_SKILL_NULLIFY:
                opponent.apply_opp_skill_nullify(effect, state, actor, passive)
            case EffectType.OPP_PHASE_MODIFY:
                opponent.apply_opp_phase_modify(effect, state, actor, passive)
            case EffectType.GUTS_BONUS:
                _zone = str(effect.zone or "attack")
                attr = f"g_{_zone}"
                if hasattr(actor, attr):
                    setattr(actor, attr, getattr(actor, attr) + (effect.amount or 1))
            case EffectType.COUNTER_ADD:
                key = str(effect.zone or "counter")
                new_val = actor.counters.get(key, 0) + (effect.amount or 1)
                # 六種類相關計數上限 6，與 _grave_unique_count 邏輯一致
                if key in {"unique", "six_type", "grave_unique"}:
                    new_val = min(6, new_val)
                actor.counters[key] = new_val
            case EffectType.NAME_CHANGE:
                pass  # 融合角色卡改名：AI 模擬暫不追蹤，略過不影響遊戲流程
            case _:
                state.log(f"[SKIP] effect_type={t} 尚未實作")

    def apply_skill(
        self,
        card_skill: CardSkill,
        state: GameState,
        actor: PlayerState,
        passive: PlayerState,
        card_no: str = "",
        deploy_zone: str | None = None,
        deploy_via_skill: bool = False,
        ai=None,
    ) -> bool:
        """評估條件 + 套用效果。回傳 True 若技能發動。"""
        # 每回合一次檢查
        if card_skill.once_per_turn:
            used_key = f"once_used:{card_no}"
            if actor.counters.get(used_key):
                return False
            actor.counters[used_key] = True

        # 條件評估
        if not evaluate_all_conditions(
            card_skill.conditions, state, actor, card_no,
            deploy_zone=deploy_zone, deploy_via_skill=deploy_via_skill,
        ):
            return False

        # 費用支付
        if card_skill.costs.guts > 0:
            zone_for_guts = deploy_zone or "attack"
            attr = f"g_{zone_for_guts}"
            available = getattr(actor, attr, 0)
            if available < card_skill.costs.guts:
                return False
            setattr(actor, attr, available - card_skill.costs.guts)

        if card_skill.costs.place_to_event:
            from game_engine.card_db import is_event
            events_in_hand = [c for c in actor.hand if is_event(c)]
            if not events_in_hand:
                return False  # 無 Event 牌可支付 → 不發動
            chosen = events_in_hand[0]
            actor.hand.remove(chosen)
            actor.event_zone.append(chosen)

        if card_skill.costs.discard > 0:
            hand_copy = list(actor.hand)
            to_discard = (ai.decide_discard(hand_copy, state, actor, card_skill.costs.discard)
                          if ai else hand_copy[:card_skill.costs.discard])
            for c in to_discard:
                if c in actor.hand:
                    actor.hand.remove(c)
                    actor.grave.append(c)
                    from game_engine.card_db import get_name
                    char_id = get_name(c) or c
                    prev = actor._grave_char_counter.get(char_id, 0)
                    actor._grave_char_counter[char_id] = prev + 1
                    if prev == 0:
                        actor._grave_unique_count += 1

        # 分支效果 vs 直接效果
        if card_skill.choices:
            cg = card_skill.choices[0]
            idx = ai.decide_skill_choice(card_skill.choices, state, actor) if ai else 0
            idx = max(0, min(idx, len(cg.choices) - 1))
            for eff in cg.choices[idx]:
                self.apply_effect(eff, state, actor, passive, card_no, ai)
        else:
            for eff in card_skill.effects:
                self.apply_effect(eff, state, actor, passive, card_no, ai)

        return True

    def try_activate_deploy_skill(
        self,
        card_no: str,
        deploy_zone: str,
        deploy_via_skill: bool,
        state: GameState,
        actor: PlayerState,
        passive: PlayerState,
        ai=None,
    ) -> bool:
        """卡片出場時嘗試觸發 [=登場] 技能。"""
        skill = self.get_skill(card_no)
        if not skill:
            return False
        # 確認有 [登場] 觸發標籤
        has_deploy_trigger = any(
            t in (TriggerTag.DEPLOY, "登場") for t in skill.triggers
        )
        if not has_deploy_trigger:
            return False
        # 確認部署區域符合 zone_qualifier
        if skill.zone_qualifiers:
            zone_map = {
                ZoneQualifier.ATTACK: "attack",
                ZoneQualifier.RECEIVE: "receive",
                ZoneQualifier.TOSS: "toss",
                ZoneQualifier.BLOCK: "block",
                ZoneQualifier.SERVE: "serve",
                "攻擊區": "attack",
                "接球區": "receive",
                "舉球區": "toss",
                "攔網區": "block",
                "發球區": "serve",
            }
            allowed = {zone_map.get(z, str(z).lower()) for z in skill.zone_qualifiers}
            if deploy_zone.lower() not in allowed and ZoneQualifier.ANY not in skill.zone_qualifiers:
                return False
        return self.apply_skill(
            skill, state, actor, passive, card_no,
            deploy_zone=deploy_zone,
            deploy_via_skill=deploy_via_skill,
            ai=ai,
        )

    # ── 階段觸發（Phase Hooks）───────────────────────────────────────────────

    # phase 名稱 → cards_skills.json 中 triggers 標籤的對應集合
    _PHASE_TRIGGERS: dict[str, set] = {
        "serve":   {"發球", "發球階段", "serve", "serve_phase"},
        "receive": {"接球", "接球階段", "receive", "receive_phase"},
        "toss":    {"舉球", "舉球階段", "toss", "toss_phase"},
        "attack":  {"攻擊", "攻擊階段", "attack", "attack_phase"},
        "block":   {"攔網", "攔網階段", "block", "block_phase"},
        "draw":    {"抽牌", "抽牌階段", "draw", "draw_phase", "=抽牌"},
    }

    def _skill_matches_phase(self, skill: CardSkill, phase: str) -> bool:
        labels = self._PHASE_TRIGGERS.get(phase, set())
        for t in skill.triggers:
            t_val = t.value if hasattr(t, "value") else str(t)
            if t_val in labels:
                return True
        return False

    def _is_nullified(self, actor: PlayerState, skill: CardSkill) -> bool:
        """對手 opp_skill_nullify 效果：封鎖含指定觸發標籤的技能。"""
        if not actor.next_turn_skill_nullify:
            return False
        blocked = set(actor.next_turn_skill_nullify)
        for t in skill.triggers:
            t_val = t.value if hasattr(t, "value") else str(t)
            if t_val in blocked:
                return True
        return "ALL" in blocked

    def try_activate_phase_skills(
        self,
        phase: str,
        state: GameState,
        actor: PlayerState,
        passive: PlayerState,
        ai=None,
    ) -> list[str]:
        """
        階段觸發掛鉤（pre-resolution 時點呼叫，在該階段判定/OP計算「之前」）：
          1. actor 場上角色卡：技能 triggers 含該 phase 標籤 → 條件符合即自動發動
          2. actor 手牌 Event 卡：triggers 含該 phase 標籤 → 先驗條件，AI 決定後打出
             （打出 = 手牌移入 event_zone，再套用效果）
        回傳實際發動的 card_no 清單。
        """
        from game_engine.card_db import is_event
        from game_engine.engine.conditions import evaluate_all_conditions
        fired: list[str] = []

        # 1. 場上角色階段技
        board_cards: list[str] = []
        for z in (actor.serve_zone, actor.toss_zone, actor.attack_zone, actor.receive_zone):
            if z.card:
                board_cards.append(z.card)
        for bz in actor.block_zones:
            if bz.card:
                board_cards.append(bz.card)
        for cno in board_cards:
            skill = self.get_skill(cno)
            if not skill or not self._skill_matches_phase(skill, phase):
                continue
            if self._is_nullified(actor, skill):
                state.log(f"[NULLIFY] {cno}@{phase} 被封鎖")
                continue
            try:
                if self.apply_skill(skill, state, actor, passive, cno,
                                    deploy_zone=None, deploy_via_skill=False, ai=ai):
                    fired.append(cno)
                    state.log(f"[PHASE_SKILL] {cno}@{phase}")
            except Exception as e:
                state.log(f"[PHASE_SKILL ERR] {cno}@{phase}: {e}")

        # 2. 手牌 Event 卡
        for cno in list(actor.hand):
            if not is_event(cno):
                continue
            skill = self.get_skill(cno)
            if not skill or not self._skill_matches_phase(skill, phase):
                continue
            if self._is_nullified(actor, skill):
                continue
            # 先驗條件（不符不打出，避免浪費）
            try:
                if not evaluate_all_conditions(skill.conditions, state, actor, cno):
                    continue
            except Exception:
                continue
            # AI 決定是否打出（無 AI 或無此方法 → 預設打出）
            decide = getattr(ai, "decide_play_event", None)
            if decide and not decide(cno, skill, phase, state, actor):
                continue
            try:
                actor.hand.remove(cno)
                actor.event_zone.append(cno)
                if self.apply_skill(skill, state, actor, passive, cno,
                                    deploy_zone=None, deploy_via_skill=False, ai=ai):
                    fired.append(cno)
                    state.log(f"[EVENT] {cno}@{phase}")
                else:
                    state.log(f"[EVENT] {cno}@{phase} 打出但未發動")
            except Exception as e:
                state.log(f"[EVENT ERR] {cno}@{phase}: {e}")

        return fired

    # ── JSON → CardSkill 解析 ────────────────────────────────────────────────

    def _parse_card_skill(self, card_no: str, data: dict) -> CardSkill | None:
        if data.get("parse_error") or not data.get("effects"):
            return None

        def _to_trigger(t: str) -> TriggerTag | str:
            for tag in TriggerTag:
                if tag.value == t or tag == t:
                    return tag
            return t

        def _to_condition(d: dict) -> Condition | None:
            t = d.get("type", "always")
            for ct in ConditionType:
                if ct.value == t:
                    return Condition(type=ct, param=d.get("param"))
            return Condition(type=ConditionType.ALWAYS)

        def _to_effect(d: dict) -> Effect | None:
            et_str = d.get("effect_type", "")
            # LLM 有時輸出 card_name_change，統一對應 name_change
            if et_str == "card_name_change":
                et_str = "name_change"
            et = None
            for e in EffectType:
                if e.value == et_str:
                    et = e
                    break
            if et is None:
                return None
            stat_str = d.get("stat")
            stat_val = None
            if stat_str:
                for s in Stat:
                    if s.value == stat_str:
                        stat_val = s
                        break
            cf_raw = d.get("card_filter") or {}
            cf = CardFilter(
                school=cf_raw.get("school"),
                position=cf_raw.get("position"),
                name=cf_raw.get("name"),
                max_count=cf_raw.get("max_count", 1),
            )
            return Effect(
                effect_type=et,
                target=d.get("target", "self"),
                stat=stat_val,
                amount=int(d.get("amount") or 0),
                duration=d.get("duration", "permanent"),
                zone=d.get("zone"),
                from_zone=d.get("from_zone"),
                to_zone=d.get("to_zone"),
                pile_position=d.get("pile_position", "top"),
                card_filter=cf,
            )

        triggers = [_to_trigger(t) for t in (data.get("triggers") or [])]
        conditions_raw = data.get("conditions") or [{"type": "always"}]
        conditions = [c for c in (_to_condition(d) for d in conditions_raw) if c]
        effects_raw = data.get("effects") or []
        effects = [e for e in (_to_effect(d) for d in effects_raw) if e]

        if not effects:
            return None

        costs_raw = data.get("costs") or {}
        costs = Cost(
            guts=int(costs_raw.get("guts") or 0),
            discard=int(costs_raw.get("discard") or 0),
            place_to_event=bool(costs_raw.get("place_to_event", False)),
        )

        # zone_qualifiers（先從 zone_qualifiers 欄位，再從 triggers 欄位補充）
        zone_quals = []
        for zq in (data.get("zone_qualifiers") or []):
            for zqe in ZoneQualifier:
                if zqe.value == zq or zqe == zq:
                    zone_quals.append(zqe)
                    break
        # LLM 有時把區域標籤放在 triggers 而非 zone_qualifiers
        for t in (data.get("triggers") or []):
            for zqe in ZoneQualifier:
                if zqe.value == t and zqe not in zone_quals:
                    zone_quals.append(zqe)
                    break

        return CardSkill(
            card_no=card_no,
            triggers=triggers,
            zone_qualifiers=zone_quals,
            conditions=conditions,
            costs=costs,
            effects=effects,
            once_per_turn=bool(data.get("once_per_turn", False)),
            volleyball_threshold=data.get("volleyball_threshold"),
            raw_text=data.get("raw_text", ""),
            notes=data.get("notes", ""),
        )
