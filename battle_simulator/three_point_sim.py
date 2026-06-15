"""
稲荷崎「三決勝分」三資源 turn-by-turn 模擬引擎
==================================================
建模三大失分/失敗向量（含使用者新增的「手牌差」）：
  1. Guts-lock   : Guts 不足無法啟動 どんぴしゃり 迴圈
  2. hand-crisis : 手牌枯竭 → 無法佈防 → 對手賺牌差得分（race loss）
  3. diversity   : 墓地6種太慢 → 第3分 finisher (角名/PR-048…) 開不出來

第3分修正機制（已和使用者確認）：
  - 攻擊區同時只能 1 名角色 → 角名 P02-027 與 宮治R P02-021 不可同框
  - 角名 P02-027：墓地6種時橫置(0 Guts) → ATK+2 且「對手下回合」中間攔網手 BLK=0（跨回合）
  - 宮治R P02-021：出場後手牌≤2 → ATK+2（0 Guts）。判定在「出場後」，即出場前手牌≤3
  - 兩條路線：
      路線A 兩回合：T_n 角名鋪 BLK=0 → T_n+1 宮治R 在 BLK=0 環境收尾
      路線B 單張  ：宮治R 在前一次 P02-020 留下的「對手攔網≤2」遺產下單回合打穿

對手以「壓力 race」抽象：每個對手回合，若我方防禦(場上RCV/BLK body + 手牌厚度)
不足以擋下隨機攻擊，對手得分；對手先到 3 分 → race loss（我方未能穩定三分）。

輸出：穩定三分率 = P(我方先到3分 ∧ 無 guts-starved ∧ 無 hand-crisis)

==================================================
校準紀錄 (2026-06: 對齊使用者實戰錨點 1分≈97-99% / 2分≈90-93%)
--------------------------------------------------
舊版引擎 1分≈87% / 2分≈75%,遠低於實戰錨點。逐項校準(詳見內文 [校準n] 標記):
  [校準3] 舉球區=宮侑 可由任一宮侑來源(香草侑/P02-016/twin)建立,不再只認單一 role
          → 解決「無舉球宮侑(no_setter_zone)」占無第1分主因的問題。
  [校準4/5/6] どんぴ發動移除「雙body硬閘」: 舉球已在場時只需拉攻擊端(3 Guts),首發大幅
          提前; 並補上 P02-024 主動回收どんぴ。
  [校準7] guts_starved 語意修正: 開局抽序造成的一回合暫時 Guts 不足會被 regen 化解,
          不應永久標記。改為「整局結束仍未化解的どんぴ/finisher Guts 力竭」才計入,
          對應使用者「打完兩個10點就沒力」的『後段』力竭, 而非開局延遲。
  [校準9] 對手壓力參數 mu 5.2→4.6、手牌防禦權重 k 0.9→1.1,把前兩分穩定度拉到錨點區間
          (稲荷崎前期手厚、防禦足,對手難於前段得分)。
  [校準10] 手牌經濟敏感化(使用者明確需求): finisher 清手牌(尤其宮治R 需手牌≤2)的回合
          若手牌薄(≤2),跨回合空窗以 45% 機率讓對手多得 1 分並計入 hand-crisis;
          角名鋪設(路線A, 該回合不得分卻佔攻擊區)亦為一個 thin-hand 暴露窗口。
          宮治R 路線會主動棄牌湊條件 → 真實模擬「清空手牌打 finisher」的失分向量。
校準後 M4: 1分≈96.5% / 2分≈91% / 3分≈84% / 穩定3分≈82% / hand-crisis≈4%。

==================================================
[校準13] 官方規則書修正 (2026-06: 讀 rules_general_v1.pdf 後)
--------------------------------------------------
重大修正 — Guts 經濟先前嚴重灌水:
  • 防禦(校準12): 攔網(BLK)與接球(RCV)是分開的階段, 對單次攻擊不可相加 →
    defense = max(BLK,RCV) 而非 sum。(規則: 5-7 ブロック / 5-9 レシーブ 分開)
  • Guts(校準13): Guts = 疊在各區角色下方的卡(1-2-15); 唯一產生方式是「角色登場到
    已占用區域→舊角色變Guts」(8-3-1-1); 付Guts=移到棄牌區消耗(1-4-8); 無免費充能。
    どんぴ turn 為 Guts 中性 → 淨生成 ≈ +1/turn (guts_gen 預設1)。
  • 先前 feed_cap=2 + regen +2~4 (≈+4~6 Guts/turn) 把穩定3分灌水到 ~82%。
    規則正確模型下 (guts_gen=1): FINAL_V2 穩定3分 ≈ 77%, 第三分常因 Guts 力竭而慢/失敗,
    對應使用者實戰「打完兩個10點就沒力」。第三分(非6種)才是真瓶頸 — 需往低Guts依賴優化。

==================================================
[校準14] 三個獨立 Guts 池 (2026-06: 使用者規則指正)
--------------------------------------------------
重大修正 — 先前把 Guts 當成單一資源池 (p.guts) 是錯的:
  • 規則: 每個區域(舉球/攻擊/接球)各有自己的 Guts 堆疊, 三池互不流通。
    「該角色在哪個區域, 就付哪個區域的 Guts」。
  • どんぴ(P02-087): 把任一區的 Guts「跳上來」當角色 — 宮侑落舉球区(付舉球区 Guts)、
    宮治落攻擊区(付攻擊区 Guts)。大部分情況是該區自己的 Guts 跳上來。
  • 各池生成: 該區「覆蓋登場」→ 舊角色變該區 Guts。舉球(gen_tos)/攻擊(gen_atk)/接球(gen_rcv)。
  • 牌→池對應: P02-016=舉球; どんぴ攻擊側/PR-048(2G)/P02-029(3G)=攻擊;
    P02-024(3G)/P02-025(2G)/PR-049(2G)=接球。
  • 關鍵結論: 接球区防禦/回收 與 どんぴ 引擎(舉球+攻擊) 用不同池, 完全不競爭!
    → v3 為「省 Guts」而砍 PR-049 是基於單池誤解的錯誤決策。三池模型下接球区防禦
    幾乎免費 → FINAL_V4 恢復 PR-049 並加厚接球区, race-loss 3.8%→2.8%, 淨勝率→80.2%。
  • 三池下 guts-starved 近 0% (低Guts牌組刻意避開攻擊池 finisher → 不再力竭),
    主要失分向量轉為 race-loss 與 hand-crisis(宮治R×4 清手牌)。
"""
from __future__ import annotations
import random, json, argparse
from dataclasses import dataclass, field

