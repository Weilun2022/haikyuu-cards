"""人工結構化的卡片（依日文原文 skill_jp）。欄位定義見 schema.md。
效果可帶 `if`：該效果只在條件成立時執行（同一技能內的追加效果）。"""

TO = 'next_opp_turn'

MANUAL = {
    # ── 角色 ────────────────────────────────────────────
    'HV-P02-001': [dict(  # 日向翔陽
        timing='on_enter', zones=['receive'],
        conditions=[dict(type='set_total_le', n=1)],
        cost=[dict(type='guts', n=3)],
        effects=[dict(type='stat_add', target='this', stat='rcv', n=6),
                 dict(type='drop_to_hand', who='self', filter=dict(school='烏野', category='CHARACTER'), max=1)])],

    'HV-P01-013': [dict(  # 縁下力
        timing='from_hand', phases=['receive'],
        cost=[dict(type='discard_this_from_hand')],
        effects=[dict(type='stat_add', target=dict(who='self', count=1, school='烏野'), stat='rcv', n=2)])],

    'HV-D01-005': [dict(  # 西谷夕
        timing='on_enter', zones=['receive'],
        cost=[dict(type='guts', n=3)],
        effects=[dict(type='draw', who='self', n=1),
                 dict(type='stat_add', target='this', stat='rcv', n=2)])],

    'HV-P03-046': [  # 赤木路成：只看對手「發球」
        dict(timing='on_enter', zones=['receive'],
             conditions=[dict(type='opp_op_le', n=2, of='serve')],
             effects=[dict(type='draw', who='self', n=1)]),
        dict(timing='on_enter', zones=['receive'],
             conditions=[dict(type='opp_op_ge', n=6, of='serve')],
             effects=[dict(type='stat_add', target='this', stat='rcv', n=2)])],

    'HV-PR-022': [  # 澤村大地：條件成立時兩項都可用
        dict(timing='on_enter', zones=['receive'],
             conditions=[dict(type='opp_op_le', n=2, of='serve_or_attack')],
             effects=[dict(type='keyword', name='Aパス', n=1)]),
        dict(timing='on_enter', zones=['receive'],
             conditions=[dict(type='opp_op_le', n=2, of='serve_or_attack')],
             cost=[dict(type='guts', n=1)],
             effects=[dict(type='draw', who='self', n=1)])],

    'HV-P01-006': [dict(  # 影山飛雄
        timing='on_enter', zones=['toss'],
        cost=[dict(type='guts', n=2)],
        effects=[dict(type='reveal_top_take', who='self', n=1, names=['日向 翔陽', 'オープン攻撃'], max=1, rest='deck_bottom'),
                 dict(type='aura_on_enter', who='self', name='日向 翔陽', stat='atk', n=2, duration='this_turn',
                      note='QA：每次出場到攻擊區時 +2；先出場的日向變成 Guts 後失去 +2')])],

    'HV-P02-060': [dict(  # 孤爪研磨
        timing='trigger', zones=['toss'],
        trigger=dict(event='enter', who='self', from_='hand', role='attack', base_atk=3),
        conditions=[dict(type='self_is_role', role='toss')],
        cost=[dict(type='mill', who='self', n=1)],
        effects=[dict(type='stat_add', target='this', stat='tos', n=1),
                 dict(type='guts_to_zone', who='self', zone='attack', max=1, exact=True)])],

    'HV-P03-047': [dict(  # 影山飛雄
        timing='trigger', zones=['toss'],
        trigger=dict(event='play_event', who='self', from_='hand', during='self_attack_phase'),
        conditions=[dict(type='self_is_role', role='toss')],
        effects=[dict(type='stat_add', target='this', stat='tos', n=1),
                 dict(type='stat_cap', target='this', stat='tos', below=4, source='skill', duration='this_turn')])],

    'HV-P01-002': [dict(  # 日向翔陽
        timing='on_enter', zones=['attack'],
        cost=[dict(type='guts', n=3)],
        effects=[dict(type='stat_add', target='this', stat='atk', n=4),
                 dict(type='restrict_opp', who='opp', rule='cannot_enter', role='receive', base_rcv_ge=6, duration=TO)])],

    'HV-P02-057': [dict(  # 岩泉一
        timing='on_enter', zones=['receive'],
        conditions=[dict(type='opp_hand_le', n=3)],
        cost=[dict(type='guts', n=3)],
        effects=[dict(type='stat_add', target='this', stat='rcv', n=7)])],

    'HV-PR-027': [dict(  # 二口堅治
        timing='on_enter', zones=['serve', 'block', 'attack'],
        effects=[dict(type='on_opp_non_draw_add_mill', who='opp', n=3, duration=TO)])],

    'HVBP-001': [dict(  # 日向翔陽
        timing='on_enter', zones=['attack'],
        cost=[dict(type='discard_hand', n=1)],
        effects=[dict(type='stat_add', target='this', stat='atk', n=2)])],

    # ── 事件 ────────────────────────────────────────────
    'HV-D01-012': [dict(  # 背後時間差攻擊（ブロード攻撃）
        timing='event', phases=['attack'],
        effects=[dict(type='draw', who='self', n=1),
                 dict(type='stat_add', target=dict(who='self', count=1, school='烏野'), stat='atk', n=1),
                 dict(type='restrict_opp', who='opp', rule='max_enter', role='block', max=1, duration=TO,
                      **{'if': [dict(type='self_role_name', role='toss', name='影山 飛雄'),
                                dict(type='self_role_name', role='attack', name='日向 翔陽')]})])],

    'HV-P01-074': [dict(  # 烏養一繋
        timing='event', phases=['attack'],
        effects=[dict(type='draw', who='self', n=1),
                 dict(type='stat_add', target=dict(who='self', count=1), stat='atk', n=1),
                 dict(type='stat_add', target='same', stat='atk', n=2,
                      **{'if': [dict(type='event_zone_phase_count_ge', who='opp', phases=['draw', 'receive'], n=5)]})])],

    'HV-P01-078': [dict(  # 高球進攻（オープン攻撃）
        timing='event', phases=['attack'],
        effects=[dict(type='draw', who='self', n=2),
                 dict(type='discard_hand', who='self', n=1, note='效果不是代價；QA：手上有牌就必須棄置'),
                 dict(type='drop_to_zone', who='self', name='日向 翔陽', zone='attack', max=1, mandatory=True,
                      then=dict(type='stat_add', target='that', stat='atk', n=1),
                      note='QA：棄牌區有日向就必須出場；舉球角色是日向時不能出場（人名規則）',
                      **{'if': [dict(type='event_zone_count_le', who='self', card_name='オープン攻撃', n=2, includes_self=True)]})])],

    'HV-P02-083': [dict(  # 我要找人幫忙！！！
        timing='event', phases=['receive'],
        effects=[dict(type='draw', who='self', n=1),
                 dict(type='guts_to_zone', who='self', zone='receive', filter=dict(position='Li'), max=1)])],

    'HV-P03-086': [  # 你的打法倒是挺乖的嘛
        dict(timing='event', phases=['toss'],
             effects=[dict(type='stat_set', target=dict(who='self', count=1, role='toss', position='S'), stat='tos', value=2)]),
        dict(timing='event', phases=['toss'], part_of_same_card=True,
             cost=[dict(type='this_to_deck_bottom')],
             effects=[dict(type='event_to_hand', who='self', filter=dict(only_phase='attack'), max=1)])],
}

