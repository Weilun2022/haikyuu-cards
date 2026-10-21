"""混校研究 結構化第 3 批：青葉城西（能用現有機制表達的）。預設關閉（DH_BATCH3=1 啟用），等使用者驗收。"""
TO = 'next_opp_turn'
G = lambda n: [dict(type='guts', n=n)]
S = lambda stat, n, tg='this': dict(type='stat_add', target=tg, stat=stat, n=n)
ON = lambda zones, **kw: dict(timing='on_enter', zones=zones, **kw)
AOS = lambda: dict(type='all_own_chars_school', school='青葉城西')

MANUAL_BATCH3 = {
    'HV-P01-034': [ON(['serve'], cost=G(1), effects=[
        dict(type='opp_reshuffle_draw', n=6, **{'if': [dict(type='paid_guts_all_school', school='青葉城西')]})])],
    'HV-P01-035': [ON(['attack'], cost=[dict(type='discard_filtered', n=1, filter=dict(school='青葉城西'))], use_if=[dict(type='allow_discard')],
                      effects=[S('atk', 2)])],
    # ※ 岩泉 P01-035：「對手手牌 ≤4 時，下回合對手不能用技能加入手牌」沒模擬
    'HV-P01-039': [ON(['receive'], conditions=[dict(type='opp_op_ge', n=6, of='any')],
                      cost=[dict(type='discard_filtered', n=1, filter=dict(school='青葉城西'))], auto_cost=True, effects=[
        S('rcv', 1), dict(type='draw', who='self', n=1, **{'if': [AOS()]})])],
    'HV-P02-056': [ON(['toss'], cost=G(3), effects=[S('tos', 2), dict(type='drop_to_hand', who='self', filter=dict(name='岩泉 一'), max=1)])],
    'HV-P03-005': [ON(['attack'], cost=G(2), effects=[
        dict(type='stat_add', target='this', stat='atk', n=2, **{'if': [dict(type='evz_total_ge', n=4)]}),
        dict(type='restrict_opp', who='opp', rule='opp_atk_add', n=-2, duration=TO, **{'if': [dict(type='evz_total_ge', n=4)]})])],
    'HV-P03-006': [ON(['block'], conditions=[dict(type='opp_op_ge', n=4, of='any')], effects=[dict(type='keyword', name='ワンタッチ', n=2)])],
    'HV-P03-007': [ON(['receive'], cost=G(3), conditions=[dict(type='any_of', conds=[AOS(), dict(type='all_own_chars_school', school='疑似ユース')])], effects=[
        dict(type='draw', who='self', n=1, **{'if': [dict(type='evz_total_ge', n=4)]}),
        dict(type='stat_add', target='this', stat='rcv', n=3, **{'if': [dict(type='evz_total_ge', n=6)]})])],
    'HV-P04-018': [ON(['serve'], cost=G(2), effects=[S('srv', 1), dict(type='opp_discard', n=1, **{'if': [dict(type='opp_hand_ge', n=4)]})])],
    'HV-P04-020': [ON(['attack'], cost=G(3), effects=[S('atk', 4),
        dict(type='restrict_opp', who='opp', rule='max_enter', role='block', max=1, duration=TO, **{'if': [dict(type='zone_stat_ge', zone='attack', n=8)]})])],
    # ※ 岩泉 P04-020：「對手 [レシーブフェイズ][手牌] 技能無效」沒模擬
    'HV-P04-023': [ON(['block'], cost=[dict(type='event_hand_to_evz', n=1, filter=dict(school='青葉城西'))], auto_cost=True,
                      effects=[dict(type='draw', who='self', n=1), S('blk', 3)])],
    'HV-P04-025': [ON(['receive'], conditions=[AOS()], cost=G(3), effects=[S('rcv', 3), dict(type='keyword', name='Aパス', n=1)])],
    'HV-P04-030': [ON(['attack'], conditions=[dict(type='self_role_name', role='toss', name='矢巾 秀')],
                      cost=[dict(type='discard_filtered', n=1, filter=dict(school='青葉城西')), dict(type='guts', n=2)], use_if=[dict(type='allow_discard')],
                      effects=[S('atk', 4)])],
    'HV-D04-001': [ON(['serve', 'toss'], cost=G(2), effects=[
        dict(type='stat_add', target='this', stat='any', n=2, **{'if': [dict(type='paid_guts_all_school', school='青葉城西')]})])],
    'HV-D04-002': [ON(['attack'], conditions=[dict(type='self_role_name', role='toss', name='及川 徹')], cost=G(2), effects=[
        S('atk', 3), dict(type='stat_add', target='this', stat='atk', n=1, **{'if': [dict(type='self_set_fewer')]})])],
    'HV-D04-008': [ON(['receive'], cost=G(4), effects=[dict(type='draw', who='self', n=1), S('rcv', 2)])],
    'HV-PR-024': [ON(['toss'], cost=G(3), effects=[S('tos', 2), dict(type='opp_reshuffle_draw', n=4)])],
    'HV-PR-025': [ON(['attack'], conditions=[dict(type='self_role_name', role='toss', name='及川 徹')], cost=G(3), effects=[
        S('atk', 2), dict(type='opp_discard', n=1, **{'if': [dict(type='opp_hand_ge', n=3)]})])],
    'HV-PR-009': [], 'HV-PR-017': [], 'HV-PR-069': [],
    # ── 事件 ──
    'HV-P01-085': [dict(timing='event', phases=['draw'], draw_policy='always', effects=[dict(type='draw', who='self', n=1)])],
    # ※ 入畑 P01-085：「場上合計付 8 Guts → 本回合青葉城西角色登場各 +1」沒模擬（只算抽 1）
    'HV-P01-086': [dict(timing='event', phases=['draw', 'receive'], draw_policy='always', effects=[
        dict(type='drop_to_hand', who='self', filter=dict(school='青葉城西', category='CHARACTER'), max=1)])],
    'HV-P01-087': [dict(timing='event', phases=['toss'], conditions=[dict(type='self_role_name', role='toss', name='及川 徹')], effects=[
        dict(type='draw', who='self', n=1), S('tos', 1, dict(who='self', count=1, name='及川 徹'))])],
    # ※ P01-087：[サーブ] 階段用法與「對手以非抽牌方式加入手牌就要棄牌」沒模擬
    'HV-P01-088': [dict(timing='event', phases=['receive'], effects=[
        dict(type='draw', who='self', n=1), S('rcv', 1, dict(who='self', count=1, school='青葉城西')),
        dict(type='stat_add', target='same', stat='rcv', n=1, **{'if': [dict(type='self_hand_le', n=3)]})])],
    'HV-P04-085': [dict(timing='event', phases=['draw', 'receive'], draw_policy='always', effects=[
        dict(type='look_top_take', who='self', n=3, school='青葉城西', max=1, rest='deck_bottom')])],
    'HV-P04-086': [dict(timing='event', phases=['draw'], draw_policy='always', effects=[
        dict(type='draw', who='self', n=1),
        dict(type='drop_to_hand', who='self', filter=dict(name='京谷 賢太郎'), max=1, **{'if': [dict(type='self_hand_le', n=4)]})])],
    'HV-P04-087': [dict(timing='event', phases=['draw'], draw_policy='always', effects=[dict(type='draw', who='self', n=1)])],
    # ※ P04-087：[サーブ] 階段（棄牌區的及川登場＋對手不能補牌）沒模擬，只算抽牌階段選項
    'HV-P04-088': [dict(timing='event', phases=['attack'], once_per_turn=True, effects=[
        dict(type='draw', who='self', n=1), S('atk', 1, dict(who='self', count=1, school='青葉城西')),
        dict(type='restrict_opp', who='opp', rule='opp_rcv_add', n=-1, duration=TO, **{'if': [dict(type='zone_stat_ge', zone='attack', n=8)]})])],
    'HV-P04-089': [dict(timing='event', phases=['receive'], once_per_turn=True, effects=[
        dict(type='draw', who='self', n=1), S('rcv', 1, dict(who='self', count=1, school='青葉城西', grade=3)),
        dict(type='optional', cost=[dict(type='discard_filtered', n=1, filter=dict(school='青葉城西', grade=3, category='CHARACTER'))],
             effects=[dict(type='stat_add', target='same', stat='rcv', n=2)])])],
    'HV-D04-012': [dict(timing='event', phases=['attack'], once_per_turn=True, effects=[
        S('atk', 1, dict(who='self', count=1, school='青葉城西')), dict(type='draw', who='self', n=1)])],
    # ※ D04-012：[サーブ] 階段用法沒模擬
    'HV-D04-013': [dict(timing='event', phases=['receive'], effects=[
        S('rcv', 1, dict(who='self', count=1, school='青葉城西')), dict(type='reveal_top_take_school', school='青葉城西')])],
    'HV-PR-051': [dict(timing='event', phases=['attack'], effects=[
        dict(type='draw', who='self', n=1),
        dict(type='optional', cost=[dict(type='guts', n=2, zone='attack')], effects=[dict(type='stat_add', target='same', stat='atk', n=2)],
             **{'if': [dict(type='self_role_name', role='attack', name='岩泉 一')]})])],
    # ※ PR-051：「下回合自己的進攻值不會被減」沒模擬
}
NAME_CHOICE_BATCH3 = {
    'HV-PR-009': ['及川 徹', '岩泉 一'],
    'HV-PR-017': ['金田一 勇太郎', '国見 英'],
    'HV-PR-069': ['及川 徹', '金田一 勇太郎'],
}