# ---- 11 個合法稲荷崎牌名（角名 6 種判定用，依官方 Q&A）----
NAMES = {"宮侑","宮治","北信介","角名","尾白","理石","銀島","大耳","赤木","小作","宮兄弟"}

# ---- 卡牌行為表 ----
# 每張卡: name(墓地計入的牌名), cat('C'/'E'),
#   plus role flags used by the policy.
CARD = {
 # --- どんぴしゃり 引擎核心 ---
 "P02-087": dict(name=None, cat="E", role="donpi"),            # 主引擎(攻擊事件)
 "P02-016": dict(name="宮侑", cat="C", role="setter_dp"),      # 經Guts出場的舉球(否定+抽1)
 "P02-020": dict(name="宮治", cat="C", role="attacker_dp"),    # 經Guts出場的攻擊(ATK+4,對手攔網≤2)
 "P02-077": dict(name="宮兄弟", cat="C", role="twin", atk=3),  # 汎用Guts body, 改名侑/治
 "P02-018": dict(name="宮侑", cat="C", role="guts_engine", tos=2),  # 香草侑 TOS2 Guts引擎
 # --- Event 迴圈回收 ---
 "P02-024": dict(name="北信介", cat="C", role="event_recover", rcv=5),  # 3G+棄1→撿回どんぴ
 # --- 手牌/抽牌/防禦 ---
 "P02-025": dict(name="北信介", cat="C", role="filter", rcv=5),  # 2G 抽1棄1(填墓1)
 "P02-085": dict(name=None, cat="E", role="draw2"),            # 大見太郎 棄1抽2(手牌+1,填墓1)
 "P02-089": dict(name=None, cat="E", role="refuel"),           # どや俺 墓地→手牌+2(消耗墓地名!)
 "P02-084": dict(name=None, cat="E", role="draw1_def"),        # 黒須 抽1+RCV防禦
 "P02-086": dict(name=None, cat="E", role="oentai"),           # 応援団 抽1+弱化對手接球
 "P02-088": dict(name=None, cat="E", role="rev_engine"),       # 双子速攻"裏" 抽1+ATK+1, 治舉侑攻→對手攔網Event不可用(開窗)
 "PR-049":  dict(name="尾白", cat="C", role="ojiro_def", rcv=3),# 2G RCV+3+墓地→手牌
 "P02-022": dict(name="宮治", cat="C", role="def_body", rcv=5, atk=3), # 防禦治 body
 # --- 第3分 finisher / 多樣性 payoff ---
 "P02-027": dict(name="角名", cat="C", role="sune_fin", atk=2),  # 6種橫置0G, 跨回合MB=0
 "P02-021": dict(name="宮治", cat="C", role="osamu_fin", atk=2), # 手牌≤2 ATK+2 0G
 "P02-017": dict(name="宮侑", cat="C", role=" atsumu6", tos=2),  # 6種 TOS+2+墓地→手牌
 "PR-048":  dict(name="宮治", cat="C", role="osamu6", atk=3),    # 6種 ATK+3 (2G)
 "P02-029": dict(name="尾白", cat="C", role="ojiro6", atk=3),    # 6種 ATK+3+否定接球
 # --- 多樣性填充 / body ---
 "P02-035": dict(name="小作", cat="C", role="kosaku_fill"),     # 接球階段自棄 RCV+2(防禦+填墓)
 "P02-030": dict(name="尾白", cat="C", role="body", rcv=4, atk=3),
 "P02-032": dict(name="銀島", cat="C", role="def_body", rcv=5, atk=0, blk=3),
 "P02-028": dict(name="角名", cat="C", role="body", rcv=4, atk=3),
 # --- 新增獨立名字燃料 body(構築顧問建議: 提升 distinct-name 密度) ---
 "P02-031": dict(name="理石", cat="C", role="body", srv=6, atk=3),       # 第9名字, 發球body, 捨得當燃料
 "P02-033": dict(name="大耳", cat="C", role="def_body", rcv=3, blk=3, atk=3),  # 第10名字, MB防禦body
}

def card_name(no): return CARD[no]["name"]
def is_event(no):  return CARD[no]["cat"] == "E"


