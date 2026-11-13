# -*- coding: utf-8 -*-
"""
special_cards_data.py - 特殊卡判定表（人工維護）

「特殊卡」＝會干擾對手、而且干擾那一段效果不依賴另一張指定卡片的強力單卡。
首頁搜尋列打「特殊卡」「通用特殊卡」「封鎖卡」等詞，就是靠這份表找卡。

這份表是人工判定的結果，不能用關鍵字規則重建或自動判定。
判定準則、分級表、邊界判例見 docs/translation/SPECIAL_CARDS.md。

範圍：任一版本的效果文字（skill）含「相手」的卡號，都要在這裡有一筆，
判定「算」或「不算」都要記——這樣 check_special_cards.py 才分得出
「判過了、不算」與「還沒判」。同卡號的不同版本共用一筆。

怎麼新增一筆（出新彈時，python check_special_cards.py 會列出還沒判的卡號）：
  算：{"card_no": "...", "verdict": "special", "tier": "通用", "kind": "封鎖", "note": "卡名"}
      tier：通用／學校
      kind：封鎖／無效／破壞／懲罰／削弱
  不算：{"card_no": "...", "verdict": "excluded", "reason": "綁人名", "note": "卡名"}
      reason：綁人名／純數值削弱／只讀對手狀態／不划算／自保或雙方對等
note 只給人看（通常寫中文卡名），程式不讀。請照卡號排序插入。
拿不準的卡不要硬判，先問維護者。
"""

