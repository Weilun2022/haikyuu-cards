"""混校研究 結構化第 4 批：稲荷崎、伊達工業、白鳥沢（能用現有機制表達的）。預設關閉（DH_BATCH4=1 啟用），等使用者驗收。
也包含先前 DH_P04 草稿的 3 張稲荷崎第四彈卡（P04-068／070／099），一併請使用者驗收。"""
TO = 'next_opp_turn'
G = lambda n: [dict(type='guts', n=n)]
S = lambda stat, n, tg='this': dict(type='stat_add', target=tg, stat=stat, n=n)
ON = lambda zones, **kw: dict(timing='on_enter', zones=zones, **kw)
DRAW = dict(type='draw', who='self', n=1)
ONE = dict(who='self', count=1)
EVG = 'おっさん'  # 備忘
DATE = lambda n: dict(type='block_comb_school_ge', school='伊達工業', n=n)
OPP_TA = lambda n: dict(type='event_zone_phase_count_ge', who='opp', phases=['toss', 'attack'], n=n)

MANUAL_BATCH4 = {
    # ══ 稲荷崎 ══
    'HV-P01-065': [ON(['receive'], conditions=[OPP_TA(5)], effects=[S('rcv', 6)])],
    'HV-P02-021': [ON(['attack'], conditions=[dict(type='self_hand_le', n=2)], effects=[S('atk', 2)])],
    'HV-P02-025': [ON(['receive'], cost=G(2), effects=[DRAW, dict(type='discard_hand', n=1)])],
    'HV-P02-029': [ON(['attack'], cost=G(3), effects=[
        dict(type='stat_add', target='this', stat='atk', n=3, **{'if': [dict(type='drop_distinct_names_ge', school='稲荷崎', n=6)]}),
        dict(type='restrict_opp', who='opp', rule='nullify_receive_skills', duration=TO, **{'if': [dict(type='drop_distinct_names_ge', school='稲荷崎', n=6)]})])],
    'HV-P02-031': [ON(['serve'], cost=G(1), effects=[
        dict(type='stat_add', target='this', stat='srv', n=6, **{'if': [dict(type='paid_guts_name', name='理石 平介')]}),
        dict(type='restrict_opp', who='opp', rule='cannot_enter_pos_from_hand', role='toss', position='S', duration=TO,
             **{'if': [dict(type='paid_guts_name', name='理石 平介')]})])],
    # ※ 理石 P02-031：「Sのトスキャラを登場させられない」我只擋「從手牌登場」的 S（實戰舉球基本上都是從手牌出）
    'HV-P02-077': [], 'HV-PR-036': [], 'HV-PR-040': [], 'HV-PR-059': [], 'HV-PR-068': [],
    'HV-P02-085': [dict(timing='event', phases=['receive'], effects=[
        S('rcv', 1, dict(who='self', count=1, school='稲荷崎')),
        dict(type='optional', cost=[dict(type='discard_filtered', n=1, filter=dict(school='稲荷崎'))],
             effects=[dict(type='draw', who='self', n=2)])])],
    'HV-P02-086': [dict(timing='event', phases=['serve', 'draw'], draw_policy='always', conditions=[dict(type='all_own_chars_school', school='稲荷崎')], effects=[
        DRAW,
        dict(type='restrict_opp', who='opp', rule='opp_noskill_rcv_add', n=-1, duration=TO, **{'if': [dict(type='phase_is', phase='serve')]}),
        dict(type='restrict_opp', who='opp', rule='opp_noskill_rcv_add', n=-1, duration=TO,
             **{'if': [dict(type='phase_is', phase='serve'), dict(type='self_role_name', role='serve', name='宮 侑')]})])],
    'HV-P03-091': [dict(timing='event', phases=['serve', 'draw'], draw_policy='always', effects=[
        DRAW,
        dict(type='stat_set_zone', zone='serve', value=6, **{'if': [dict(type='phase_is', phase='serve'), dict(type='self_role_name', role='serve', name='宮 侑')]})])],
    # ※ P03-091：「這張從 Event 區被丟棄時抽 1」沒模擬
    'HV-P03-092': [dict(timing='event', phases=['attack'], effects=[
        DRAW,
        dict(type='restrict_opp', who='opp', rule='nullify_doshat', duration=TO),
        dict(type='restrict_opp', who='opp', rule='nullify_onetouch', duration=TO),
        dict(type='optional', cost=[dict(type='guts', n=2, zone='attack')], effects=[dict(type='stat_add', target='same', stat='atk', n=2)],
             **{'if': [dict(type='self_role_name', role='attack', name='角名 倫太郎')]})])],
    # ※ P03-092：抽 1 與「對手ドシャット／ワンタッチ無效」是無條件；角名時才可付 2 Guts 換 +2（付得起才付）
    'HV-P04-068': [ON(['serve'], conditions=[dict(type='all_own_chars_school', school='稲荷崎'), dict(type='enter_on_top_name', name='宮 侑')], effects=[
        DRAW, dict(type='restrict_opp', who='opp', rule='opp_s_toss_add', n=-1, duration=TO)])],
    'HV-P04-070': [ON(['receive'], conditions=[dict(type='event_zone_school_count_ge', who='self', school='稲荷崎', n=3)],
                      cost=[dict(type='discard_filtered', n=1, filter=dict(school='稲荷崎'))], use_if=[dict(type='receive_below_op')], effects=[S('rcv', 2)])],
    # ※ P04-070「本回合稲荷崎角色數值不會被減」模擬中沒有會減我方數值的對手效果，略過
    'HV-P04-099': [dict(timing='event', phases=['toss'], once_per_turn=True, conditions=[dict(type='self_role_name', role='toss', name='宮 侑')], effects=[
        DRAW, S('tos', 1, dict(who='self', count=1)),
        dict(type='look_top_take', who='self', n=3, names=['どん ぴしゃり'], max=1, rest='deck_bottom')])],
    'HV-D03-003': [ON(['serve'], cost=[dict(type='event_hand_to_evz', n=1)], effects=[DRAW, dict(type='restrict_opp', who='opp', rule='opp_toss_add', n=-2, duration=TO)])],
    # ※ 宮侑 D03-003：二選一（發球 +1 或 對手舉球角色登場舉球 −2），程式固定選「舉球 −2」；放進去的事件技能不能用（已照辦：放進 Event 區不發動）
    'HV-D03-008': [ON(['attack'], cost=G(5), effects=[S('atk', 2)])],
    'HV-D03-012': [dict(timing='event', phases=['receive'], effects=[
        DRAW, S('rcv', 1, dict(who='self', count=1, school='稲荷崎')),
        dict(type='optional', cost=[dict(type='guts', n=4, zone='receive')], effects=[DRAW])])],
    'HV-PR-048': [ON(['attack'], cost=G(2), effects=[
        dict(type='stat_add', target='this', stat='atk', n=3, **{'if': [dict(type='drop_distinct_names_ge', school='稲荷崎', n=6)]})])],
    'HV-PR-049': [ON(['receive'], cost=G(2), effects=[
        S('rcv', 3), dict(type='drop_to_hand', who='self', filter=dict(school='稲荷崎', category='CHARACTER'), max=1,
                          **{'if': [dict(type='opp_op_le', n=2, of='serve')]})])],

    # ══ 伊達工業 ══
    'HV-P01-054': [ON(['block'], cost=G(3), effects=[S('blk', 5)])],
    'HV-P02-036': [ON(['block'], conditions=[DATE(3)], cost=G(2), effects=[dict(type='keyword', name='ドシャット', n=7)])],
    'HV-P02-038': [ON(['block'], effects=[
        dict(type='keyword', name='ドシャット', n=4),
        dict(type='restrict_opp', who='opp', rule='opp_rcv_add', n=-1, duration=TO, **{'if': [dict(type='is_side_blocker')]})])],
    'HV-P02-039': [ON(['attack'], conditions=[dict(type='self_role_school_pos', role='toss', school='伊達工業', position='S')],
                      effects=[dict(type='restrict_opp', who='opp', rule='block_fail_le', n=6, duration=TO)])],
    'HV-P02-042': [ON(['block'], conditions=[OPP_TA(4)], effects=[S('blk', 5)])],
    'HV-P03-009': [ON(['toss'], cost=G(2), effects=[
        dict(type='stat_add', target='this', stat='tos', n=2, **{'if': [dict(type='evz_total_ge', n=4)]}),
        dict(type='restrict_opp', who='opp', rule='nullify_onetouch', duration=TO, **{'if': [dict(type='evz_total_ge', n=6)]})])],
    'HV-P03-063': [ON(['serve'], cost=[dict(type='mill', who='self', n=1, capture='milled')], effects=[
        dict(type='stat_add', target='this', stat='srv', n=3, **{'if': [dict(type='captured_school', key='milled', school='伊達工業', category='CHARACTER')]}),
        dict(type='restrict_opp', who='opp', rule='nullify_attack_event_skills', duration=TO,
             **{'if': [dict(type='captured_school', key='milled', school='伊達工業', category='CHARACTER')]})])],
    'HV-P03-064': [ON(['block'], cost=[dict(type='discard_filtered', n=2, filter=dict(school='伊達工業'))], auto_cost=True,
                      effects=[DRAW, S('blk', 4)])],
    'HV-PR-083': [ON(['block'], cost=[dict(type='event_hand_to_evz', n=1, filter=dict(school='伊達工業'))], auto_cost=True,
                     effects=[S('blk', 3), dict(type='keyword', name='ドシャット', n=6)])],
    'HV-PR-039': [], 'HV-PR-070': [],
    'HV-P04-073': [ON(['block'], conditions=[dict(type='evz_total_ge', n=4)], cost=G(1), effects=[S('blk', 2)])],
    # ※ 黄金川 P04-073：「對手 Guts 的国見英最多 3 張丟棄」沒模擬
    # 事件（攔網階段）
    'HV-P02-090': [dict(timing='event', phases=['block', 'receive'], effects=[
        DRAW,
        dict(type='stat_add', target=dict(who='self', count=1, school='伊達工業', base_eq=3), stat='blk', n=1, **{'if': [dict(type='phase_is', phase='block')]}),
        dict(type='stat_add', target=dict(who='self', count=1, school='伊達工業'), stat='rcv', n=1, **{'if': [dict(type='phase_is', phase='receive')]})])],
    'HV-P02-091': [dict(timing='event', phases=['block'], effects=[
        DRAW, S('blk', 1, dict(who='self', count=1, school='伊達工業')),
        dict(type='stat_add', target=dict(who='self', count=1, school='伊達工業'), stat='blk', n=6, **{'if': [OPP_TA(4)]}),
        dict(type='keyword', name='ドシャット', n=7, **{'if': [OPP_TA(4)]})])],
    'HV-P02-093': [dict(timing='event', phases=['block'], effects=[
        DRAW, S('blk', 1, dict(who='self', count=1, school='伊達工業')),
        dict(type='keyword', name='ドシャット', n=5, **{'if': [DATE(2)]}),
        dict(type='restrict_opp', who='opp', rule='opp_rcv_add', n=-1, duration=TO, **{'if': [DATE(3)]})])],
    'HV-P03-097': [dict(timing='event', phases=['block'], effects=[dict(type='drop_distinct_school_to_hand', school='伊達工業', n=2)])],
    'HV-P03-098': [dict(timing='event', phases=['serve', 'block'], conditions=[dict(type='all_own_chars_school', school='伊達工業')], effects=[
        DRAW,
        dict(type='stat_add', target=dict(who='self', count=1), stat='blk', n=1, **{'if': [dict(type='phase_is', phase='block')]}),
        dict(type='restrict_opp', who='opp', rule='opp_s_toss_add', n=-1, duration=TO, **{'if': [dict(type='phase_is', phase='serve')]})])],
    # ※ P03-098 二選一：攔網階段固定選「攔網 +1」、發球階段固定選「對手手牌出場的 S 舉球 −1」

    # ══ 白鳥沢 ══
    'HV-P02-048': [ON(['block'], effects=[dict(type='coin',
        heads=[S('blk', 4)], tails=[dict(type='mill_n', n=3)])])],
    'HV-P02-051': [ON(['attack'], conditions=[dict(type='entered_from_hand'), dict(type='enter_on_top_name', name='牛島 若利'), dict(type='self_hand_le', n=3)],
                      effects=[S('atk', 2)])],
    'HV-P02-052': [ON(['receive'], cost=G(3), effects=[S('rcv', 2)])],
    'HV-P02-095': [dict(timing='event', phases=['draw'], draw_policy='always', effects=[
        dict(type='drop_to_hand', who='self', filter=dict(school='白鳥沢', category='CHARACTER', no_skill=True), max=2),
        dict(type='discard_if_took_n', n=2)])],
    'HV-P02-098': [dict(timing='event', phases=['attack'], once_per_turn=True, effects=[
        DRAW, S('atk', 1, dict(who='self', count=1, school='白鳥沢')),
        dict(type='optional', cost=[dict(type='discard_named', n=1, name='牛島 若利')], effects=[dict(type='stat_add', target='same', stat='atk', n=1)],
             **{'if': [dict(type='self_role_name', role='attack', name='五色 工')]})])],
    'HV-P03-079': [dict(timing='event', phases=['draw'], draw_policy='always', effects=[
        dict(type='look_top_two_picks', n=5,
             first=dict(school='疑似ユース', category='CHARACTER', positions=['WS', 'MB', 'S', 'Li']),
             second=dict(school='疑似ユース', category='CHARACTER', positions=['ボール拾い']))])],
    'HV-P04-060': [ON(['attack'], cost=[dict(type='discard_filtered', n=1, filter=dict(school='白鳥沢')), dict(type='guts', n=2)],
                      use_if=[dict(type='allow_discard')], effects=[
        S('atk', 2), dict(type='stat_add', target='this', stat='atk', n=2, **{'if': [dict(type='self_role_name', role='receive', name='大平 獅音'),
                                                                                   dict(type='self_role_name', role='toss', name='天童 覚')]})])],
    'HV-P04-061': [ON(['toss'], cost=[dict(type='discard_filtered', n=1, filter=dict(school='白鳥沢')), dict(type='guts', n=2)],
                      auto_cost=True, use_if=[dict(type='drop_has_name', name='牛島 若利')], effects=[
        dict(type='drop_to_hand', who='self', filter=dict(school='白鳥沢', grade=3), max=1), S('tos', 1)])],
    # ※ 天童 P04-061：「棄牌區白鳥沢 3 年的卡」我只撈角色卡；策略：棄牌區有牛島才發動（撈最有價值的 3 年角色）
    'HV-P04-062': [ON(['receive'], cost=[dict(type='discard_filtered', n=1, filter=dict(school='白鳥沢')), dict(type='guts', n=2)],
                      use_if=[dict(type='receive_below_op')], effects=[
        S('rcv', 2), dict(type='mill_take', n=2, filter=dict(school='白鳥沢', grade=3, category='CHARACTER'))])],
    'HV-PR-028': [ON(['toss'], cost=G(2), effects=[
        dict(type='drop_opp_events_then', n=1, max_left=99, then=[]),
        dict(type='restrict_opp', who='opp', rule='opp_rcv_add', n=-2, duration=TO)])],
    'HV-PR-046': [ON(['block'], cost=[dict(type='discard_filtered', n=1, filter=dict(school='白鳥沢'))], auto_cost=True, effects=[
        S('blk', 3), dict(type='stat_add', target='this', stat='blk', n=2, **{'if': [dict(type='opp_hand_le', n=2)]})])],
    'HV-PR-052': [dict(timing='event', phases=['block'], conditions=[dict(type='all_own_chars_school', school='白鳥沢')], effects=[
        DRAW, S('blk', 1, dict(who='self', count=1, name='天童 覚')),
        dict(type='keyword', name='ドシャット', n=8, **{'if': [dict(type='court_has_name', name='天童 覚'), dict(type='opp_hand_le', n=2)]})])],
    'HV-PR-018': [], 'HV-PR-042': [], 'HV-PR-061': [], 'HV-PR-013': [],
}
NAME_CHOICE_BATCH4 = {
    'HV-PR-036': ['宮 侑', '宮 治'], 'HV-PR-040': ['宮 侑', '宮 治'],
    'HV-PR-059': ['宮 侑', '古森 元也'], 'HV-PR-068': ['宮 治', '角名 倫太郎'],
    'HV-PR-039': ['青根 高伸', '二口 堅治'], 'HV-PR-070': ['青根 高伸', '二口 堅治'],
    'HV-PR-018': ['牛島 若利', '五色 工'], 'HV-PR-042': ['白布 賢二郎', '瀬見 英太'], 'HV-PR-061': ['国見 英', '五色 工'],
}
