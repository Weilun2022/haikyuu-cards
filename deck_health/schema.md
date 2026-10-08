# 卡片效果結構（schema v0）

每張卡 = `{card_no, source, skills: [skill...]}`
- `source`: `manual`（人工依日文原文建立）或 `parser`（程式解析）
- 日文原文 `skill_jp` 是唯一依據；中文只用來反向對照

## skill
| 欄位 | 意義 |
|---|---|
| `timing` | `on_enter` 登場時 / `trigger` 常駐觸發 / `from_hand` 從手牌發動 / `event` 事件牌打出 |
| `zones` | 技能生效的區域：`serve` `block` `receive` `toss` `attack`（`on_enter` 指登場到這些區域時） |
| `phases` | 事件牌可打出的階段：`draw` `receive` `toss` `attack` `block` |
| `trigger` | `timing=trigger` 時的觸發條件 |
| `conditions` | 發動條件（全部成立才可發動） |
| `cost` | 代價（付不起就不能發動） |
| `effects` | 依序執行的效果 |
| `once_per_turn` | 每回合一次 |

## 主體
所有 `who` / `target` 欄位只能是 `self`（自己）或 `opp`（對手），不可省略。

## conditions 類型
- `set_total_le {n}` 雙方 Set 牌合計 ≤ n
- `opp_op_le {n, of}` / `opp_op_ge {n, of}` 對手進攻值（`of`: `serve` / `attack` / `serve_or_attack`）
- `opp_hand_le {n}` 對手手牌 ≤ n
- `self_role_name {role, name}` 自己某位置角色是某人名（`role`: `toss` / `attack`）
- `self_is_role {role}` 此角色是某位置角色
- `event_zone_count_le {who, card_name, n, includes_self}` Event 區某卡張數 ≤ n
- `event_zone_phase_count_ge {who, phases, n}` Event 區可在某些階段打出的牌合計 ≥ n

## cost 類型
- `guts {n}` 從此卡底下支付 n Guts（移到棄牌區）
- `mill {who, n}` 棄置某方牌庫頂 n 張
- `discard_hand {n}` 從手牌棄置 n 張（任意）
- `discard_this_from_hand` 從手牌棄置此卡
- `this_to_deck_bottom` 此卡放到牌庫底

## effects 類型
- `draw {who, n}`
- `stat_add {target, stat, n}` / `stat_set {target, stat, value}`
  - `target`: `this` / `that`（觸發對象）/ `choose {who, count, school?, role?, name?}`
  - `stat`: `srv` `blk` `rcv` `tos` `atk` `any`
- `stat_cap {target, stat, below, source, duration}` 數值因技能不會達到某值
- `reveal_top_take {who, n, names, max, rest}` 公開牌庫頂，挑指定牌加入手牌，其餘放 `rest`
- `aura_on_enter {who, name, zone, stat, n, duration}` 期間內某人名角色每次出場時加值
- `drop_to_hand {who, filter, max}` 從棄牌區加入手牌
- `drop_to_zone {who, name, zone, max}` 從棄牌區登場到某區（`mandatory` 表示必須盡可能執行）
- `guts_to_zone {who, zone, filter, max}` 某區的 Guts 登場到該區
- `event_to_hand {who, filter, max}` 從 Event 區加入手牌
- `restrict_opp {rule, ..., duration}` 限制對手
- `on_opp_non_draw_add_mill {n, duration}` 對手以抽牌以外方式加入手牌時，棄置對手牌庫頂 n 張
- `keyword {name, n}` 關鍵字技能（例：A傳球、一觸）

## duration
`this_turn` 此回合 / `next_opp_turn` 對手下一回合