# ── 梟谷（2026-10-09 結構化，待使用者驗收）──────────────────
MANUAL_FUKURODANI = {
    'HV-P01-051': [dict(  # 鷲尾辰生
        timing='on_enter', zones=['block'],
        conditions=[dict(type='opp_op_ge', n=4, of='any',
                         note='QA（PR-022/PR-023）：進攻值有發球、攔網、攻擊三種；原文未限定，三種都適用')],
        cost=[dict(type='mill', who='self', n=1, capture='milled')],
        effects=[dict(type='keyword', name='ワンタッチ', n=3,
                      **{'if': [dict(type='captured_school', key='milled', school='梟谷')]},
                      note='9-3：對手進攻 −3，跳過剩下的攔網階段，進入自己的抽牌→接球；QA：之後接球可再出另一張鷲尾')])],

    'HV-PR-047': [dict(  # 小見春樹
        timing='on_enter', zones=['receive'],
        cost=[dict(type='discard_hand', n=1)],
        effects=[dict(type='stat_add', target='this', stat='rcv', n=2)])],

    'HV-P01-045': [dict(  # 赤葦京治
        timing='on_enter', zones=['toss'],
        cost=[dict(type='guts_multi', zones=['toss', 'attack'], n=4,
                   note='QA：從舉球區與攻擊區任意組合，合計 4')],
        effects=[dict(type='stat_add', target='this', stat='tos', n=2),
                 dict(type='drop_to_hand', who='self', filter=dict(name='木兎 光太郎'), max=1,
                      note='QA：剛支付的 Guts 裡的木兎也可以拿')])],

    'HV-P02-067': [dict(  # 赤葦京治
        timing='on_enter', zones=['toss'],
        effects=[dict(type='mill', who='self', n=1, up_to=True, capture='milled'),
                 dict(type='optional', cost=[dict(type='discard_hand', n=1)],
                      effects=[dict(type='keyword', name='ツーアタック', n=3,
                                    note='9-8：進攻值固定 3，跳到結束階段（不出攻擊角色），對手下回合不能出攔網')],
                      **{'if': [dict(type='captured_school', key='milled', school='梟谷', category='CHARACTER')]})])],

    'HV-P03-061': [dict(  # 木兎光太郎
        timing='on_enter', zones=['serve', 'attack'],
        cost=[dict(type='discard_named', name='木兎 光太郎', n=1,
                   note='QA：雙名卡「木兎・赤葦」不能拿來棄')],
        effects=[dict(type='draw', who='self', n=1),
                 dict(type='stat_add', target='this', stat='any', n=3,
                      note='任一數值；在發球區加發球、在攻擊區加攻擊')])],

    'HV-P01-043': [dict(  # 木兎光太郎
        timing='on_enter', zones=['attack'],
        conditions=[dict(type='entered_from_hand'),
                    dict(type='all_own_chars_school', school='梟谷'),
                    dict(type='zone_guts_odd', zone='attack',
                         note='QA：在這張出場、使用技能的時候判斷')],
        effects=[dict(type='stat_add', target='this', stat='atk', n=5)])],

    'HV-P01-091': [  # 這可不是音駒的專利啊！
        dict(timing='event', phases=['receive'],
             effects=[dict(type='draw', who='self', n=1),
                      dict(type='stat_add', target=dict(who='self', count=1, school='梟谷'), stat='rcv', n=1)]),
        dict(timing='event', phases=['receive'], part_of_same_card=True,
             cost=[dict(type='drop_block_char', who='self', school='梟谷', n=1)],
             effects=[dict(type='opp_op_add', n=-1, note='QA：可以降到負數')])],

    'HV-PR-031': [dict(  # 所有人都在看著你喔
        timing='event', phases=['attack'],
        effects=[dict(type='draw', who='self', n=1),
                 dict(type='stat_add', target=dict(who='self', count=1, school='梟谷'), stat='atk', n=1),
                 dict(type='restrict_opp', who='opp', rule='center_blocker_blk_add', n=-2, duration=TO,
                      note='QA：可以降到負數',
                      **{'if': [dict(type='self_role_name', role='toss', name='赤葦 京治'),
                                dict(type='self_role_name', role='attack', name='木兎 光太郎')]})])],
}
MANUAL.update(MANUAL_FUKURODANI)