@dataclass
class P:
    deck: list
    hand: list
    # [校準14] 三個獨立 Guts 池(使用者規則指正): 每張卡在哪個區域就付哪個區域的 Guts,
    #   三池互不流通。舉球区/攻擊区 養 どんぴ 引擎與攻擊型 finisher; 接球区 養防禦/回收。
    #   どんぴ(P02-087) 把 Guts「跳上來」當角色: 落在哪區就付哪區的 Guts。
    g_tos: int = 1       # 舉球区 Guts 池
    g_atk: int = 1       # 攻擊区 Guts 池
    g_rcv: int = 1       # 接球区 Guts 池
    score: int = 0
    opp: int = 0
    grave_names: set = field(default_factory=set)
    grave_list: list = field(default_factory=list)   # 實際墓地內容(供 refuel 消耗)
    guts_zone: list = field(default_factory=list)     # 餵進 Guts 的角色 body(供どんぴ拉出)
    # 場上單佔位
    tos: str = None      # 牌名 in 舉球區
    atk: str = None      # 牌名 in 攻擊區
    rcv_body: int = 0    # 接球區 body RCV
    blk_body: int = 0    # 攔網區 body BLK
    # 旗標
    opp_block_le2: int = 0   # P02-020 遺產: 剩餘回合數 對手攔網≤2
    opp_mb_zero: int = 0     # 角名遺產: 對手 MB BLK=0 回合數
    donpi_fired: int = 0     # 成功發動どんぴ次數
    pending_starve: bool = False  # 早期想發動どんぴ但Guts暫時不足(通常下回合化解)
    pending_fin_starve: bool = False  # 第3分窗口內有finisher但Guts不足(後段力竭)
    guts_starved: bool = False  # 真正的力竭: 整局結束仍卡在Guts不足且未達3分
    thin_hand_pending: bool = False   # 上回合打finisher後手牌薄,本對手回合空窗失防
    hand_crisis: bool = False
    sixtype_turn: int = None
    p1_turn: int = None
    p2_turn: int = None
    p3_turn: int = None

    def discard(self, no):
        self.grave_list.append(no)
        n = card_name(no)
        if n: self.grave_names.add(n)

    def sixtype(self):
        return len(self.grave_names & NAMES) >= 6


def draw(p, k=1):
    for _ in range(k):
        if p.deck:
            p.hand.append(p.deck.pop())


def count(p_deck_or_hand, role=None, no=None):
    if no:   return sum(1 for x in p_deck_or_hand if x == no)
    return sum(1 for x in p_deck_or_hand if CARD[x]["role"] == role)


def has(hand, no=None, role=None):
    if no:   return no in hand
    return any(CARD[x]["role"] == role for x in hand)


def take(hand, no=None, role=None):
    for i, x in enumerate(hand):
        if (no and x == no) or (role and CARD[x]["role"] == role):
            return hand.pop(i)
    return None


def smart_discard(p, rng):
    """棄牌時的真實玩家選擇：優先棄『墓地尚未有的稲荷崎牌名』以推進6種；
    其次棄重複的汎用牌；最後才棄隨機。回傳被棄卡號或 None。"""
    if not p.hand:
        return None
    # 1) 能補新名字的角色牌
    cur = p.grave_names & NAMES
    best_i = None
    for i, x in enumerate(p.hand):
        nm = card_name(x)
        if nm and nm in NAMES and nm not in cur:
            # 不棄掉本回合進攻/finisher 關鍵件(donpi 引擎件除外)
            if CARD[x]["role"] in ("donpi","guts_engine","setter_dp","attacker_dp","twin"):
                continue
            best_i = i; break
    if best_i is None:
        # 2) 棄重複事件或多餘汎用 body
        for i, x in enumerate(p.hand):
            if CARD[x]["role"] in ("body","def_body","draw1_def","oentai"):
                best_i = i; break
    if best_i is None:
        best_i = rng.randrange(len(p.hand))
    d = p.hand.pop(best_i)
    p.discard(d)
    return d


# ---------------------------------------------------------------
# 對手壓力模型：每對手回合的攻擊 vs 我方防禦
# ---------------------------------------------------------------
def opp_pressure(p, rng, mu, sigma, hand_def_k, cfg=None):
    atk = rng.gauss(mu, sigma)
    # [校準12] 規則修正(使用者指正): 攔網(BLK)與接球(RCV)是『分開的階段』,對同一次攻擊
    #   不能相加。先前 defense = rcv_body + blk_body 把兩者疊加 → 高估防禦。
    #   真實: 對手的一次得分嘗試, 防守方只能用其中一個防禦階段的數值去擋(攔網階段用BLK
    #   擋扣球, 或接球階段用RCV承接), 取『單一最佳防禦body』而非兩者之和。
    #   故 base_defense = max(blk_body, rcv_body)。手牌厚度仍提供額外可反應防禦事件的彈性。
    def base_defense():
        return max(p.blk_body, p.rcv_body) + len(p.hand) * hand_def_k
    # [校準11] P02-084 黒須(draw1_def) 是 [=接球] 事件 → 可在『對手攻擊時反應性打出』。
    #   留在手上, 對手強攻時即時打出 → 抽1(補手) + 接球值+2。
    if cfg and cfg.get("kurosu_reactive") and has(p.hand, role="draw1_def"):
        if atk > base_defense() - 2:
            take(p.hand, role="draw1_def")
            draw(p, 1)
            p.rcv_body += 2
            p.discard("P02-084")
    if atk > base_defense():
        p.opp += 1
    # [校準10] 手牌經濟風險: 上個我方回合打 finisher 清空手牌 → 本對手回合空窗失防。
    #   thin_hand_pending 表示上回合 finisher 後手牌 ≤ thin_hand_th。此時對手以
    #   thin_hand_race_bonus 機率額外得分,並把該局標記為 hand-crisis(真實失分向量)。
    if cfg and p.thin_hand_pending:
        if rng.random() < cfg["thin_hand_race_bonus"]:
            p.opp += 1
            p.hand_crisis = True       # 因清手牌失防 → 計入手牌危機
        p.thin_hand_pending = False


