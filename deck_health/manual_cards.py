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
