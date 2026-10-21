"""混校研究 結構化第 1 批：烏野一線（角色 + 事件）。依日文 skill_jp 逐張結構化。
預設關閉（DH_BATCH1=1 才啟用），等使用者驗收中文反向翻譯後改預設開。
未模擬／簡化的部分都寫在各卡註解的「※」。"""
TO = 'next_opp_turn'
G = lambda n: [dict(type='guts', n=n)]
S = lambda stat, n, tg='this': dict(type='stat_add', target=tg, stat=stat, n=n)
ON = lambda zones, **kw: dict(timing='on_enter', zones=zones, **kw)

MANUAL_BATCH1 = {
    # ── 角色 ─────────────────────────────────────────
    'HV-D01-001': [ON(['attack'], cost=G(2), effects=[S('atk', 2)])],   # 日向：付 2 Guts，攻擊 +2
    'HV-D01-002': [ON(['toss'], cost=G(2), effects=[S('tos', 2)])],     # 影山：付 2 Guts，舉球 +2
    'HV-D01-003': [ON(['block'], conditions=[dict(type='opp_op_le', n=4, of='any')], cost=G(1),
                      effects=[dict(type='draw', who='self', n=1)])],   # 月島：對手進攻值 ≤4，付 1 Guts：抽 1
    'HV-D01-007': [ON(['receive'], cost=[dict(type='discard_hand', n=1)], effects=[S('rcv', 3)])],  # 縁下：丟手牌 1 張，接球 +3
    'HV-P01-003': [ON(['attack'], conditions=[dict(type='entered_from_hand'), dict(type='self_hand_le', n=3),
                                              dict(type='self_role_name', role='toss', name='影山 飛雄')],
                      effects=[S('atk', 2), dict(type='restrict_opp', who='opp', rule='max_enter', role='block', max=2, duration=TO)])],
    'HV-P01-008': [ON(['block'], cost=G(2), effects=[
        dict(type='stat_add', target='this', stat='blk', n=2, **{'if': [dict(type='court_has_name', name='山口 忠')]}),
        dict(type='keyword', name='ドシャット', n=6)])],               # 月島：付 2 Guts；有山口 → 攔網 +2；ドシャット(6)
    'HV-P01-010': [ON(['serve'], effects=[
        dict(type='reveal_top_then', who='self', school='烏野',
             then=[dict(type='restrict_opp', who='opp', rule='opp_toss_add', n=-2, duration=TO)])])],  # 山口：翻到烏野 → 對手舉球角色登場舉球 −2
    'HV-P01-015': [ON(['toss'], cost=G(2), effects=[dict(type='draw', who='self', n=1), S('tos', 1)])],
    'HV-P01-016': [ON(['attack'], conditions=[dict(type='self_role_school_pos', role='toss', school='烏野', position='S')],
                      cost=G(4), effects=[S('atk', 2)])],
    'HV-P02-002': [ON(['toss'], cost=[dict(type='discard_hand', n=1), dict(type='guts', n=2)], auto_cost=True,
                      use_if=[dict(type='drop_has_name', name='田中 龍之介')],
                      effects=[S('tos', 2), dict(type='drop_to_hand', who='self', filter=dict(name='田中 龍之介'), max=1)])],
    'HV-P02-006': [ON(['receive'], conditions=[dict(type='event_zone_phase_count_ge', who='opp', phases=['serve'], n=3)],
                      effects=[dict(type='draw', who='self', n=1), S('rcv', 3)])],
    'HV-P02-012': [ON(['receive'], conditions=[dict(type='set_total_le', n=1)], cost=G(3), effects=[S('rcv', 3)])],
    'HV-P02-014': [ON(['serve'], effects=[
        dict(type='stat_add', target='this', stat='srv', n=2, **{'if': [dict(type='event_zone_school_count_ge', who='self', school='烏野', n=4)]}),
        dict(type='stat_add', target='this', stat='srv', n=1, **{'if': [dict(type='event_zone_school_count_ge', who='self', school='烏野', n=6)]})])],
    'HV-P03-051': [ON(['receive'], cost=G(2), effects=[
        dict(type='stat_add', target='this', stat='rcv', n=2, **{'if': [dict(type='paid_guts_all_school', school='烏野')]}),
        dict(type='opp_op_add', n=-3, **{'if': [dict(type='paid_guts_all_school', school='烏野'),
                                                dict(type='opp_role_base_le', role='attack', stat='atk', n=0)]})])],
    # ※ 西谷 P03-051：「払ったカードすべてが烏野の場合」に 2 個效果都掛在條件下，是我的讀法（待驗收）
    'HV-P03-053': [ON(['attack'], conditions=[dict(type='self_role_name', role='toss', name='影山 飛雄')], cost=G(3), effects=[
        S('atk', 3),
        dict(type='restrict_opp', who='opp', rule='nullify_doshat', duration=TO),
        dict(type='restrict_opp', who='opp', rule='center_blocker_blk_add', n=-4, duration=TO)])],
    'HV-P03-054': [ON(['serve'], effects=[dict(type='restrict_opp', who='opp', rule='opp_s_toss_set', value=1, duration=TO)])],
    'HV-P04-004': [ON(['serve'], effects=[dict(type='restrict_opp', who='opp', rule='li_receive_add', n=-1, duration=TO)])],
    'HV-P04-005': [ON(['toss'], conditions=[dict(type='enter_on_top_school_pos', school='烏野', position='S')], cost=G(2), effects=[S('tos', 3)])],
    'HV-P04-006': [ON(['attack'], conditions=[dict(type='opp_court_has_grade', grade=2)], cost=G(2), effects=[S('atk', 3)])],
    'HV-P04-007': [ON(['receive'], cost=G(3), effects=[
        dict(type='rcv_add_paid_blk', **{'if': [dict(type='paid_guts_distinct_school', school='烏野')]})])],
    'HV-P04-009': [ON(['receive'], cost=[dict(type='discard_filtered', n=2, filter=dict(school='烏野'))],
                      use_if=[dict(type='receive_below_op')], effects=[
        dict(type='draw', who='self', n=1), S('rcv', 2),
        dict(type='stat_add', target='this', stat='rcv', n=1, **{'if': [dict(type='drop_distinct_names_ge', school='烏野', n=8)]}),
        dict(type='keyword', name='Aパス', n=1, **{'if': [dict(type='drop_distinct_names_ge', school='烏野', n=8)]})])],
    'HV-P04-013': [ON(['attack'], cost=[dict(type='discard_filtered', n=1, filter=dict(school='烏野'))],
                      use_if=[dict(type='allow_discard')], effects=[
        S('atk', 2),
        dict(type='restrict_opp', who='opp', rule='nullify_center_skills', duration=TO,
             **{'if': [dict(type='drop_distinct_names_ge', school='烏野', n=8)]})])],
    'HV-P04-014': [ON(['receive'], cost=[dict(type='discard_filtered', n=1, filter=dict(school='烏野'))],
                      use_if=[dict(type='receive_below_op'), dict(type='guts_has_name', zone='receive', name='澤村 大地')],
                      effects=[dict(type='guts_to_zone', who='self', zone='receive', filter=dict(name='澤村 大地'), max=1,
                                    then=dict(type='stat_add', target='that', stat='rcv', n=1))])],
    'HV-P04-078': [ON(['serve'], conditions=[dict(type='event_zone_name_count_ge', who='self', name='おっさんも本気出しちゃうんだぜ', n=4)],
                      effects=[dict(type='draw', who='self', n=1),
                               dict(type='restrict_opp', who='opp', rule='cannot_enter', role='receive', base_rcv_ge=4, duration=TO)])],
    'HV-P04-079': [ON(['receive', 'attack'], cost=G(3), effects=[
        S('any', 3),
        dict(type='stat_add', target='this', stat='any', n=1,
             **{'if': [dict(type='event_zone_name_count_ge', who='self', name='おっさんも本気出しちゃうんだぜ', n=4)]})])],
    'HV-P04-080': [ON(['toss'], cost=G(2), effects=[
        S('tos', 2), dict(type='look_top_take', who='self', n=3, names=['おっさんも本気出しちゃうんだぜ'], max=1, rest='deck_bottom')])],
    'HV-PR-003': [ON(['attack'], cost=[dict(type='discard_hand', n=1)], effects=[S('atk', 2)])],
    'HVBP-002': [ON(['attack'], cost=[dict(type='discard_hand', n=1)], effects=[S('atk', 2)])],
    'HV-PR-004': [ON(['toss'], cost=G(2), effects=[dict(type='draw', who='self', n=1)])],
    'HVBP-003': [ON(['toss'], cost=G(2), effects=[dict(type='draw', who='self', n=1)])],
    'HVBP-004': [ON(['toss'], cost=G(2), effects=[dict(type='draw', who='self', n=1)])],
    'HV-PR-037': [ON(['attack'], cost=[dict(type='discard_hand', n=1)], effects=[S('atk', 3)])],  # ※「巣立て ヒナガラス」要喊出來，不模擬
    'HVBP-009': [ON(['receive', 'attack'], cost=G(2), effects=[S('any', 1)])],

    # ── 事件 ─────────────────────────────────────────
    'HV-D01-011': [dict(timing='event', phases=['receive'], effects=[
        dict(type='draw', who='self', n=1), S('rcv', 1, dict(who='self', count=1)),
        dict(type='stat_add', target='same', stat='rcv', n=1, **{'if': [dict(type='zone_stat_le', zone='receive', n=4)]})])],
    'HV-P01-075': [dict(timing='event', phases=['receive', 'attack'], effects=[
        dict(type='stat_add', target=dict(who='self', count=1, school='烏野'), stat='any_phase', n=1),
        dict(type='draw', who='self', n=1, **{'if': [dict(type='phase_is', phase='receive')]})])],
    'HV-P01-076': [dict(timing='event', phases=['draw'], draw_policy='always',
                        conditions=[dict(type='self_hand_le', n=4)], use_if=[dict(type='guts_pair_same_school', n=2)],
                        effects=[dict(type='guts_to_hand_same_school', n=2)])],
    'HV-P01-077': [dict(timing='event', phases=['receive'], once_per_turn=True, effects=[
        S('rcv', 2, dict(who='self', count=1, school='烏野')),
        dict(type='draw', who='self', n=1, **{'if': [dict(type='self_role_name', role='receive', name='西谷 夕')]})])],
    'HV-P02-081': [dict(timing='event', phases=['receive'], effects=[
        dict(type='draw', who='self', n=1),
        dict(type='stat_add', target=dict(who='self', count=1, school='烏野'), stat='any_phase', n=1)])],
    # ※ 田中冴子 P02-081 的「接球值改回原本值」不模擬（只在被減值時有用）
    'HV-P03-094': [dict(timing='event', phases=['draw'], once_per_turn=True, draw_policy='always', effects=[
        dict(type='look_top_take', who='self', n=3, school='烏野', event_only=True, max=1, rest='deck_bottom'),
        dict(type='this_event_to_hand_if_took')])],
    'HV-P03-096': [dict(timing='event', phases=['receive', 'attack'], once_per_turn=True, effects=[
        dict(type='draw', who='self', n=1),
        dict(type='stat_add', target=dict(who='self', count=1, name='日向 翔陽'), stat='any_phase', n=1)])],
    # ※ 日向夏 的攔網階段用法不模擬
    'HV-P04-084': [dict(timing='event', phases=['receive', 'toss', 'attack'], once_per_turn=True,
                        conditions=[dict(type='evz_total_le', n=5)], effects=[
        dict(type='draw', who='self', n=1),
        dict(type='stat_add', target=dict(who='self', count=1, school='烏野', grade=3), stat='rcv', n=1),
        dict(type='draw', who='self', n=1, **{'if': [dict(type='drop_distinct_names_ge', school='烏野', n=8)]}),
        dict(type='stat_add', target=dict(who='self', count=1), stat='any_phase', n=2,
             **{'if': [dict(type='drop_distinct_names_ge', school='烏野', n=8)]})])],
    'HV-PR-029': [dict(timing='event', phases=['draw'], draw_policy='always', effects=[
        dict(type='drop_to_hand', who='self', filter=dict(name='日向 翔陽'), max=1),
        dict(type='drop_to_hand', who='self', filter=dict(name='影山 飛雄'), max=1)])],
    'HV-PR-078': [dict(timing='event', phases=['draw'], draw_policy='always',
                       conditions=[dict(type='self_hand_ge', n=4), dict(type='self_hand_le', n=4)],
                       effects=[dict(type='guts_grade_to_hand', n=1, grade=1)])],
    'HVBP-013': [dict(timing='event', phases=['attack'], effects=[
        dict(type='stat_add', target=dict(who='self', count=1), stat='atk', n=1),
        dict(type='restrict_opp', who='opp', rule='max_enter', role='block', max=2, duration=TO,
             **{'if': [dict(type='self_role_name', role='toss', name='影山 飛雄'),
                       dict(type='self_role_name', role='attack', name='日向 翔陽')]})])],
    'HVBP-014': [dict(timing='event', phases=['receive'], effects=[
        dict(type='stat_add', target=dict(who='self', count=1), stat='rcv', n=1),
        dict(type='draw', who='self', n=1, **{'if': [dict(type='self_hand_le', n=3)]})])],
    # ※ P04-101（町内会限定）此批不結構化：「自分のキャラすべてが町内会」在烏野牌組幾乎不成立，且需要 affil 條件，留到後面
}
NAME_CHOICE_BATCH1 = {}