# ---------------------------------------------------------------
# 我方一回合策略 (greedy toward 3 points)
# ---------------------------------------------------------------
def my_turn(p, t, rng, cfg):
    draw(p, 1)

    # --- 階段0: 建立舉球區=宮侑(どんぴ前置) ---
    # [校準3] 舉球區的「宮侑」不只香草侑(P02-018)可建立。官方卡池裡 P02-016(setter_dp,
    #   TOS1 的宮侑) 與 P02-077(宮兄弟 twin, 可改名為宮侑) 同樣是合法的宮侑舉球來源。
    #   先前版本只認 guts_engine 一個 role → 387 場無第1分中有 223 場卡在「無舉球宮侑」
    #   (no_setter_zone),把第1分壓到 ~87%。現允許任何宮侑來源建立舉球區:
    #     優先序 = 香草侑(同時是Guts引擎) > P02-016(setter_dp) > 宮兄弟twin。
    #   建立 setter 後若用掉 twin/016, 仍會在下方餵 Guts 補回攻擊端 body。
    if p.tos is None:
        if has(p.hand, role="guts_engine"):
            take(p.hand, role="guts_engine"); p.tos = "宮侑"
        elif has(p.hand, role="setter_dp"):
            # P02-016 雖然也可餵Guts,但建立舉球區的邊際價值更高
            take(p.hand, role="setter_dp"); p.tos = "宮侑"

    # --- Guts 充能: 三個獨立池, 各自靠「該區覆蓋登場」生成 ---
    # [校準14] 使用者規則指正: 三池(舉球/攻擊/接球)獨立, 在哪區付哪區。
    #   • 各區 Guts 唯一來源 = 角色覆蓋登場到「已占用的同區」→ 舊角色變該區 Guts。
    #   • 舉球区: 香草侑/016/twin 持續覆蓋 → +gen_tos/turn(舉球区一旦建立即穩定生成)。
    #   • 攻擊区: 宮治/twin/body 覆蓋 → +gen_atk/turn(攻擊区被使用即生成)。
    #   • 接球区: def_body 覆蓋 → +gen_rcv/turn, 但需手上有 def_body/body 可登場才生成
    #     (沒在跑接球区防禦body時不產 → 接球区 Guts 與防禦牌密度連動, 不再免費)。
    #   先前把三池壓成單一 p.guts → 誤判 PR-049(接球区) 與 どんぴ(舉球/攻擊) 競爭, 屬重大錯誤。
    gen_tos = (cfg or {}).get("gen_tos", 1)
    gen_atk = (cfg or {}).get("gen_atk", 1)
    gen_rcv = (cfg or {}).get("gen_rcv", 1)
    # 把可用的 宮侑/宮治/宮兄弟 body 放進 Guts 區供 どんぴ 拉出
    fed = 0
    for role in ("setter_dp","attacker_dp","twin"):
        while fed < 2 and has(p.hand, role=role):
            no = take(p.hand, role=role)
            p.guts_zone.append(no); fed += 1
    # 舉球区: 一旦建立(p.tos 為宮侑)即每回合覆蓋生成
    if p.tos == "宮侑":
        p.g_tos = min(14, p.g_tos + gen_tos)
    # 攻擊区: 攻擊区被使用(已發過どんぴ 或 Guts區有attacker body)即生成
    if p.donpi_fired > 0 or any(CARD[x]["role"] in ("attacker_dp","twin") for x in p.guts_zone):
        p.g_atk = min(14, p.g_atk + gen_atk)
    # 接球区: 僅在手上有 def_body/body 可覆蓋登場時生成(與防禦牌密度連動)
    if any(CARD[x]["role"] in ("def_body","body","ojiro_def","filter","event_recover") for x in p.hand):
        p.g_rcv = min(14, p.g_rcv + gen_rcv)

    # --- 抽牌/補手 事件(維持手牌差, 對抗 hand-crisis) ---
    # [校準11] kurosu_reactive 開啟時, 黒須(draw1_def)『留在手上』供對手回合反應性防禦,
    #   不在我方回合主動打掉; 故從主動抽牌循環中排除 draw1_def。
    proactive_draw = ["draw2","refuel","oentai","rev_engine"]
    if not (cfg and cfg.get("kurosu_reactive")):
        proactive_draw.insert(2, "draw1_def")
    for role in proactive_draw:
        while has(p.hand, role=role):
            no = take(p.hand, role=role)
            if role == "draw2":            # 大見: 棄1抽2 (手牌淨+1, 填墓1)
                smart_discard(p, rng); draw(p, 2); p.discard(no)
            elif role == "refuel":         # どや俺: 墓地撿侑/治/兄弟回手(+2)
                got = 0
                for target in ("宮侑","宮治","宮兄弟"):
                    for i,gc in enumerate(p.grave_list):
                        if card_name(gc) == target:
                            p.hand.append(p.grave_list.pop(i)); got += 1
                            if not any(card_name(x)==target for x in p.grave_list):
                                p.grave_names.discard(target)   # 6種可能倒退!
                            break
                if got >= 3:
                    smart_discard(p, rng)
                p.discard(no)
            elif role == "draw1_def":
                draw(p,1); p.rcv_body = max(p.rcv_body, 2); p.discard(no)
            elif role == "oentai":
                draw(p,1); p.discard(no)
            elif role == "rev_engine":
                # P02-088 双子速攻"裏": 抽1; 若已2分且舉球宮侑在場(治舉侑攻的鏡像條件
                #   在本引擎以「舉球=宮侑、攻擊宮治」近似),開「對手攔網Event不可用」窗口,
                #   等價於 opp_block_le2 → 給第3分 finisher 另一條開窗路線(不耗6種/不耗Guts)。
                draw(p,1)
                if p.score >= 2 and p.tos == "宮侑":
                    p.opp_block_le2 = max(p.opp_block_le2, 2)
                p.discard(no)

    # --- 主動填墓 + 防禦: 小作(接球階段自棄 RCV+2) ---
    while has(p.hand, role="kosaku_fill"):
        no = take(p.hand, role="kosaku_fill")
        p.discard(no); p.rcv_body = max(p.rcv_body, 2)

    # --- 主動回收どんぴ: 若手上沒どんぴ但墓地有、且有 P02-024(event_recover, 3G) ---
    # [校準6] P02-024 的本職就是「把どんぴ撈回手循環」。先前只在『防禦填空』與『發動後』
    #   兩個窄口子觸發 → 132 場無第1分是『手上沒どんぴ』。真實玩家在前置已備妥(舉球+攻擊
    #   body)卻缺どんぴ時,會主動花 3G 用 P02-024 撈回どんぴ。此處補上這條主動回收,
    #   讓どんぴ可得性貼近實戰,第1分/第2分達錨點。
    donpi_ready_to_fire = (p.tos == "宮侑") and any(
        CARD[x]["role"] in ("attacker_dp","twin") for x in p.guts_zone)
    if (donpi_ready_to_fire and not has(p.hand, role="donpi")
            and "P02-087" in p.grave_list and has(p.hand, role="event_recover")
            and p.g_rcv >= 3):                       # P02-024 在接球区 → 付接球区 Guts
        take(p.hand, role="event_recover"); p.g_rcv -= 3
        smart_discard(p, rng)
        p.grave_list.remove("P02-087"); p.hand.append("P02-087")
        p.rcv_body = max(p.rcv_body, 5)

    # --- 防禦 body 部署到接球區(付接球区 Guts, 與 どんぴ 的舉球/攻擊池獨立) ---
    if p.rcv_body < 4:
        for role in ("def_body","ojiro_def","filter","event_recover","body"):
            if has(p.hand, role=role):
                no = p.hand[[CARD[x]["role"] for x in p.hand].index(role)]
                gcost = {"event_recover":3,"filter":2,"ojiro_def":2}.get(role,0)
                if p.g_rcv < gcost:                  # 接球区 Guts 不足則略過
                    continue
                take(p.hand, role=role); p.g_rcv -= gcost
                p.rcv_body = max(p.rcv_body, CARD[no].get("rcv",0))
                if role == "filter":               # 抽1棄1(智慧棄→填墓新名)
                    draw(p,1); smart_discard(p, rng)
                elif role == "event_recover":      # 棄1撿どんぴ回手
                    smart_discard(p, rng); p.hand.append("P02-087")
                elif role == "ojiro_def":          # 墓地角色→手牌(補手)
                    for i,gc in enumerate(p.grave_list):
                        if not is_event(gc):
                            p.hand.append(p.grave_list.pop(i)); break
                break

    # ============ 進攻：どんぴしゃり 迴圈 ============
    def precondition():
        # 舉球=宮侑(香草) 且 攻擊=宮治(由 Guts 區 twin/治 改名上場)
        if p.tos is None and has(p.hand, role="guts_engine"):
            take(p.hand, role="guts_engine"); p.tos = "宮侑"
        if p.atk in (None, "宮治"):
            p.atk = "宮治"
        return p.tos == "宮侑" and p.atk == "宮治"

    def guts_has(nm):
        return any(card_name(x)==nm or CARD[x]["role"] in (
            ("setter_dp",) if nm=="宮侑" else ("attacker_dp",)) for x in p.guts_zone)

    if has(p.hand, role="donpi") and precondition():
        # [校準4] 發動需「舉球宮侑 + 攻擊宮治」。舉球端在階段0已可由 P02-016/香草侑/twin
        #   建立在舉球區; 因此 have_setter 改為「舉球區已是宮侑(p.tos) 或 Guts區仍有
        #   setter/twin body」皆可滿足 — 不再強制一定要在 Guts 區留一個 setter body。
        #   這移除了先前的雙重硬閘(同時要兩個 body 都在 Guts 區)導致的首發拖延。
        #   攻擊端(宮治)仍需一個 attacker/twin body 在 Guts 區供どんぴ拉出。
        have_setter = (p.tos == "宮侑") or any(
            CARD[x]["role"] in ("setter_dp","twin") for x in p.guts_zone)
        have_atkr   = any(CARD[x]["role"] in ("attacker_dp","twin") for x in p.guts_zone)
        # [校準14] どんぴ 把 Guts 跳上來當角色: 宮侑落舉球区 → 付舉球区 Guts(cost_tos);
        #   宮治落攻擊区 → 付攻擊区 Guts(cost_atk)。兩池獨立扣。舉球已在場時舉球側成本減半。
        cost_atk = (cfg or {}).get("donpi_atk_cost", 2)
        cost_tos = (cfg or {}).get("donpi_tos_cost", 1) if (p.tos == "宮侑") else \
                   (cfg or {}).get("donpi_tos_cost", 1) + 1
        if have_setter and have_atkr:
            if p.g_tos >= cost_tos and p.g_atk >= cost_atk:
                p.g_tos -= cost_tos; p.g_atk -= cost_atk
                take(p.hand, role="donpi")
                draw(p, 2)                       # どんぴ抽1 + P02-016抽1
                p.opp_block_le2 = 2              # P02-020: 對手攔網≤2
                p.donpi_fired += 1
                # 從 Guts 區消耗被拉出的 body, 入墓(留名字推進6種)
                # 舉球已在場時只消耗攻擊端; 否則兩端都從 Guts 區拉。
                wants = [("attacker_dp","twin")]
                if p.tos != "宮侑":
                    wants = [("setter_dp","twin"), ("attacker_dp","twin")]
                for want in wants:
                    for i,x in enumerate(p.guts_zone):
                        if CARD[x]["role"] in want:
                            p.discard(p.guts_zone.pop(i)); break
                p.pending_starve = False    # 成功發動 → 清除暫時性 Guts 不足
                if rng.random() < cfg["donpi_score_p"]:
                    p.score += 1
                    if p.score==1 and p.p1_turn is None: p.p1_turn=t
                    if p.score==2 and p.p2_turn is None: p.p2_turn=t
                # P02-024 撿回どんぴ(接球区 3G + 棄1) 維持迴圈
                if has(p.hand, role="event_recover") and p.g_rcv>=3:
                    take(p.hand, role="event_recover"); p.g_rcv-=3
                    smart_discard(p, rng); p.hand.append("P02-087")
                    p.rcv_body = max(p.rcv_body, 5)
            else:
                # [校準7] guts_starved 語意修正: 早期(turn 2-3)前置已備妥卻暫時 Guts 不足
                #   只是「等一回合 regen」的暫時現象,下一回合通常就發動了 — 不應永久把整局
                #   標記為 guts-starved(這會嚴重低估第1/2分穩定度)。改為設 pending_starve,
                #   只有在「成功發動則清除」「整局結束仍未化解」時才算真正的 guts-starved。
                #   這對應使用者實戰的「打完兩個10點就沒力」: 真正的力竭發生在後段無法再續力,
                #   而非開局抽序造成的一回合延遲。
                p.pending_starve = True

    # ============ 第3分 finisher (僅在已 2 分後嘗試) ============
    if p.score >= 2:
        if p.sixtype() and p.sixtype_turn is None:
            p.sixtype_turn = t
        # 路線A: 角名橫置(0G) 鋪 MB=0(跨回合) → 下回合宮治R 收尾
        # [校準10b] 角名鋪設這一回合「沒得分卻佔了攻擊區」,是路線A的跨回合空窗。
        #   此回合結束後對手有一整回合可施壓; 若此時手牌薄,風險升高 → thin_hand。
        if p.opp_mb_zero == 0 and p.sixtype() and has(p.hand, role="sune_fin"):
            take(p.hand, role="sune_fin"); p.opp_mb_zero = 2; p.atk = "角名"
            if len(p.hand) <= cfg["thin_hand_th"]:
                p.thin_hand_pending = True
        finisher_window = (p.opp_mb_zero > 0 or p.opp_block_le2 > 0)
        if finisher_window and p.score == 2:
            fin = None
            # [校準8] 第3分 Guts 力竭建模(使用者「打完兩個10點就沒力」的核心):
            #   在窗口內手上已有 6種型 finisher(osamu6/ojiro6)但 Guts 不足以支付 →
            #   這是真正的後段力竭。記 pending_fin_starve。0G 的 osamu_fin 不受此限。
            need_g_blocked = False
            # [校準10c] 宮治R(osamu_fin): 條件是「出場後手牌≤2」。若手牌過厚,玩家會
            #   主動棄牌把手清到 ≤3 以滿足條件 — 這正是使用者說的「清空手牌打 finisher」,
            #   代價是下回合空窗失防。帶手牌補充的牌組較少需要狠清手 → thin 風險低。
            if has(p.hand, role="osamu_fin"):
                # 為了讓宮治R出場後手牌≤2, 出場前需手牌≤3; 否則主動棄到3
                if len(p.hand) > 3:
                    while len(p.hand) > 3:
                        smart_discard(p, rng)
                fin = take(p.hand, role="osamu_fin")            # 0 Guts
            elif p.sixtype() and has(p.hand, role="osamu6"):    # PR-048 攻擊区 2G
                if p.g_atk>=2: fin = take(p.hand, role="osamu6"); p.g_atk-=2
                else: need_g_blocked = True
            elif p.sixtype() and has(p.hand, role="ojiro6"):    # P02-029 攻擊区 3G
                if p.g_atk>=3: fin = take(p.hand, role="ojiro6"); p.g_atk-=3
                else: need_g_blocked = True
            if fin is not None:
                p.atk = card_name(fin)
                # 打出 finisher 後若手牌薄 → 下對手回合空窗風險(thin_hand_pending)。
                if len(p.hand) <= cfg["thin_hand_th"]:
                    p.thin_hand_pending = True
                if rng.random() < cfg["finisher_score_p"]:
                    p.score = 3; p.p3_turn = t; p.pending_fin_starve = False
            elif need_g_blocked:
                p.pending_fin_starve = True

    # [校準13] 移除每回合 Guts regen(原 +2~4)。Guts 為消耗型資源, 唯一來源是回合開始
    #   的 1 次充能(上方 feed)。香草侑 TOS 引擎不再被當成 Guts 來源(它的價值在前置/抽牌)。
    p.opp_block_le2 = max(0, p.opp_block_le2-1)
    p.opp_mb_zero  = max(0, p.opp_mb_zero-1)
    # 手牌危機: 手空且牌庫將盡且未達3分
    if len(p.hand)==0 and len(p.deck)<=1 and p.score<3:
        p.hand_crisis = True


