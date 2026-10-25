"""混校研究 結構化第 2 批：音駒（能用現有機制表達的）。預設關閉（DH_BATCH2=1 啟用），等使用者驗收。
沒做的（觸發型／手牌發動／サイドブロッカー／バックアタック）見 batch2_review.md 最後一段。"""
TO = 'next_opp_turn'
G = lambda n: [dict(type='guts', n=n)]
S = lambda stat, n, tg='this': dict(type='stat_add', target=tg, stat=stat, n=n)
ON = lambda zones, **kw: dict(timing='on_enter', zones=zones, **kw)
ALL_Z = ['receive', 'toss', 'attack', 'block', 'serve']
KO = 'school'  # 備忘

MANUAL_BATCH2 = {
    'HV-P01-018': [ON(['toss'], cost=G(3), effects=[S('tos', 1),
        dict(type='event_to_hand', who='self', filter={}, max=1, **{'if': [dict(type='all_own_chars_school', school='音駒')]})])],
    'HV-P01-021': [ON(['attack'], cost=G(3), effects=[S('atk', 3), dict(type='guts_to_hand_same_school', n=2, distinct=True)])],
    'HV-P01-025': [ON(['attack'], cost=G(2), effects=[
        dict(type='stat_add', target='this', stat='atk', n=2, **{'if': [dict(type='entered_by', card_name='孤爪 研磨')]}),
        dict(type='restrict_opp', who='opp', rule='center_blocker_blk_add', n=-3, duration=TO)])],
    # ※ 灰羽 P01-025 的「孤爪 研磨のスキルで登場」：研磨 P01-019 還沒結構化（觸發型），所以 +2 目前不會成立
    'HV-P01-032': [ON(['serve'], effects=[dict(type='restrict_opp', who='opp', rule='nullify_receive_toss_skills', duration=TO)])],
    'HV-P02-061': [ON(['receive'], cost=G(2), effects=[S('rcv', 3),
        dict(type='stat_add', target='this', stat='rcv', n=3, **{'if': [dict(type='opp_role_base_le', role='attack', stat='atk', n=0)]})])],
    'HV-P02-062': [ON(['receive'], cost=G(2), effects=[
        dict(type='look_top_take', who='self', n=2, school='音駒', char_only=True, max=1, rest='deck_bottom')])],
    'HV-P03-031': [ON(['toss'], cost=G(2), effects=[
        dict(type='stat_add', target='this', stat='tos', n=2, **{'if': [dict(type='paid_guts_all_pos', position='S'), dict(type='paid_guts_all_school', school='音駒')]}),
        dict(type='look_top_take', who='self', n=3, school='音駒', event_only=True, max=1, rest='deck_bottom',
             **{'if': [dict(type='paid_guts_all_pos', position='S'), dict(type='paid_guts_all_school', school='音駒')]})])],
    'HV-P03-035': [ON(['receive'], cost=G(3), effects=[dict(type='draw', who='self', n=1), S('rcv', 2)])],
    'HV-P03-036': [ON(['block'], conditions=[dict(type='opp_op_ge', n=4, of='any')], effects=[dict(type='keyword', name='ワンタッチ', n=2)])],
    'HV-P03-038': [ON(['block'], cost=[dict(type='discard_filtered', n=1, filter=dict(school='音駒'))], auto_cost=True, effects=[
        S('blk', 3), dict(type='stat_add', target='this', stat='blk', n=2, **{'if': [dict(type='opp_hand_le', n=2)]})])],
    'HV-P04-053': [ON(['attack'], cost=G(2), effects=[
        dict(type='stat_add', target='this', stat='atk', n=3, **{'if': [dict(type='self_role_name', role='receive', name='夜久 衛輔'),
                                                                        dict(type='self_role_name', role='toss', name='海 信行')]})])],
    'HV-P04-054': [ON(['receive'], conditions=[dict(type='opp_op_le', n=3, of='any')], effects=[dict(type='keyword', name='Aパス', n=1)])],
    'HV-P04-055': [ON(['receive'], cost=G(2), effects=[S('rcv', 1),
        dict(type='look_top_take', who='self', n=3, names=['黒尾 鉄朗', '海 信行'], max=1, rest='deck_bottom')])],
    'HV-D02-001': [ON(['toss'], cost=G(2), effects=[S('tos', 1), dict(type='restrict_opp', who='opp', rule='opp_atk_add', n=-2, duration=TO)])],
    'HV-D02-002': [ON(['block'], cost=G(1), effects=[dict(type='keyword', name='ドシャット', n=5)])],
    'HV-D02-003': [ON(['receive'], cost=[dict(type='discard_hand', n=1)], effects=[S('rcv', 2)])],
    'HV-PR-044': [ON(['block', 'receive'], cost=[dict(type='event_hand_to_evz', n=1, filter=dict(school='音駒'))], effects=[
        dict(type='draw', who='self', n=1), S('any', 3)])],
    # ── 雙名卡（名字在登場時選，沿用既有機制）──
    'HV-PR-014': [], 'HV-PR-058': [], 'HV-PR-062': [],
    # ── 事件／應援 ──
    'HV-P01-080': [dict(timing='event', phases=['receive'], effects=[
        dict(type='draw', who='self', n=1), S('rcv', 1, dict(who='self', count=1)),
        dict(type='stat_add', target='same', stat='rcv', n=2, **{'if': [dict(type='event_zone_phase_count_ge', who='opp', phases=['toss', 'attack'], n=5)]})])],
    'HV-P01-081': [dict(timing='event', phases=['attack'], effects=[
        dict(type='draw', who='self', n=1), S('atk', 1, dict(who='self', count=1, school='音駒')),
        dict(type='optional', cost=[dict(type='guts', n=3, zone='receive')],
             effects=[dict(type='stat_add', target='same', stat='atk', n=1)],
             **{'if': [dict(type='all_own_chars_school', school='音駒')]})])],
    'HV-P01-082': [dict(timing='event', phases=['receive'], effects=[
        dict(type='draw', who='self', n=1), dict(type='rcv_best_of', school='音駒')])],
    'HV-P01-083': [dict(timing='event', phases=['attack'], effects=[
        dict(type='draw', who='self', n=1),
        dict(type='optional', cost=[dict(type='guts_multi', zones=ALL_Z, n=6)],
             effects=[S('atk', 3, dict(who='self', count=1))],
             **{'if': [dict(type='all_own_chars_school', school='音駒')]})])],
    'HV-P01-084': [dict(timing='event', phases=['toss'], conditions=[dict(type='self_role_name', role='toss', name='孤爪 研磨')], effects=[
        dict(type='draw', who='self', n=1), S('tos', 1, dict(who='self', count=1)),
        dict(type='restrict_opp', who='opp', rule='cannot_enter_pos_from_hand', role='attack', position='MB', duration=TO)])],
    'HV-P02-100': [dict(timing='event', phases=['block', 'receive', 'attack'], once_per_turn=True, effects=[
        dict(type='draw', who='self', n=1),
        dict(type='stat_add', target=dict(who='self', count=1, name='灰羽 リエーフ'), stat='any_phase', n=1)])],
    'HV-P03-088': [dict(timing='event', phases=['draw'], draw_policy='always', conditions=[dict(type='self_hand_le', n=4)],
                        use_if=[dict(type='guts_pair_same_school', n=2)], effects=[
        dict(type='guts_to_hand_same_school', n=2, distinct=True),
        dict(type='drop_to_deck_bottom_if_took', school='音駒')])],
    'HV-P03-089': [dict(timing='event', phases=['draw', 'receive'], draw_policy='always', effects=[
        dict(type='drop_to_hand', who='self', filter=dict(school='音駒', category='CHARACTER'), max=1)])],
    'HV-D02-011': [dict(timing='event', phases=['block', 'receive'], effects=[
        dict(type='draw', who='self', n=1),
        dict(type='stat_add', target=dict(who='self', count=1, name='黒尾 鉄朗'), stat='blk', n=1, **{'if': [dict(type='phase_is', phase='block')]}),
        dict(type='stat_add', target=dict(who='self', count=1), stat='rcv', n=1, **{'if': [dict(type='phase_is', phase='receive')]})])],
    # D02-011：二選一。攔網階段選「黒尾攔網 +1」（2026-10-25 補上），接球階段選「接球 +1」
    'HV-D02-012': [dict(timing='event', phases=['draw'], draw_policy='always', effects=[
        dict(type='draw', who='self', n=1),
        dict(type='look_top_take', who='self', n=3, names=['灰羽 リエーフ', '犬岡 走'], max=1, rest='deck_bottom')])],
    'HV-PR-030': [dict(timing='event', phases=['receive'], once_per_turn=True, effects=[
        S('rcv', 2, dict(who='self', count=1, school='音駒')),
        dict(type='draw', who='self', n=1, **{'if': [dict(type='self_role_name', role='receive', name='芝山 優生')]})])],
    'HV-PR-084': [dict(timing='event', phases=['attack'], once_per_turn=True, effects=[
        dict(type='draw', who='self', n=1), S('atk', 1, dict(who='self', count=1, name='山本 猛虎')),
        dict(type='stat_add', target='same', stat='atk', n=1, **{'if': [dict(type='zone_entered_by_skill', zone='attack')]})])],
    # PR-084：該角色是以技能出場時再 +1（2026-10-25 補上；以技能叫出的記錄在 T['by_skill']）
}
NAME_CHOICE_BATCH2 = {
    'HV-PR-014': ['孤爪 研磨', '黒尾 鉄朗'],
    'HV-PR-058': ['黒尾 鉄朗', '山本 猛虎'],
}