# ── 暫定（未經使用者驗收，只用於比較測試）──────────────────
MANUAL_PROVISIONAL = {
    'HV-P02-064': [dict(  # 木兎光太郎：登場到任一區時，可以從手牌棄 2 張；沒棄的話所有數值變 0
        timing='on_enter', zones=['serve', 'block', 'receive', 'toss', 'attack'],
        effects=[dict(type='optional_discard_else_zero', n=2,
                      note='策略：手牌夠 2 張就一定棄（模擬器假設）')])],
}
MANUAL.update(MANUAL_PROVISIONAL)

# ── 梟谷第二批（2026-10-11 草稿，待使用者驗收反向翻譯）─────────
# 規則確認（使用者 2026-10-11）：PR-062 音駒・梟谷算梟谷角色；P01-090 抽到 7 張後局間只補不棄；
# P01-090「全部是梟谷」在打出當下判斷。
# 未驗收前預設不啟用；設環境變數 DH_PENDING=1 才會載入（只能用來測程式，不能下結論）。
NAME_CHOICE_PENDING = {
    'HV-PR-013': ['木兎 光太郎', '赤葦 京治'],    # 木兎・赤葦：出場時選名字，到回合結束有效；其他時候叫「木兎・赤葦」
    'HV-PR-062': ['灰羽 リエーフ', '木兎 光太郎'],  # 灰羽・木兎
}
MANUAL_PENDING = {
    'HV-PR-026': [dict(  # 猿杙大和：接球區登場，付 4 Guts，接球 +4
        timing='on_enter', zones=['receive'],
        cost=[dict(type='guts', n=4)],
        effects=[dict(type='stat_add', target='this', stat='rcv', n=4)])],

    'HV-P01-047': [dict(  # 木葉秋紀：此攻擊角色上有梟谷角色登場時，棄手牌 1 張，那個角色攻擊 +1
        timing='trigger', trigger=dict(event='enter_on_top', zone='attack', school='梟谷'),
        cost=[dict(type='discard_hand', n=1)],
        effects=[dict(type='stat_add', target='that', stat='atk', n=1)])],

    'HV-P02-066': [dict(  # 赤葦京治：舉球區登場，棄自己牌庫頂 3 張＋付 2 Guts，舉球 +2，本回合自己的木兎技能無效
        timing='on_enter', zones=['toss'],
        cost=[dict(type='mill', who='self', n=3, note='QA 1335：棄不滿 3 張就沒有效果'),
              dict(type='guts', n=2)],
        effects=[dict(type='stat_add', target='this', stat='tos', n=2),
                 dict(type='negate_skills', name='木兎 光太郎', duration='this_turn')])],

    'HV-P01-089': [dict(  # 闇路建行：看牌庫頂 3 張，梟谷牌最多 1 張加入手牌，其餘放牌庫底
        timing='event', phases=['draw', 'receive'],
        effects=[dict(type='look_top_take', n=3, school='梟谷', max=1, rest='deck_bottom',
                      note='QA 1240：可以不拿；不是抽牌（二口陷阱會觸發）')])],

    'HV-P01-090': [dict(  # 「その瞬間」：抽 1、梟谷角色攻擊 +1；全員梟谷時，對手下回合 LOSS 時自己抽到 7 張
        timing='event', phases=['attack'],
        effects=[dict(type='draw', who='self', n=1),
                 dict(type='stat_add', target=dict(who='self', count=1, school='梟谷'), stat='atk', n=1),
                 dict(type='restrict_opp', who='opp', rule='owner_draw_to_on_loss', n=7, duration='next_opp_turn',
                      note='QA 1241：對手主動宣告 LOSS 也算',
                      **{'if': [dict(type='all_own_chars_school', school='梟谷')]})])],
}
import os as _os
NAME_CHOICE = {}
if _os.environ.get('DH_PENDING') == '1':
    MANUAL.update(MANUAL_PENDING)
    NAME_CHOICE.update(NAME_CHOICE_PENDING)