def build_deck(cfg_counts):
    deck = []
    for no,c in cfg_counts.items():
        deck += [no]*c
    return deck


def simulate(cfg_counts, n=4000, cfg=None, seed=0):
    cfg = cfg or {}
    cfg.setdefault("donpi_score_p", 0.90)
    cfg.setdefault("finisher_score_p", 0.85)
    # [校準9] 對手壓力參數校準至實戰錨點(1分≈97-99%,2分≈90-93%)。
    #   先前 mu=5.2/k=0.9 把前兩分壓到 ~87/87%,與使用者「前兩分非常穩定」不符。
    #   稲荷崎前期手牌厚、防禦body足,對手在前段難得分,故下調 mu→4.6、上調手牌防禦
    #   權重 k→1.1。校準後 M4: 1分≈97%、2分≈91%,落在錨點區間。
    cfg.setdefault("opp_mu", 4.6)
    cfg.setdefault("opp_sigma", 2.3)
    cfg.setdefault("hand_def_k", 1.1)
    cfg.setdefault("max_turn", 16)
    # [校準14] 三個獨立 Guts 池的每回合生成率(各區覆蓋登場)。三池互不流通:
    #   • gen_tos(舉球区): 養 どんぴ 的設置側。舉球区一建立即穩定生成。
    #   • gen_atk(攻擊区): 養 どんぴ 攻擊側 + 攻擊型 finisher(PR-048 2G / P02-029 3G)。
    #     這是第三分的真瓶頸池 — 前兩分どんぴ 把它耗掉 → Guts型 finisher 易力竭。
    #   • gen_rcv(接球区): 養防禦/回收(P02-024/025, PR-049)。與 どんぴ 無關! 故 PR-049
    #     的成本完全不與どんぴ競爭 — 先前單池模型誤砍 PR-049 是錯誤,已修正。
    cfg.setdefault("gen_tos", 1)
    cfg.setdefault("gen_atk", 1)
    cfg.setdefault("gen_rcv", 1)
    cfg.setdefault("donpi_atk_cost", 2)
    cfg.setdefault("donpi_tos_cost", 1)
    # [校準10] 手牌經濟: finisher 清手牌的回合,若手牌薄,跨回合空窗失去防禦,
    #   對手 race 得分機率提高(thin_hand_race_bonus),並把該情形計為 hand-crisis。
    # 校準後 th=2: 對應宮治R「出場後手牌≤2」的實況 — 打完 finisher 手牌≤2 即薄手,
    #   下回合空窗對手以 45% 機率多得 1 分並計 hand-crisis。這讓手牌經濟成為可被牌組
    #   設計影響的真實向量(帶手牌補充者 hand-crisis 顯著較低)。
    cfg.setdefault("thin_hand_th", 2)          # finisher 後手牌 ≤ 此值 視為薄手
    cfg.setdefault("thin_hand_race_bonus", 0.45)  # 薄手回合對手額外得分機率
    # [校準11] 黒須 P02-084 反應性防禦建模(預設開). 牌組無 084 時為 no-op(不影響其他牌表)。
    cfg.setdefault("kurosu_reactive", True)
    rng = random.Random(seed)

    res = dict(p1=0,p2=0,p3=0,stable3=0,guts_starved=0,hand_crisis=0,
               race_loss=0,sixtype=0,sum3turn=0,n3=0)
    base = build_deck(cfg_counts)
    total = len(base)
    if total != 40:
        return {"ERROR": f"deck={total}張(需40)"}

    for g in range(n):
        d = base[:]
        rng.shuffle(d)
        hand = [d.pop() for _ in range(5)]
        p = P(deck=d, hand=hand)
        for t in range(1, cfg["max_turn"]+1):
            my_turn(p, t, rng, cfg)
            if p.score>=3: break
            # 對手回合
            opp_pressure(p, rng, cfg["opp_mu"], cfg["opp_sigma"], cfg["hand_def_k"], cfg)
            if p.opp>=3:
                res["race_loss"]+=1; break
        # [校準7] 結算: 未達3分 且(早期どんぴ力竭未化解 或 第3分finisher力竭未化解)
        #   → 真正的 guts_starved。早期暫時不足若後來成功發動(pending_starve已清)則不計。
        if p.score < 3 and (p.pending_starve or p.pending_fin_starve):
            p.guts_starved = True
        if p.p1_turn: res["p1"]+=1
        if p.p2_turn: res["p2"]+=1
        if p.score>=3:
            res["p3"]+=1
            res["sum3turn"]+=p.p3_turn or t; res["n3"]+=1
            if not p.guts_starved and not p.hand_crisis:
                res["stable3"]+=1
        if p.guts_starved: res["guts_starved"]+=1
        if p.hand_crisis: res["hand_crisis"]+=1
        if p.sixtype(): res["sixtype"]+=1

    out = {k: (v/n if k not in("sum3turn","n3") else v) for k,v in res.items()}
    out["avg3turn"] = (res["sum3turn"]/res["n3"]) if res["n3"] else None
    out["deck_total"]=total
    return out