SPECIAL_CARD_ENTRIES = [
    {"card_no": "HV-D01-003", "verdict": "excluded", "reason": "只讀對手狀態", "note": "月島螢"},
    {"card_no": "HV-D01-012", "verdict": "excluded", "reason": "綁人名", "note": "背後時間差攻擊"},
    {"card_no": "HV-D02-001", "verdict": "excluded", "reason": "純數值削弱", "note": "孤爪研磨"},
    {"card_no": "HV-D03-003", "verdict": "excluded", "reason": "純數值削弱", "note": "宮侑"},
    {"card_no": "HV-D04-002", "verdict": "excluded", "reason": "只讀對手狀態", "note": "岩泉一"},
    {"card_no": "HV-D04-005", "verdict": "excluded", "reason": "只讀對手狀態", "note": "金田一勇太郎"},
    {"card_no": "HV-P01-002", "verdict": "special", "tier": "通用", "kind": "封鎖", "note": "日向翔陽"},
    {"card_no": "HV-P01-003", "verdict": "excluded", "reason": "綁人名", "note": "日向翔陽"},
    {"card_no": "HV-P01-010", "verdict": "excluded", "reason": "純數值削弱", "note": "山口忠"},
    {"card_no": "HV-P01-025", "verdict": "special", "tier": "通用", "kind": "削弱", "note": "灰羽利耶夫"},
    {"card_no": "HV-P01-032", "verdict": "special", "tier": "通用", "kind": "無效", "note": "手白球彦"},
    {"card_no": "HV-P01-033", "verdict": "special", "tier": "學校", "kind": "破壞", "note": "及川徹"},
    {"card_no": "HV-P01-034", "verdict": "special", "tier": "學校", "kind": "破壞", "note": "及川徹"},
    {"card_no": "HV-P01-035", "verdict": "special", "tier": "學校", "kind": "封鎖", "note": "岩泉一"},
    {"card_no": "HV-P01-037", "verdict": "excluded", "reason": "只讀對手狀態", "note": "松川一靜"},
    {"card_no": "HV-P01-039", "verdict": "excluded", "reason": "只讀對手狀態", "note": "渡親治"},
    {"card_no": "HV-P01-041", "verdict": "excluded", "reason": "只讀對手狀態", "note": "國見英"},
    {"card_no": "HV-P01-051", "verdict": "excluded", "reason": "只讀對手狀態", "note": "鷲尾辰生"},
    {"card_no": "HV-P01-057", "verdict": "special", "tier": "通用", "kind": "懲罰", "note": "天童覺"},
    {"card_no": "HV-P01-060", "verdict": "excluded", "reason": "只讀對手狀態", "note": "百澤雄大"},
    {"card_no": "HV-P01-065", "verdict": "excluded", "reason": "只讀對手狀態", "note": "北信介"},
    {"card_no": "HV-P01-066", "verdict": "special", "tier": "學校", "kind": "破壞", "note": "星海光來"},
    {"card_no": "HV-P01-074", "verdict": "excluded", "reason": "只讀對手狀態", "note": "烏養一繋"},
    {"card_no": "HV-P01-079", "verdict": "excluded", "reason": "純數值削弱", "note": "我可一毫米都沒想過要靠自己一個人贏"},
    {"card_no": "HV-P01-080", "verdict": "excluded", "reason": "只讀對手狀態", "note": "猫又育史"},
    {"card_no": "HV-P01-084", "verdict": "excluded", "reason": "綁人名", "note": "「助跑」是翔陽的翅膀呢"},
    {"card_no": "HV-P01-087", "verdict": "excluded", "reason": "綁人名", "note": "我也是這麼想的☆"},
    {"card_no": "HV-P01-090", "verdict": "special", "tier": "學校", "kind": "懲罰", "note": "差別就在於——有沒有「那一瞬間」"},
    {"card_no": "HV-P01-091", "verdict": "excluded", "reason": "純數值削弱", "note": "這可不是音駒的專利啊！"},
    {"card_no": "HV-P01-093", "verdict": "special", "tier": "通用", "kind": "封鎖", "note": "無論是誰，我都接受挑戰"},
    {"card_no": "HV-P02-003", "verdict": "excluded", "reason": "只讀對手狀態", "note": "月島螢"},
    {"card_no": "HV-P02-004", "verdict": "excluded", "reason": "不划算", "note": "山口忠"},
    {"card_no": "HV-P02-006", "verdict": "excluded", "reason": "只讀對手狀態", "note": "西谷夕"},
    {"card_no": "HV-P02-007", "verdict": "excluded", "reason": "純數值削弱", "note": "田中龍之介"},
    {"card_no": "HV-P02-016", "verdict": "excluded", "reason": "綁人名", "note": "宮侑"},
    {"card_no": "HV-P02-020", "verdict": "excluded", "reason": "綁人名", "note": "宮治"},
    {"card_no": "HV-P02-027", "verdict": "special", "tier": "學校", "kind": "封鎖", "note": "角名倫太郎"},
    {"card_no": "HV-P02-029", "verdict": "special", "tier": "學校", "kind": "無效", "note": "尾白阿蘭"},
    {"card_no": "HV-P02-031", "verdict": "special", "tier": "通用", "kind": "封鎖", "note": "理石平介"},
    {"card_no": "HV-P02-038", "verdict": "excluded", "reason": "純數值削弱", "note": "二口堅治"},
    {"card_no": "HV-P02-039", "verdict": "special", "tier": "學校", "kind": "封鎖", "note": "二口堅治"},
    {"card_no": "HV-P02-042", "verdict": "excluded", "reason": "只讀對手狀態", "note": "鎌先靖志"},
    {"card_no": "HV-P02-046", "verdict": "special", "tier": "學校", "kind": "破壞", "note": "牛島若利"},
    {"card_no": "HV-P02-049", "verdict": "excluded", "reason": "只讀對手狀態", "note": "天童覺"},
    {"card_no": "HV-P02-057", "verdict": "excluded", "reason": "只讀對手狀態", "note": "岩泉一"},
    {"card_no": "HV-P02-061", "verdict": "excluded", "reason": "只讀對手狀態", "note": "黑尾鐵朗"},
    {"card_no": "HV-P02-074", "verdict": "excluded", "reason": "純數值削弱", "note": "沼井和馬"},
    {"card_no": "HV-P02-079", "verdict": "excluded", "reason": "不划算", "note": "谷地仁花"},
    {"card_no": "HV-P02-080", "verdict": "excluded", "reason": "不划算", "note": "武田一鐵"},
    {"card_no": "HV-P02-082", "verdict": "excluded", "reason": "綁人名", "note": "超銳角斜線扣球！！！"},
    {"card_no": "HV-P02-086", "verdict": "excluded", "reason": "純數值削弱", "note": "稻荷崎應援團"},
    {"card_no": "HV-P02-088", "verdict": "excluded", "reason": "綁人名", "note": "雙子速攻　負節奏「裏」！！！"},
    {"card_no": "HV-P02-091", "verdict": "excluded", "reason": "只讀對手狀態", "note": "最強的防守，也是最快的攻擊——那就是「攔網」"},
    {"card_no": "HV-P02-093", "verdict": "excluded", "reason": "純數值削弱", "note": "集中站位讀切式攔網"},
    {"card_no": "HV-P02-097", "verdict": "excluded", "reason": "綁人名", "note": "可惡，太強了啊！！！"},
    {"card_no": "HV-P03-003", "verdict": "special", "tier": "學校", "kind": "削弱", "note": "月島螢"},
    {"card_no": "HV-P03-005", "verdict": "excluded", "reason": "純數值削弱", "note": "金田一勇太郎"},
    {"card_no": "HV-P03-006", "verdict": "excluded", "reason": "只讀對手狀態", "note": "金田一勇太郎"},
    {"card_no": "HV-P03-009", "verdict": "special", "tier": "通用", "kind": "無效", "note": "黃金川貫至"},
    {"card_no": "HV-P03-020", "verdict": "excluded", "reason": "自保或雙方對等", "note": "影山飛雄"},
    {"card_no": "HV-P03-030", "verdict": "excluded", "reason": "只讀對手狀態", "note": "千鹿谷栄吉"},
    {"card_no": "HV-P03-036", "verdict": "excluded", "reason": "只讀對手狀態", "note": "灰羽利耶夫"},
    {"card_no": "HV-P03-038", "verdict": "excluded", "reason": "只讀對手狀態", "note": "犬岡走"},
    {"card_no": "HV-P03-046", "verdict": "excluded", "reason": "只讀對手狀態", "note": "赤木路成"},
    {"card_no": "HV-P03-051", "verdict": "excluded", "reason": "純數值削弱", "note": "西谷夕"},
    {"card_no": "HV-P03-053", "verdict": "excluded", "reason": "綁人名", "note": "東峰旭"},
    {"card_no": "HV-P03-054", "verdict": "special", "tier": "通用", "kind": "封鎖", "note": "嶋田誠"},
    {"card_no": "HV-P03-063", "verdict": "special", "tier": "學校", "kind": "無效", "note": "青根高伸"},
    {"card_no": "HV-P03-067", "verdict": "excluded", "reason": "純數值削弱", "note": "牛島若利"},
    {"card_no": "HV-P03-072", "verdict": "excluded", "reason": "純數值削弱", "note": "瀨見英太"},
    {"card_no": "HV-P03-073", "verdict": "special", "tier": "通用", "kind": "無效", "note": "小鹿野大樹"},
    {"card_no": "HV-P03-092", "verdict": "special", "tier": "通用", "kind": "無效", "note": "你很會攔網喔"},
    {"card_no": "HV-P03-098", "verdict": "excluded", "reason": "純數值削弱", "note": "打垮你！！！"},
    {"card_no": "HV-P03-099", "verdict": "excluded", "reason": "綁人名", "note": "……所以，你現在在做什麼？"},
    {"card_no": "HV-P04-001", "verdict": "excluded", "reason": "綁人名", "note": "日向翔陽"},
    {"card_no": "HV-P04-004", "verdict": "excluded", "reason": "純數值削弱", "note": "山口忠"},
    {"card_no": "HV-P04-006", "verdict": "excluded", "reason": "只讀對手狀態", "note": "田中龍之介"},
    {"card_no": "HV-P04-013", "verdict": "special", "tier": "學校", "kind": "無效", "note": "東峰旭"},
    {"card_no": "HV-P04-018", "verdict": "special", "tier": "通用", "kind": "破壞", "note": "及川徹"},
    {"card_no": "HV-P04-020", "verdict": "special", "tier": "通用", "kind": "封鎖", "note": "岩泉一"},
    {"card_no": "HV-P04-031", "verdict": "excluded", "reason": "只讀對手狀態", "note": "溫田兼生"},
    {"card_no": "HV-P04-041", "verdict": "excluded", "reason": "只讀對手狀態", "note": "母畑和馬"},
    {"card_no": "HV-P04-048", "verdict": "excluded", "reason": "不划算", "note": "川渡瞬己"},
    {"card_no": "HV-P04-051", "verdict": "excluded", "reason": "只讀對手狀態", "note": "鳴子哲平"},
    {"card_no": "HV-P04-054", "verdict": "excluded", "reason": "只讀對手狀態", "note": "夜久衛輔"},
    {"card_no": "HV-P04-068", "verdict": "excluded", "reason": "純數值削弱", "note": "宮侑"},
    {"card_no": "HV-P04-073", "verdict": "excluded", "reason": "不划算", "note": "黃金川貫至"},
    {"card_no": "HV-P04-078", "verdict": "excluded", "reason": "綁人名", "note": "嶋田誠"},
    {"card_no": "HV-P04-082", "verdict": "excluded", "reason": "綁人名", "note": "……這樣才站上起跑線……！！"},
    {"card_no": "HV-P04-087", "verdict": "excluded", "reason": "綁人名", "note": "啊，來了 發球拋球 感覺不錯"},
    {"card_no": "HV-P04-088", "verdict": "excluded", "reason": "純數值削弱", "note": "分毫不差！！！"},
    {"card_no": "HV-P04-090", "verdict": "excluded", "reason": "純數值削弱", "note": "——從上面……！"},
    {"card_no": "HV-P04-097", "verdict": "excluded", "reason": "純數值削弱", "note": "致曾經的「小巨人」"},
    {"card_no": "HV-P04-100", "verdict": "excluded", "reason": "自保或雙方對等", "note": "要贏啊……！連我們的份一起！！！"},
    {"card_no": "HV-PR-022", "verdict": "excluded", "reason": "只讀對手狀態", "note": "澤村大地"},
    {"card_no": "HV-PR-024", "verdict": "special", "tier": "通用", "kind": "破壞", "note": "及川徹"},
    {"card_no": "HV-PR-025", "verdict": "excluded", "reason": "綁人名", "note": "京谷賢太郎"},
    {"card_no": "HV-PR-027", "verdict": "excluded", "reason": "不划算", "note": "二口堅治"},
    {"card_no": "HV-PR-028", "verdict": "special", "tier": "通用", "kind": "破壞", "note": "白布賢二郎"},
    {"card_no": "HV-PR-031", "verdict": "excluded", "reason": "純數值削弱", "note": "所有人都在看著你喔"},
    {"card_no": "HV-PR-046", "verdict": "excluded", "reason": "只讀對手狀態", "note": "天童覺"},
    {"card_no": "HV-PR-049", "verdict": "excluded", "reason": "只讀對手狀態", "note": "尾白阿蘭"},
    {"card_no": "HV-PR-051", "verdict": "excluded", "reason": "自保或雙方對等", "note": "照平常來就好，讓我去決勝負"},
    {"card_no": "HV-PR-052", "verdict": "excluded", "reason": "只讀對手狀態", "note": "想打倒若利君，就先過我這關～之類的啦～"},
    {"card_no": "HV-PR-063", "verdict": "excluded", "reason": "自保或雙方對等", "note": "Jump慶典最棒了！！"},
    {"card_no": "HVBP-013", "verdict": "excluded", "reason": "綁人名", "note": "完全命中！！"},
]