# ── 白鳥沢（2026-10-11 草稿，待使用者驗收反向翻譯）──────────────
# 未驗收前預設不啟用；設環境變數 DH_SHIRA=1 才會載入（只能用來測程式，不能下結論）。
MANUAL_SHIRATORIZAWA = {
    'HV-P02-049': [dict(  # 天童覚：攔網區登場，對手進攻值 ≥4 時，一觸(2)
        timing='on_enter', zones=['block'],
        conditions=[dict(type='opp_op_ge', n=4, of='any', note='原文未限定，發球、攔網、攻擊三種進攻值都適用（同鷲尾 QA）')],
        effects=[dict(type='keyword', name='ワンタッチ', n=2,
                      note='QA 1320：之後接球可再出另一張天童')])],

    'HV-P03-071': [dict(  # 山形隼人：接球區登場，雙方 Set 合計 ≤1，付 3 Guts：接球 +2，撈回山形以外的白鳥沢 3 年角色 1 張
        timing='on_enter', zones=['receive'],
        conditions=[dict(type='set_total_le', n=1)],
        cost=[dict(type='guts', n=3)],
        effects=[dict(type='stat_add', target='this', stat='rcv', n=2),
                 dict(type='drop_to_hand', who='self', max=1,
                      filter=dict(affiliation='白鳥沢·3年', exclude_name='山形 隼人', category='CHARACTER'),
                      note='QA 1816：剛支付的 Guts 也可以拿；QA 1817：所屬字串要完全一致')])],

    'HV-P02-050': [dict(  # 白布賢二郎：舉球區登場，自己角色全部白鳥沢，付 2 Guts：舉球 +2；付的 Guts 全是 S 時，白鳥沢 Guts 1 張移到攻擊區當 Guts
        timing='on_enter', zones=['toss'],
        conditions=[dict(type='all_own_chars_school', school='白鳥沢', note='QA 1321：看場上各區最上面的角色')],
        cost=[dict(type='guts', n=2)],
        effects=[dict(type='stat_add', target='this', stat='tos', n=2),
                 dict(type='guts_move_to_zone', who='self', school='白鳥沢', to='attack', max=1,
                      note='QA 1322：可從自己場上任一區的 Guts 拿',
                      **{'if': [dict(type='paid_guts_all_pos', position='S')]})])],

    'HV-P03-072': [dict(  # 瀬見英太：發球區登場，疊在白鳥沢角色上時：發球 +3，對手下回合 Li 接球角色每次出場接球 −1
        timing='on_enter', zones=['serve'],
        conditions=[dict(type='enter_on_top_school', school='白鳥沢')],
        effects=[dict(type='stat_add', target='this', stat='srv', n=3),
                 dict(type='restrict_opp', who='opp', rule='li_receive_add', n=-1, duration=TO)])],

    'HV-P02-046': [dict(  # 牛島若利：攻擊區登場，舉球角色是白鳥沢的 S，付 3 Guts：攻擊 +3，棄對手接球區 Guts 最多 2 張
        timing='on_enter', zones=['attack'],
        conditions=[dict(type='self_role_school_pos', role='toss', school='白鳥沢', position='S')],
        cost=[dict(type='guts', n=3)],
        effects=[dict(type='stat_add', target='this', stat='atk', n=3),
                 dict(type='drop_opp_zone_guts', who='opp', zone='receive', max=2, note='QA 1317：由使用技能的一方選')])],

    'HV-P02-094': [  # 鷲匠鍛治：接球階段，抽 1、白鳥沢角色接球 +1；可棄手牌中無技能的白鳥沢角色 1 張，再 +2
        dict(timing='event', phases=['receive'],
             effects=[dict(type='draw', who='self', n=1),
                      dict(type='stat_add', target=dict(who='self', count=1, school='白鳥沢'), stat='rcv', n=1),
                      dict(type='optional', cost=[dict(type='discard_filtered', n=1,
                                                       filter=dict(school='白鳥沢', category='CHARACTER', no_skill=True))],
                           effects=[dict(type='stat_add', target='same', stat='rcv', n=2)])])],

    'HV-P02-096': [  # 道を空けろ：攻擊階段、每回合 1 次，抽 1、白鳥沢角色攻擊 +1；舉球是白布且攻擊角色原本攻擊 3 時，攻擊區 Guts 的牛島 1 張登場到攻擊區並攻擊 +1
        dict(timing='event', phases=['attack'], once_per_turn=True,
             effects=[dict(type='draw', who='self', n=1),
                      dict(type='stat_add', target=dict(who='self', count=1, school='白鳥沢'), stat='atk', n=1),
                      dict(type='guts_to_zone', who='self', zone='attack', filter=dict(name='牛島 若利'), max=1,
                           then=dict(type='stat_add', target='that', stat='atk', n=1),
                           note='QA 1381：進攻值看最後的攻擊角色；QA 1382：看「原本」攻擊值',
                           **{'if': [dict(type='self_role_name', role='toss', name='白布 賢二郎'),
                                     dict(type='self_role_base', role='attack', stat='atk', n=3)]})])],

    'HV-P02-097': [  # クソかっけえええ：攻擊階段，抽 1、白鳥沢角色攻擊 +1；攻擊角色是牛島時，對手下回合不能從手牌出 MB 攔網角色
        dict(timing='event', phases=['attack'],
             effects=[dict(type='draw', who='self', n=1),
                      dict(type='stat_add', target=dict(who='self', count=1, school='白鳥沢'), stat='atk', n=1),
                      dict(type='restrict_opp', who='opp', rule='cannot_enter_pos_from_hand', role='block', position='MB',
                           duration=TO, note='QA 1383：雙名卡含 MB 也不行；QA 1384：用技能從別區移過來可以',
                           **{'if': [dict(type='self_role_name', role='attack', name='牛島 若利')]})])],

    'HV-P03-090': [  # おれにバレーボール教えてくれて ありがとう（音駒）：抽牌階段、每回合 1 次，從 Event 區拿這張以外的事件 1 張回手牌
        dict(timing='event', phases=['draw'], once_per_turn=True,
             effects=[dict(type='event_to_hand', who='self', max=1,
                           filter=dict(exclude_name='おれにバレーボール教えてくれて ありがとう'))])],

    'HV-P03-099': [  # それでお前は何をやっている：攻擊階段，抽 1、白鳥沢攻擊角色攻擊 +1；是牛島時，棄對手 Event 區所有角色牌，棄 2 張以上再 +1
        dict(timing='event', phases=['attack'],
             effects=[dict(type='draw', who='self', n=1),
                      dict(type='stat_add', target=dict(who='self', count=1, school='白鳥沢', role='attack'), stat='atk', n=1),
                      dict(type='drop_opp_event_chars', who='opp', bonus_if_ge=2,
                           then=dict(type='stat_add', target='same', stat='atk', n=1),
                           **{'if': [dict(type='self_role_name', role='attack', name='牛島 若利')]})])],

    'HV-P03-067': [  # 牛島若利：接球區登場，付 2 Guts 接球 +4；對手攻擊角色原本攻擊 ≤1 時，可棄自己的白鳥沢攔網角色 1 人，對手攻擊進攻值 −2
        dict(timing='on_enter', zones=['receive'],
             cost=[dict(type='guts', n=2)],
             effects=[dict(type='stat_add', target='this', stat='rcv', n=4)]),
        dict(timing='on_enter', zones=['receive'],
             conditions=[dict(type='opp_role_base_le', role='attack', stat='atk', n=1,
                              note='只看對手「攻擊」的進攻值；與付 Guts 的部分各自獨立（各有「使える」）')],
             cost=[dict(type='drop_block_char', who='self', school='白鳥沢', n=1)],
             effects=[dict(type='opp_op_add', n=-2, note='策略：只有接不住時才棄攔網角色')])],
}
if _os.environ.get('DH_SHIRA') == '1':
    MANUAL.update(MANUAL_SHIRATORIZAWA)