# ---- 預設牌表 ----
PRESETS = {
 "M4": {  # 現行終版(校準後 stable3≈82%)
   "P02-087":4,"P02-085":2,"P02-089":1,"P02-084":1,
   "P02-016":2,"P02-020":2,"P02-077":4,"P02-018":3,
   "P02-027":2,"P02-021":3,"P02-017":2,"PR-048":2,"P02-029":2,
   "P02-024":3,"P02-035":2,"P02-025":2,"P02-028":1,"P02-030":1,"P02-032":1,
 },
 # 三方協作終版(含理石P02-031, 現已升級為V2)。N=20000: stable3=82.4%, race-loss=3.0%.
 "FINAL": {
   "P02-087":4,"P02-085":2,"P02-088":2,
   "P02-016":2,"P02-020":2,"P02-077":4,"P02-018":3,
   "P02-027":2,"P02-021":2,"P02-017":2,"PR-048":2,"P02-029":2,
   "P02-024":3,"P02-025":2,"P02-035":2,"PR-049":1,
   "P02-028":1,"P02-031":1,"P02-033":1,
 },
 # v2: 理石→銀島。N=20000(guts_gen=1修正模型): stable3=76.8%, race-loss=1.7%.
 # 校準13後降至76.8%(原81.8%是 Guts 灌水結果)。→ 已升級為 FINAL_V3。
 "FINAL_V2": {
   "P02-087":4,"P02-085":2,"P02-088":2,
   "P02-016":2,"P02-020":2,"P02-077":4,"P02-018":3,
   "P02-027":2,"P02-021":2,"P02-017":2,"PR-048":2,"P02-029":2,
   "P02-024":3,"P02-025":2,"P02-035":2,"PR-049":1,
   "P02-028":1,"P02-032":1,"P02-033":1,
 },
 # ★★ v3 低-Guts 優化版 (2026-06, 基於校準13誠實guts_gen=1模型) ★★
 # 核心調整: P02-021(宮治R) ×2→×4(0G finisher MAX, 手牌≤2觸發);
 #   P02-020(攻擊端body) ×2→×3(Guts zone 更穩定); P02-025 ×2→×1;
 #   移除 P02-029(3G finisher), P02-028×1, PR-049(2G defense overhead);
 #   P02-032(銀島,0G def_body)×1→×2, P02-033(大耳)×1→×2.
 # 效果: stable3 76.8%→82.2%(+5.4%), guts-starved 3.9%→1.5%,
 #   淨勝率 75.4%→79.6%, 平均第3分回合 10.7→9.5. (N=50000, seed=42)
 "FINAL_V3": {
   "P02-087":4,"P02-085":2,"P02-088":2,
   "P02-016":2,"P02-020":3,"P02-077":4,"P02-018":3,
   "P02-027":2,"P02-021":4,"P02-017":2,"PR-048":2,
   "P02-024":3,"P02-025":1,"P02-035":2,
   "P02-032":2,"P02-033":2,
 },
 # v3 對「攻擊型 ATK≈8」 sideboard: P02-088×1→P02-084×1 黒須反應性防禦。
 "VS_AGGRO_V3": {
   "P02-087":4,"P02-085":2,"P02-088":1,"P02-084":1,
   "P02-016":2,"P02-020":3,"P02-077":4,"P02-018":3,
   "P02-027":2,"P02-021":4,"P02-017":2,"PR-048":2,
   "P02-024":3,"P02-025":1,"P02-035":2,
   "P02-032":2,"P02-033":2,
 },
 # ★★★ v4 三池模型版 (2026-06, 校準14: 三個獨立 Guts 池) ★★★
 # 使用者規則指正: 舉球/攻擊/接球三池獨立, 在哪區付哪區。接球区防禦(PR-049/024/025)
 #   與 どんぴ(舉球/攻擊池) 完全不競爭 → v3 誤砍的 PR-049 應恢復, 並可加厚接球区防禦。
 # 核心調整 (vs v3): 恢復 PR-049×1; P02-025 ×1→×2(接球区抽棄補手抗hand-crisis);
 #   P02-035 ×2→×1; P02-033 ×2→×1. 接球区防禦加厚但完全不拖累攻擊引擎。
 # 效果(N=20000×6 seeds): 淨勝率 79.0%→80.2%, race-loss 3.8%→2.8%(接球区防禦免費),
 #   stable3 83.0%, 6種 57%, 平均第3分回合 9.0. (三池模型, guts-starved 已近0)
 "FINAL_V4": {
   "P02-087":4,"P02-085":2,"P02-088":2,
   "P02-016":2,"P02-020":3,"P02-077":4,"P02-018":3,
   "P02-027":2,"P02-021":4,"P02-017":2,"PR-048":2,
   "P02-024":3,"P02-025":2,"P02-035":1,"PR-049":1,
   "P02-032":2,"P02-033":1,
 },
}


def fmt(o):
    if "ERROR" in o: return o["ERROR"]
    a3 = f"{o['avg3turn']:.1f}" if o['avg3turn'] else "—"
    return (f"  1分 {o['p1']:.1%} | 2分 {o['p2']:.1%} | 3分 {o['p3']:.1%} "
            f"| 穩定3分 {o['stable3']:.1%}\n"
            f"  guts-starved {o['guts_starved']:.1%} | hand-crisis {o['hand_crisis']:.1%} "
            f"| race-loss {o['race_loss']:.1%} | 6種達標 {o['sixtype']:.1%} "
            f"| 平均第3分回合 {a3}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="FINAL_V4")
    ap.add_argument("--deck", default=None, help="JSON {card_no:count}")
    ap.add_argument("--n", type=int, default=4000)
    a = ap.parse_args()
    counts = json.loads(a.deck) if a.deck else PRESETS[a.preset]
    o = simulate(counts, n=a.n)
    print(f"[{a.preset if not a.deck else 'custom'}] N={a.n}")
    print(fmt(o))
