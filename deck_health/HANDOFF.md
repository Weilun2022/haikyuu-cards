# deck_health 交接說明（給接手的 AI）

## 這是什麼
バボカ!! BREAK 卡組健檢系統。核心是 `sim2.py`：兩副牌依官方規則實際對打（総合ルール v1.03 第 5 章、規則表）。
已用使用者的實戰經驗校準：平均進攻 ≈5、進攻 ≥8 約 15～19%、結束時牌庫剩 7～12 張、鏡像對打 ≈50%。

## 檔案
| 檔案 | 用途 |
|---|---|
| `sim2.py` | 雙人對打引擎（攔網／接球二選一、攔回 0 點球、Guts 分區、人名規則、局間補牌與 Set 牌） |
| `manual_cards.py` | 已人工結構化、使用者驗收過的 17 張卡（依日文原文） |
| `schema.md` | 卡片效果結構定義 |
| `template.py` | 通用卡型（不綁學校）配比搜尋 |
| `compare2.py` | 實際牌組：換卡方案 vs 原牌組對打 |
| `report2.py` / `trace2.py` | 統計／逐拍印出一場對局 |
| `deck.json` | 使用者的烏野(3彈)(白鳥) 40 張 |
| `sim.py` `report.py` `trace.py` `verify.py` | 舊版（固定門檻對手），**已被 sim2 取代，不要用來下結論** |

## 取得與交回（git 分支 `deck-health`）
本機 repo：`C:\Users\evils\Documents\Claude\Claude Code\排球少年`
```
git fetch origin
git checkout deck-health
cd deck_health
```
做完後把 `results.md`（以及你改過的 `template.py`）commit 到 `deck-health` 分支並 push。不要 merge 到 main，不要動 deck_health 以外的檔案。

## 執行（Windows，在 deck_health 資料夾內）
```
set PYTHONIOENCODING=utf-8
python -I template.py vs 2000 out.jsonl <基準配比> <配比1> <配比2> ...
```
需要卡片資料的指令（compare2.py、待辦 3）用 `..\cards_data.js`。
配比格式：`事件,接球,舉球,攻擊[,接球6張數,舉球2張數]`，例如 `8,11,9,12,2,4`。
`vs` 模式 = 第一個配比當基準，其餘各自與基準對打；`duel` 模式 = 兩兩對打。
2000 場約 35 秒（2 核心）。實際牌組請改 `compare2.py ..\cards_data.js deck.json variants.json 2000 out.jsonl`。

## 鐵則（違反就會重蹈舊系統的錯）
1. 結論只能來自 sim2 對打勝率，並附場數 N 與標準誤 SE；差距 < 2×SE 一律寫「無差異」
2. 不要用「起手 6 張超幾何機率」「死手率」「COPIES_RULES」當結論。所有角色都能接球／舉球／攻擊，只是數值不同；起手機率不含每拍手牌 −2、補牌、Guts、對手
3. 不要用舊系統（deck_optimizer/、card_synergy_cli.py、audit_system.py）
4. 卡片效果以日文 skill_jp 為準；要新增卡片到 manual_cards.py，必須逐張讓使用者驗收中文反向翻譯（verify.py 可產生）
5. 規則有疑問先查 Project 文件「健檢系統_規則庫」，不要自己假設
6. 為了省 token：長輸出寫進檔案，對話中只貼摘要表格

## 已知結論（不要重跑）
- 事件放滿 8 張比 6 張好（約 +1.6%）
- 通用配比平坦最佳區：事件 8／接球 10～11／舉球 8～10／攻擊 11～14（前四名差距在 ±1.1% 內）
- 使用者實際牌組：舉球手 9～10 張最佳，11 張或 7 張明顯變差（各 −3%，8000 場）
- 高球進攻放第 3 張會變差（Event 區 ≤2 張限制）
- 接球 6、舉球 2 越多越好（舉球 2 約 6 張飽和）；503 約 4 張飽和、013 放 2～4 張皆為正收益（見 results.md 的 Claude 審查段落）
- 比較卡型時只能改一個變因：替換卡要沿用被替換卡的技能比例，也不能順便擠掉其他高數值卡（503／013 第一版就是這樣量錯的）

## 待辦（依序做，做完交回）
1. 量化接球 6、舉球 2 的張數：
   `python -I template.py vs 2000 qual.jsonl 8,11,9,12,2,4 8,11,9,12,0,4 8,11,9,12,1,4 8,11,9,12,3,4 8,11,9,12,4,4 8,11,9,12,2,1 8,11,9,12,2,2 8,11,9,12,2,6 8,11,9,12,2,7`
2. 加入雙重卡型，回答「503 要幾張、013 要幾張」：
   - 在 `template.py` 的 ARCH 加入（卡池平均值）：
     - `RA`（503，可攻可守）：srv 1, blk 1, rcv 5, tos 0, atk 3，position 'WS'
     - `SA`（013，可舉可攻）：srv 1, blk 1, rcv 1, tos 1, atk 3，position 'S'
   - `make_deck` 加參數 `nRA`、`nSA`（從接球手／舉球手的張數中替換，總數維持 40）
   - 以 `8,11,9,12,2,4` 為基準，測 nRA = 0,2,4,6,8 與 nSA = 0,2,4,6,8
   - 注意：卡池 R+A 只有 10 種卡號、S+A 22 種、接球 6 有 10 種，結論要附「卡池裡做得出來嗎」
3. 卡池可行性：用 cards_data.js 統計主要學校（烏野、稲荷崎、音駒、白鳥沢、青葉城西、伊達工業、梟谷）各卡型的卡號數，列表
4. 結果寫進 `results.md`（表格：配比、勝率、SE、N、結論），commit 並 push 到 `deck-health` 分支，然後停止，交回 Claude