# ── 稲荷崎（2026-10-12 使用者驗收通過）──────────────
NAME_CHOICE_INARIZAKI = {
    'HV-P02-077': ['宮 侑', '宮 治'],  # 宮兄弟：出場時選名字，到回合結束有效（QA 1344/1346：可當侑和另一張治一起攔網）
}
MANUAL_INARIZAKI = {
    'HV-D03-011': [dict(  # 赤木路成（Li）：接球區登場，付 2 Guts，接球 +2
        timing='on_enter', zones=['receive'],
        cost=[dict(type='guts', n=2)],
        effects=[dict(type='stat_add', target='this', stat='rcv', n=2)])],

    'HV-P02-024': [dict(  # 北信介：接球區登場，棄手牌 1 張＋付 3 Guts，接球 +1，Event 區的稲荷崎牌 1 張回手牌
        timing='on_enter', zones=['receive'],
        cost=[dict(type='discard_hand', n=1), dict(type='guts', n=3)],
        effects=[dict(type='stat_add', target='this', stat='rcv', n=1),
                 dict(type='event_to_hand', who='self', max=1, filter=dict(school='稲荷崎'),
                      note='QA 1285：不必是最上面那張')])],

    'HV-P02-016': [dict(  # 宮侑：舉球區登場，付 3 Guts，抽 1、舉球 +2；若是由「どん ぴしゃり」登場，對手下回合一觸與「接球階段・手牌」技能無效
        timing='on_enter', zones=['toss'],
        cost=[dict(type='guts', n=3)],
        effects=[dict(type='draw', who='self', n=1),
                 dict(type='stat_add', target='this', stat='tos', n=2),
                 dict(type='restrict_opp', who='opp', rule='nullify_onetouch_and_receive_hand', duration=TO,
                      note='QA 1273：一觸(2)(3) 都無效；QA 1274：例如成田 P02-011',
                      **{'if': [dict(type='entered_by', card_name='どん ぴしゃり')]})])],

    'HV-P03-021': [dict(  # 宮侑（Li）：舉球區登場，付 3 Guts，舉球 +2，棄牌區的「ユース」事件最多 1 張回手牌；有拿就從手牌棄 1
        timing='on_enter', zones=['toss'],
        cost=[dict(type='guts', n=3)],
        effects=[dict(type='stat_add', target='this', stat='tos', n=2),
                 dict(type='drop_to_hand', who='self', max=1, filter=dict(affiliation='ユース', category='EVENT'),
                      then=dict(type='discard_hand', who='self', n=1),
                      note='QA 1781：所屬字串要完全一致；本牌組沒有ユース事件，這段不會發生')])],

    'HV-D03-002': [dict(  # 宮治：攻擊區登場，舉球角色是宮侑時，手牌 1 張放牌庫底，攻擊 +2
        timing='on_enter', zones=['attack'],
        conditions=[dict(type='self_role_name', role='toss', name='宮 侑', note='QA 1251：宮兄弟選「宮 侑」也算')],
        cost=[dict(type='hand_to_deck_bottom', n=1, note='QA 1252：牌庫 0 張也能用')],
        effects=[dict(type='stat_add', target='this', stat='atk', n=2)])],

    'HV-P02-020': [dict(  # 宮治：攻擊區登場，付 3 Guts，攻擊 +3；若是由「どん ぴしゃり」登場，再 +1，對手下回合從手牌最多只能出 2 名攔網角色
        timing='on_enter', zones=['attack'],
        cost=[dict(type='guts', n=3)],
        effects=[dict(type='stat_add', target='this', stat='atk', n=3),
                 dict(type='stat_add', target='this', stat='atk', n=1,
                      **{'if': [dict(type='entered_by', card_name='どん ぴしゃり')]}),
                 dict(type='restrict_opp', who='opp', rule='max_block_from_hand', role='block', max=2, duration=TO,
                      **{'if': [dict(type='entered_by', card_name='どん ぴしゃり')]})])],

    'HV-P02-084': [dict(  # 黒須法宗：接球階段，抽 1、稲荷崎角色接球 +1；Event 區可在發球／舉球／攻擊打出的稲荷崎牌合計 ≥2 張時再 +1
        timing='event', phases=['receive'],
        effects=[dict(type='draw', who='self', n=1),
                 dict(type='stat_add', target=dict(who='self', count=1, school='稲荷崎'), stat='rcv', n=1),
                 dict(type='stat_add', target='same', stat='rcv', n=1,
                      note='QA 1363：多個圖示的事件算 1 張',
                      **{'if': [dict(type='event_zone_phase_count_ge', who='self', phases=['serve', 'toss', 'attack'], n=2, school='稲荷崎')]})])],

    'HV-P02-087': [dict(  # どん ぴしゃり：攻擊階段，抽 1；舉球侑＋攻擊治時：任一區 Guts 的侑→舉球區、治→攻擊區，稲荷崎角色任一數值 +1
        timing='event', phases=['attack'],
        effects=[dict(type='draw', who='self', n=1),
                 dict(type='guts_any_to_zone', who='self', zone='toss', filter=dict(name='宮 侑'), max=1,
                      note='QA 1370：任一區的 Guts 都可以',
                      **{'if': [dict(type='self_role_name', role='toss', name='宮 侑'), dict(type='self_role_name', role='attack', name='宮 治')]}),
                 dict(type='guts_any_to_zone', who='self', zone='attack', filter=dict(name='宮 治'), max=1,
                      **{'if': [dict(type='self_role_name', role='toss', name='宮 侑'), dict(type='self_role_name', role='attack', name='宮 治')]}),
                 dict(type='stat_add', target=dict(who='self', count=1, school='稲荷崎'), stat='any', n=1,
                      note='QA 1368：這張全部解決完，才解決叫出來的侑／治的登場技能；QA 1371：加給被蓋掉的角色會失效',
                      **{'if': [dict(type='self_role_name', role='toss', name='宮 侑'), dict(type='self_role_name', role='attack', name='宮 治')]})])],
}
# 2026-10-12 使用者驗收通過 → 預設啟用（DH_INARI=0 可關閉）
if _os.environ.get('DH_INARI', '1') == '1':
    MANUAL.update(MANUAL_INARIZAKI)
    NAME_CHOICE.update(NAME_CHOICE_INARIZAKI)
