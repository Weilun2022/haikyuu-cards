"""
game_engine/schema.py — 完整遊戲效果資料模型
覆蓋 cards_zh.json 518 張牌的所有效果型別
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════

class TriggerTag(str, Enum):
    """效果觸發時機 (對應 skill_zh 中的 [=...] 標籤)"""
    DEPLOY          = "登場"
    ATTACK          = "攻擊"
    RECEIVE         = "接球"
    DRAW            = "抽牌"
    SERVE           = "發球"
    BLOCK           = "攔網"
    TOSS            = "舉球"
    HAND            = "手牌"          # [=手牌]: 從手牌發動
    # 回合階段
    DRAW_PHASE      = "抽牌階段"
    ATTACK_PHASE    = "攻擊階段"
    BLOCK_PHASE     = "攔網階段"
    RECEIVE_PHASE   = "接球階段"
    # 排球動作觸發 (N = 門檻值)
    SPIKE_N         = "封殺攔網(N)"   # 封殺攻擊
    DIG_N           = "一觸(N)"       # 一觸接球
    BACK_ATK_N      = "後排攻擊(N)"   # 後排攻擊
    FEINT_N         = "佯攻(N)"       # 佯攻
    TWO_TOUCH_N     = "二段攻擊(N)"   # 二段攻擊
    OVERHAND_N      = "A傳球(N)"      # A傳球
    OUT_OF_BOUNDS   = "攔網出界(N)"   # 攔網出界
    # 限制標籤
    ONCE_PER_TURN   = "每回合1次"
    FIELD           = "場地"          # 場地效果


class ZoneQualifier(str, Enum):
    """部署目標區域"""
    ATTACK  = "攻擊區"
    RECEIVE = "接球區"
    TOSS    = "舉球區"
    BLOCK   = "攔網區"
    SERVE   = "發球區"
    ANY     = "任意"


class ConditionType(str, Enum):
    """技能條件類型"""
    ALWAYS              = "always"
    # 棄牌區條件
    SIX_UNIQUE          = "six_unique"          # 棄牌區 6 種不同名稱
    GRAVE_UNIQUE_GE     = "grave_unique_ge"     # 棄牌區 N 種不同名稱 (N≠6)
    CARD_IN_GRAVE       = "card_in_grave"       # 棄牌區有特定角色
    # 手牌條件
    HAND_LE             = "hand_le"             # 手牌 ≤ N
    HAND_GE             = "hand_ge"             # 手牌 ≥ N
    HAND_HAS            = "hand_has"            # 手牌有特定卡
    # 自己場地條件
    ALL_SAME_SCHOOL     = "all_same_school"     # 自己角色全是同一學校
    MULTI_SCHOOL_GE     = "multi_school_ge"     # 不同所屬角色 ≥ N 人
    ZONE_OCCUPIED       = "zone_occupied"       # 特定區有角色
    ZONE_EMPTY          = "zone_empty"          # 特定區沒有角色
    SETTER_IS           = "setter_is"           # 舉球角色是「姓名」
    ATTACKER_IS         = "attacker_is"         # 攻擊角色是「姓名」
    LIBERO_IN_RECEIVE   = "libero_in_receive"   # 自由人在接球區
    SELF_IS_RECEIVER    = "self_is_receiver"    # 此角色在接球區
    # 出場方式條件
    SKILL_DEPLOY        = "skill_deploy"        # 以技能出場
    NAMED_SKILL_DEPLOY  = "named_skill_deploy"  # 以特定技能出場 (param: 技能卡名)
    DEPLOY_AS_POSITION  = "deploy_as_position"  # 以特定位置身份出場
    FROM_HAND           = "from_hand"           # 從手牌出場（非技能）
    # 對手條件
    OPP_ATK_GE          = "opp_atk_ge"         # 對手攻擊值 ≥ N
    OPP_SRV_LE          = "opp_srv_le"         # 對手發球值 ≤ N
    OPP_EVENT_ZONE_LE   = "opp_event_zone_le"  # 對手Event區牌數 ≤ N
    OPP_HAS_CARD        = "opp_has_card"       # 對手有特定角色
    # Guts 條件
    GUTS_ALL_RARITY     = "guts_all_rarity"    # 支付的Guts全部是指定稀有度
    GUTS_HAS_NAMED      = "guts_has_named"     # Guts區有特定角色
    # 特殊條件
    IS_YOSU             = "is_yosu"            # ユース牌組條件
    AFTER_DISCARD       = "after_discard"      # 棄置N張後 (已在 cost 中，此為效果條件)
    PILE_TOP_MATCHES    = "pile_top_matches"   # 牌庫頂牌滿足條件
    COUNTER_GE          = "counter_ge"         # 計數器 ≥ N


class EffectType(str, Enum):
    """效果類型"""
    # 數值加成
    STAT_BONUS          = "stat_bonus"          # 數值 +N
    STAT_SET            = "stat_set"            # 數值設為 N
    STAT_IMMUNITY       = "stat_immunity"       # 此回合數值不能被降低
    # 手牌操作
    DRAW                = "draw"                # 抽 N 張
    DISCARD_FROM_HAND   = "discard_from_hand"  # 棄置手牌 N 張
    RECOVER_CHAR        = "recover_char"        # 從棄牌區取角色到手牌
    RECOVER_EVENT       = "recover_event"       # 從棄牌區取Event到手牌
    RECOVER_FROM_EVENT_ZONE = "recover_from_event_zone"  # 從Event區取牌到手牌
    ADD_TO_HAND_FROM_PILE = "add_to_hand_from_pile"     # 從牌庫取特定牌到手牌
    # 出場/移動
    DEPLOY_FROM_GRAVE   = "deploy_from_grave"   # 從棄牌區直接出場
    DEPLOY_FROM_GUTS    = "deploy_from_guts"    # 從Guts出場至指定區
    RETURN_TO_HAND      = "return_to_hand"      # 回到手牌
    RETURN_TO_PILE      = "return_to_pile"      # 放到牌庫 top/bottom
    MOVE_TO_ZONE        = "move_to_zone"        # 移至指定區
    MOVE_GUTS_TO_ZONE   = "move_guts_to_zone"  # Guts牌移至指定區
    TAP_DEPLOY          = "tap_deploy"          # 横置出場
    SWAP_ZONE           = "swap_zone"           # 交換兩個區的牌
    # 牌庫/棄牌操作
    PILE_PEEK           = "pile_peek"           # 公開牌庫頂 N 張
    PILE_PEEK_AND_KEEP  = "pile_peek_and_keep" # 公開並可選取加入手牌
    SHUFFLE_PILE        = "shuffle_pile"        # 洗牌庫
    EVENT_ZONE_PLACE    = "event_zone_place"    # 將手牌Event放至Event區
    # 對手操作
    OPP_DISCARD_FROM_EVENT = "opp_discard_from_event"  # 棄置對手Event區牌
    OPP_STAT_REDUCE     = "opp_stat_reduce"     # 對手角色數值 -N
    OPP_STAT_SET        = "opp_stat_set"        # 對手角色數值設為 N
    OPP_BLK_ZERO        = "opp_blk_zero"        # 對手下回合MB攔網無效
    OPP_ZONE_LOCK       = "opp_zone_lock"       # 對手出場/技能限制
    OPP_SKILL_NULLIFY   = "opp_skill_nullify"   # 對手特定技能無效化
    OPP_PHASE_MODIFY    = "opp_phase_modify"    # 對手下回合阶段修改
    # 特殊
    PHASE_CONTROL       = "phase_control"       # 立即結束/進入某階段
    GUTS_BONUS          = "guts_bonus"          # Guts +N
    COUNTER_ADD         = "counter_add"         # 計數器 +N
    ONCE_PER_TURN_MARK  = "once_per_turn_mark"  # 標記本回合已使用
    SCORE_POINT         = "score_point"         # 直接得分 (極少)
    CONDITIONAL_EXTRA   = "conditional_extra"   # 如果額外條件成立再觸發額外效果
    NAME_CHANGE         = "name_change"         # 改變此牌的牌名（融合角色卡）


class Stat(str, Enum):
    ATK = "atk"
    RCV = "rcv"
    BLK = "blk"
    TOS = "tos"
    SRV = "srv"
    ANY = "any"  # 任意數值 +N (由玩家選擇)


class Position(str, Enum):
    WS  = "WS"   # 側翼攔網手
    MB  = "MB"   # 中間攔網手
    OH  = "OH"   # 主攻手（有些卡標記此位置）
    L   = "L"    # 自由人
    SET = "SET"  # 舉球手
    ANY = "ANY"


# ═══════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════

@dataclass
class Condition:
    type: ConditionType
    param: int | str | list | None = None
    # param 語意:
    #   hand_le/hand_ge     → int N
    #   setter_is/attacker_is → str 角色名稱
    #   named_skill_deploy  → str 技能卡名
    #   deploy_as_position  → str 位置縮寫
    #   opp_atk_ge/srv_le   → int N
    #   guts_all_rarity     → str 稀有度 ("S","R",...)
    #   guts_has_named      → str 角色名稱
    #   multi_school_ge     → int N
    #   grave_unique_ge     → int N
    #   card_in_grave       → str 角色名稱
    #   all_same_school     → str 學校名稱 (None = 任意單一學校)
    #   counter_ge          → int N


@dataclass
class Cost:
    guts: int = 0
    discard: int = 0
    discard_filter: dict = field(default_factory=dict)
    # discard_filter: e.g. {"school": "稲荷崎"}, {"category": "EVENT"}
    place_to_event: bool = False   # 需要把手牌Event放到Event區作為費用


@dataclass
class CardFilter:
    """用於 recover/deploy 效果中篩選目標卡片"""
    school: str | None = None
    position: list[str] | None = None    # e.g. ["WS", "MB"]
    category: str | None = None          # "CHARACTER" or "EVENT"
    name: str | None = None              # 特定卡名
    rarity: str | None = None            # "S", "R", etc.
    max_count: int = 1


@dataclass
class Effect:
    effect_type: EffectType
    target: str = "self"              # "self", "opponent", "card", "zone"
    stat: Stat | None = None
    amount: int = 0
    duration: str = "permanent"       # "permanent", "this_turn", "next_turn", "until_deploy"
    zone: ZoneQualifier | str | None = None
    from_zone: str | None = None
    to_zone: str | None = None
    pile_position: str = "top"        # "top" or "bottom"
    card_filter: CardFilter = field(default_factory=CardFilter)
    phase: str | None = None          # for PHASE_CONTROL: target phase name
    # 條件分支: 如果某額外條件成立，額外再觸發 extra_effects
    extra_condition: Condition | None = None
    extra_effects: list[Effect] = field(default_factory=list)


@dataclass
class ChoiceGroup:
    """▶ 選一 結構: 玩家從多個效果組中選一組執行"""
    choices: list[list[Effect]]
    must_choose: int = 1              # 必須選幾項 (通常=1)


@dataclass
class CardSkill:
    card_no: str
    triggers: list[TriggerTag]
    zone_qualifiers: list[ZoneQualifier]
    conditions: list[Condition]           # AND 邏輯
    costs: Cost
    effects: list[Effect]                 # 直接效果 (無分支)
    choices: list[ChoiceGroup] = field(default_factory=list)  # 含分支效果
    once_per_turn: bool = False
    volleyball_threshold: int | None = None  # [封殺攔網(N)] 的 N
    raw_text: str = ""
    notes: str = ""                       # AI 解析備注


# ═══════════════════════════════════════════════════════════
# GAME STATE (供效果 handler 使用)
# ═══════════════════════════════════════════════════════════

@dataclass
class CardInstance:
    """
    牌局中每張卡片的唯一實體（fugu-ultra 建議：CardDefinition vs CardInstance 分離）。
    同一 card_no 可有多個 CardInstance（例如牌組裡有 3 張相同卡）。
    """
    instance_id: str              # 唯一 ID，例如 "HV-P02-017_01"
    card_no: str                  # 對應 CardDefinition 的鍵
    owner: int                    # 1 or 2 (player num)
    zone: str = "pile"            # "pile","hand","grave","event_zone","toss","attack","receive","block_0-2","serve","guts_toss",...
    tapped: bool = False          # 横置狀態
    stat_modifiers: dict = field(default_factory=dict)  # {"atk": +2} 暫時加值
    once_per_turn_used: bool = False
    immune_to_stat_reduce: bool = False


@dataclass
class GutsPool:
    """
    各區域獨立 Guts 池（fugu-ultra 建議：不只是計數，需記錄卡片實體）。
    """
    zone: str                      # "toss","attack","receive","block","serve"
    cards: list[CardInstance] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.cards)


# ── Event Queue (fugu-ultra 建議：timing window + stack) ──────────────

class GamePhase(str, Enum):
    START_RALLY      = "start_rally"
    DRAW             = "draw"
    MAIN             = "main"            # 部署牌
    ON_DEPLOY        = "on_deploy"       # 卡剛出場時
    ACTION_SELECT    = "action_select"   # 選擇動作
    BEFORE_ATTACK    = "before_attack"
    ON_ATTACK_DECL   = "on_attack_declared"
    AFTER_ATTACK_VAL = "after_attack_value"
    ON_BLOCK_DECL    = "on_block_declared"
    AFTER_BLOCK_VAL  = "after_block_value"
    ON_ONE_TOUCH     = "on_one_touch"
    ON_KILL_BLOCK    = "on_kill_block_success"
    BEFORE_RECEIVE   = "before_receive"
    ON_RECEIVE_DECL  = "on_receive_declared"
    AFTER_RECEIVE    = "after_receive_value"
    END_RALLY        = "end_rally"
    END_SET          = "end_set"


@dataclass
class GameEvent:
    """進入 Event Stack 的觸發事件。"""
    phase: GamePhase
    actor_player: int                  # 1 or 2
    source_instance_id: str | None = None
    payload: dict = field(default_factory=dict)
    # payload 例子:
    #   ON_DEPLOY: {"zone": "attack", "instance_id": "...", "deploy_via_skill": True}
    #   ON_ATTACK_DECLARED: {"atk_value": 5, "target_player": 2}


@dataclass
class ZoneState:
    card: str | None = None          # card_no（快取，真實記錄在 CardInstance.zone）
    instance_id: str | None = None   # 對應 CardInstance
    guts: list[str] = field(default_factory=list)  # instance_id list
    tapped: bool = False


@dataclass
class PlayerState:
    name: str
    school: str
    pile: list[str] = field(default_factory=list)       # card_no list, 牌庫
    hand: list[str] = field(default_factory=list)
    grave: list[str] = field(default_factory=list)      # 棄牌區
    event_zone: list[str] = field(default_factory=list) # Event區
    # 場地
    serve_zone: ZoneState = field(default_factory=ZoneState)
    toss_zone: ZoneState = field(default_factory=ZoneState)
    attack_zone: ZoneState = field(default_factory=ZoneState)
    receive_zone: ZoneState = field(default_factory=ZoneState)
    block_zones: list[ZoneState] = field(default_factory=lambda: [ZoneState(), ZoneState(), ZoneState()])
    # Guts 池 (三個獨立池)
    g_serve: int = 0
    g_toss: int = 0
    g_attack: int = 0
    g_receive: int = 0
    g_block: int = 0
    # 狀態修正 (本回合)
    atk_bonus: int = 0
    rcv_bonus: int = 0
    blk_bonus: int = 0
    tos_bonus: int = 0
    srv_bonus: int = 0
    # 跨回合狀態
    next_turn_blk_zero: bool = False      # 對手下回合MB BLK=0
    next_turn_skill_nullify: list[str] = field(default_factory=list)
    next_turn_zone_lock: dict = field(default_factory=dict)
    # 計數器
    counters: dict = field(default_factory=dict)
    set_score: int = 0                    # 贏得的 LOST 數（顯示用）
    set_cards: int = 2                    # SET ZONE 剩餘張數（0 時再 LOST → 敗北）
    # 六種類追蹤 (fugu-ultra 建議：character_id 增量計數，不掃陣列)
    # character_id = 角色名稱的標準化 ID（處理全名/簡稱/同角色不同版本）
    _grave_char_counter: dict = field(default_factory=dict)   # {character_id: count}
    _grave_unique_count: int = 0                              # 快取的唯一角色數

    def unique_names_in_grave(self) -> int:
        return self._grave_unique_count

    def add_to_grave(self, instance: CardInstance, character_id: str | None) -> None:
        self.grave.append(instance.instance_id)
        if character_id:
            prev = self._grave_char_counter.get(character_id, 0)
            self._grave_char_counter[character_id] = prev + 1
            if prev == 0:
                self._grave_unique_count += 1

    def remove_from_grave(self, instance: CardInstance, character_id: str | None) -> None:
        if instance.instance_id in self.grave:
            self.grave.remove(instance.instance_id)
        if character_id:
            cur = self._grave_char_counter.get(character_id, 0)
            if cur > 0:
                self._grave_char_counter[character_id] = cur - 1
                if cur - 1 == 0:
                    self._grave_unique_count -= 1


@dataclass
class GameState:
    p1: PlayerState
    p2: PlayerState
    turn: int = 1
    current_player: int = 1    # 1 or 2（目前行動方）
    phase: str = "serve"
    game_log: list[str] = field(default_factory=list)
    round_num: int = 1         # 目前第幾局 (rally count)
    # 新規則欄位
    pending_op: int = 0        # 當前進攻值（下一個行動方需抵擋）
    server_num: int = 1        # 本 rally 發球方
    last_deployed_name: str | None = None  # ABA規則：上一位出場角色名稱
    game_over: bool = False
    game_winner: int = 0

    def active(self) -> PlayerState:
        return self.p1 if self.current_player == 1 else self.p2

    def passive(self) -> PlayerState:
        return self.p2 if self.current_player == 1 else self.p1

    def is_terminal(self) -> bool:
        return self.game_over

    def winner(self) -> int | None:
        return self.game_winner if self.game_over else None

    def log(self, msg: str) -> None:
        self.game_log.append(f"Rally{self.round_num}T{self.turn}P{self.current_player}: {msg}")
