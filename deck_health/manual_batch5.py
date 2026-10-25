"""混校研究 結構化第 5 批：雙名卡、各校「登場技」「事件」中能用現有機制表達的。預設關閉（DH_BATCH5=1 啟用），等使用者驗收。
沒做的（觸發型「○○登場時」、手牌丟棄技、球拾い放 Event 區、フェイント、バックアタック、サイドブロッカー特召、疑似ユース／ユース整組）留給第 6 批。"""
TO = 'next_opp_turn'
G = lambda n: [dict(type='guts', n=n)]
S = lambda stat, n, tg='this': dict(type='stat_add', target=tg, stat=stat, n=n)
ON = lambda zones, **kw: dict(timing='on_enter', zones=zones, **kw)
DRAW = dict(type='draw', who='self', n=1)
EV = lambda phases, **kw: dict(timing='event', phases=phases, **kw)
ONE = lambda **kw: dict(who='self', count=1, **kw)
OP4 = dict(type='opp_op_ge', n=4, of='any')
ALL = ['serve', 'block', 'receive', 'toss', 'attack']
YOUTH = dict(type='all_own_chars_affil', affil='ユース')
PYOUTH = dict(type='all_own_chars_affil', affil='疑似ユース')

MANUAL_BATCH5 = {
    # ══ 雙名卡（登場時選名字；技能欄沒有技能）══
    'HV-P01-072': [], 'HV-P01-073': [], 'HV-P02-078': [], 'HV-P03-077': [],
    'HV-PR-012': [], 'HV-PR-015': [], 'HV-PR-016': [], 'HV-PR-038': [], 'HV-PR-041': [],
    'HV-PR-057': [], 'HV-PR-060': [], 'HV-PR-067': [],

    # ══ 登場技 ══
    'HV-P02-070': [ON(['receive'], cost=G(4), effects=[dict(type='draw', who='self', n=2), dict(type='hand_to_deck_bottom', n=1), S('rcv', 3)])],
    # ※ 古森 P02-070：「手牌 1 張放牌庫上或下」固定放下
    'HV-P02-071': [ON(['receive'], cost=G(2), effects=[DRAW, S('rcv', 2)])],
    'HV-P02-073': [ON(['attack'], cost=G(3), effects=[
        S('atk', 4), dict(type='event_to_hand', who='self', filter=dict(school='戸美'), discard_after=True)])],
    'HV-P02-074': [ON(['serve'], cost=G(1), effects=[
        dict(type='stat_add', target='this', stat='srv', n=2, **{'if': [dict(type='paid_guts_all_school', school='戸美')]}),
        dict(type='restrict_opp', who='opp', rule='opp_s_toss_add', n=-1, duration=TO, **{'if': [dict(type='paid_guts_all_school', school='戸美')]})])],
    # ※ 沼井 P02-074：「對手 S 舉球角色登場就 −1」我用「手牌出場的 S 舉球 −1」規則（跟稲荷崎 P04-068 一樣）
    'HV-P02-076': [ON(['attack'], conditions=[dict(type='enter_on_top_name', name='田中 龍之介')], cost=G(4), effects=[S('atk', 2)])],
    'HV-P03-075': [ON(['receive', 'attack'], conditions=[dict(type='self_role_name', role='toss', name='越後 栄')], cost=G(3), effects=[S('any', 3)])],
    'HV-P03-073': [ON(['attack'], cost=[dict(type='guts_each', zones=['receive', 'toss', 'attack'], n=2)], effects=[S('atk', 5), dict(type='restrict_opp', who='opp', rule='nullify_block_skills', duration=TO)])],
    # 小鹿野 P03-073：對手下回合攔網角色技能無效（2026-10-25 補上）
    'HV-P01-060': [ON(['block'], conditions=[OP4], effects=[dict(type='keyword', name='ワンタッチ', n=2)])],
    'HV-P04-041': [ON(['block'], conditions=[OP4], effects=[dict(type='keyword', name='ワンタッチ', n=2)])],
    'HV-P04-051': [ON(['block'], conditions=[OP4], effects=[
        dict(type='mill_tiers', n=1, school='和久谷南', tiers=[dict(ge=1, effects=[dict(type='keyword', name='ワンタッチ', n=3)])])])],
    'HV-P04-039': [ON(['attack'], effects=[
        dict(type='mill_tiers', n=3, count='event', tiers=[dict(ge=1, effects=[S('atk', 2)]), dict(ge=2, effects=[S('atk', 2)]), dict(ge=3, effects=[S('atk', 4)])])])],
    'HV-P04-045': [ON(['receive'], effects=[
        dict(type='mill_tiers', n=3, count='event', tiers=[dict(ge=1, effects=[S('rcv', 2)]), dict(ge=2, effects=[DRAW])])])],
    'HV-P04-044': [ON(['receive'], cost=[dict(type='guts_each', zones=['receive', 'toss', 'attack'], n=2)], effects=[
        S('rcv', 2), dict(type='event_to_hand', who='self', filter=dict(school='条善寺'), include_drop=True, discard_after=True)])],
    'HV-P04-046': [ON(['attack'], cost=G(3), effects=[
        S('atk', 1), dict(type='keyword', name='ブロックアウト', n=2),
        dict(type='draw', who='self', n=1, **{'if': [dict(type='all_own_chars_school', school='和久谷南')]}),
        dict(type='event_to_hand', who='self', filter=dict(name='かつての "小さな巨人"に'), **{'if': [dict(type='all_own_chars_school', school='和久谷南')]})])],
    'HV-P04-049': [ON(['receive'], cost=G(3), effects=[S('rcv', 2)])],
    'HV-P04-050': [ON(['toss'], cost=G(3), effects=[S('tos', 1), dict(type='drop_to_hand', who='self', filter=dict(school='和久谷南', category='CHARACTER'), max=1)])],
    'HV-P04-032': [ON(['attack'], conditions=[dict(type='all_own_chars_school', school='角川')],
                      cost=[dict(type='guts_multi', zones=['block', 'attack'], n=3)], effects=[S('atk', 5),
        dict(type='stat_add', target='this', stat='atk', n=2, **{'if': [dict(type='paid_guts_name_noskill', name='百沢 雄大')]})])],
    # 百沢 P04-032：付的全是沒技能的百沢 → 再 +2（2026-10-25 補上；付 Guts 不刻意挑牌）
    'HV-P04-037': [ON(['block'], cost=[dict(type='discard_filtered', n=1, filter=dict(school='角川'))], use_if=[dict(type='allow_discard')], effects=[
        dict(type='drop_to_hand', who='self', filter=dict(name='百沢 雄大', category='CHARACTER'), max=1),
        dict(type='keyword', name='ワンタッチ', n=2)])],
    # ※ 馬門 P04-037：「本回合不能把百沢登場到接球區」沒模擬（代價是少掉一種接球選擇，實戰影響小）
    'HV-P04-063': [ON(['attack'], cost=G(3), effects=[
        dict(type='stat_add', target='this', stat='atk', n=7, **{'if': [dict(type='paid_guts_school_excl_name', school='梟谷', exclude_name='木兎 光太郎')]})])],
    'HV-P04-064': [ON(['toss'], cost=G(2), effects=[S('tos', 1)])],
    # ※ 木葉 P04-064：「手牌梟谷角色與攻擊區梟谷 Guts 互換」沒模擬
    'HV-P04-065': [ON(['attack'], conditions=[dict(type='self_role_name', role='toss', name='木葉 秋紀')],
                      cost=[dict(type='discard_filtered', n=1, filter=dict(school='梟谷', grade=3))], use_if=[dict(type='allow_discard')], effects=[S('atk', 4)])],
    'HV-P04-066': [ON(['receive'], cost=[dict(type='discard_filtered', n=1, filter=dict(school='梟谷', grade=3)), dict(type='guts', n=2)],
                      use_if=[dict(type='allow_discard')], effects=[
        S('rcv', 1), dict(type='drop_to_hand', who='self', filter=dict(school='梟谷', grade=3, category='CHARACTER'), max=1)])],
    'HV-P04-067': [ON(['serve'], cost=[dict(type='discard_filtered', n=1, filter=dict(school='梟谷', grade=3)), dict(type='guts', n=1)],
                      use_if=[dict(type='allow_discard')], effects=[dict(type='draw', who='self', n=2), S('srv', 3)])],
    'HV-P04-077': [ON(['receive', 'attack'], cost=[dict(type='event_hand_to_evz', n=1, filter=dict(school='ユース'))], effects=[DRAW, S('any', 3)])],
    'HV-PR-001': [ON(ALL, conditions=[dict(type='enter_on_top_name', name='日向 翔陽')], effects=[S('any', 1)])],
    'HV-PR-002': [ON(ALL, conditions=[dict(type='enter_on_top_name', name='影山 飛雄')], effects=[S('any', 1)])],
    'HV-PR-080': [ON(['attack'], conditions=[dict(type='self_role_name', role='toss', name='影山 飛雄')], cost=G(2), effects=[
        dict(type='stat_add', target='this', stat='atk', n=5, **{'if': [dict(type='paid_guts_name', name='日向 翔陽')]})])],
    # ※ PR-080：2 或 3 張擇一——我固定付 2（+3+2 = +5）；付 3 要 +6 但多 1 張 Guts，且要付的全是日向才有效

    # ══ 事件／角色事件 ══
    'HV-P01-079': [EV(['block'], effects=[
        DRAW, S('blk', 1, ONE(school='烏野')),
        dict(type='restrict_opp', who='opp', rule='opp_rcv_add', n=-2, duration=TO, **{'if': [dict(type='self_role_name', role='block', name='月島 蛍')]})])],
    # ※ P01-079：月島時「發球區山口回手牌」沒模擬
    'HV-P02-079': [EV(['attack'], effects=[S('atk', 1, ONE(school='烏野'))])],
    # ※ 谷地 P02-079：「對手輸掉時手牌烏野角色放成 Guts」沒模擬
    'HV-P02-080': [EV(['draw'], draw_policy='always', effects=[DRAW])],
    # ※ 武田 P02-080：「對手 Event 區的教練放回牌庫底後查看牌庫頂 3 張」沒模擬
    'HV-P02-082': [EV(['attack'], effects=[DRAW, S('atk', 1, ONE(name='田中 龍之介')),
        dict(type='restrict_opp', who='opp', rule='drop_side_blocker_once', duration=TO, **{'if': [dict(type='self_role_name', role='attack', name='田中 龍之介')]})])],
    # P02-082：田中攻擊時，對手下回合側翼攔網手出場時只限一次棄置（2026-10-25 補上）
    'HV-P02-092': [EV(['block', 'draw'], draw_policy='always', effects=[DRAW])],
    # ※ P02-092：「中間攔網是伊達工業 3 年時，場上 1・2 年回手牌再棄 1」沒模擬
    'HV-P02-099': [EV(['draw'], draw_policy='always', conditions=[dict(type='self_hand_le', n=4)], effects=[
        dict(type='drop_to_hand', who='self', filter=dict(name='大将 優', category='CHARACTER'), max=1)])],
    # ※ 山架 P02-099：「再從場上戸美 Guts 1 張回手牌」沒模擬
    'HV-P03-078': [EV(['draw'], draw_policy='always', effects=[dict(type='look_top_take', who='self', n=3, school='条善寺', char_only=True, max=1, rest='deck_bottom')])],
    # ※ 穴原 P03-078：疑似ユース角色也算，我只算条善寺；「沒拿的牌可放牌庫上」固定放下
    'HV-P03-095': [EV(['attack'], effects=[
        S('atk', 1, ONE(school='烏野')),
        dict(type='optional', cost=[dict(type='guts_multi', zones=['receive', 'toss', 'attack'], n=6)], effects=[dict(type='draw', who='self', n=2)],
             **{'if': [dict(type='all_own_chars_school', school='烏野')]})])],
    'HV-P03-083': [EV(['receive'], conditions=[YOUTH], effects=[DRAW, S('rcv', 1, ONE())])],
    # ※ 火焼 P03-083：「接球區與攻擊區的ユース Guts 互換」沒模擬
    'HV-P03-084': [EV(['receive'], once_per_turn=True, conditions=[YOUTH], effects=[
        DRAW, S('rcv', 1, ONE()),
        dict(type='stat_add', target='same', stat='rcv', n=1, **{'if': [dict(type='evz_total_le', n=2)]})])],
    'HV-P03-085': [EV(['attack'], once_per_turn=True, effects=[
        DRAW, S('atk', 1, ONE(school='ユース')),
        dict(type='optional', cost=[dict(type='guts', n=3, zone='attack')], effects=[S('atk', 2, 'same')],
             **{'if': [dict(type='self_role_name', role='attack', name='星海 光来')]})])],
    'HV-P03-087': [EV(['receive', 'attack'], once_per_turn=True, conditions=[dict(type='any_of', conds=[dict(type='all_own_chars_school', school='烏野'), YOUTH])], effects=[
        DRAW, S('atk', 1, ONE()),
        dict(type='optional', cost=[dict(type='guts_multi', zones=['receive', 'toss', 'attack'], n=6)], effects=[S('atk', 2, 'same')],
             **{'if': [dict(type='self_role_name', role='attack', name='影山 飛雄')]})])],
    'HV-P03-081': [EV(['block', 'receive', 'attack'], once_per_turn=True, effects=[
        DRAW, dict(type='stat_add', target=ONE(), stat='any', n=1, **{'if': [PYOUTH]}),
        dict(type='draw', who='self', n=1, **{'if': [PYOUTH, dict(type='evz_total_ge', n=8)]})])],
    'HV-P03-082': [EV(['receive'], conditions=[PYOUTH], effects=[DRAW, S('rcv', 1, ONE())])],
    # ※ P03-082：「Event 區 4 張以上時，疑似ユース百沢登場 +1 攻擊」沒模擬
    'HV-P04-101': [EV(['receive', 'attack'], conditions=[dict(type='all_own_chars_affil', affil='町内会')], effects=[
        DRAW, S('rcv', 1, ONE()),
        dict(type='stat_add', target=ONE(), stat='atk', n=1, **{'if': [dict(type='event_zone_name_count_ge', name='おっさんも本気出しちゃうんだぜ', n=4)]})])],
    'HV-P04-090': [EV(['attack'], effects=[
        DRAW,
        dict(type='restrict_opp', who='opp', rule='all_blockers_blk_add', n=-1, duration=TO, **{'if': [dict(type='self_role_name', role='attack', name='百沢 雄大')]}),
        dict(type='restrict_opp', who='opp', rule='opp_rcv_add', n=-1, duration=TO, **{'if': [dict(type='self_role_name', role='attack', name='百沢 雄大')]})])],
    # P04-090：對手每個攔網角色（含側翼）攔網 −1（2026-10-25 改為 all_blockers_blk_add）
    'HV-P04-091': [EV(['receive'], once_per_turn=True, effects=[
        S('rcv', 1, ONE(school='角川', grade=2)),
        dict(type='draw', who='self', n=1, **{'if': [dict(type='self_role_name', role='attack', name='百沢 雄大')]}),
        dict(type='stat_add', target='same', stat='rcv', n=1, **{'if': [dict(type='self_role_name', role='attack', name='百沢 雄大')]})])],
    'HV-P04-092': [EV(['block', 'attack'], effects=[DRAW, S('any', 1, ONE(name='百沢 雄大'))])],
    'HV-P04-093': [EV(ALL, once_per_turn=True, effects=[DRAW])],
    # ※ 三咲 P04-093：「全條善寺時，Event／棄牌區的條善寺卡洗回牌庫」沒模擬
    'HV-P04-094': [EV(['draw', 'receive'], once_per_turn=True, draw_policy='always', effects=[
        DRAW, dict(type='stat_add', target=ONE(school='条善寺'), stat='rcv', n=1, **{'if': [dict(type='phase_is', phase='receive')]})])],
    'HV-P04-095': [EV(['receive', 'attack'], effects=[
        S('any', 1, ONE(school='条善寺')),
        dict(type='mill_tiers', n=3, count='event', tiers=[dict(ge=1, effects=[DRAW, dict(type='stat_add', target='same', stat='rcv', n=1, **{'if': [dict(type='phase_is', phase='receive')]})])])])],
    'HV-P04-096': [EV(['draw'], draw_policy='always', effects=[
        DRAW, dict(type='look_top_take', who='self', n=3, names=['中島 猛', 'かつての "小さな巨人"に'], max=1, rest='deck_bottom')])],
    'HV-P04-097': [EV(['attack'], once_per_turn=True, conditions=[dict(type='all_own_chars_school', school='和久谷南')], effects=[
        dict(type='restrict_opp', who='opp', rule='opp_rcv_add', n=-2, base_ge=5, duration=TO),
        dict(type='restrict_opp', who='opp', rule='opp_rcv_add', n=-1, base_ge=5, duration=TO, **{'if': [dict(type='self_role_name', role='attack', name='中島 猛')]})])],
    'HV-P04-098': [EV(['receive'], effects=[DRAW, dict(type='rcv_best_of', school='和久谷南', set_to=6, min_cur=0)])],
    'HV-PR-050': [EV(['serve', 'draw'], once_per_turn=True, draw_policy='always', effects=[
        DRAW,
        dict(type='draw', who='self', n=1, **{'if': [dict(type='phase_is', phase='serve'), dict(type='self_role_name', role='serve', name='山口 忠')]}),
        dict(type='stat_set_zone', zone='serve', value=6, **{'if': [dict(type='phase_is', phase='serve'), dict(type='self_role_name', role='serve', name='山口 忠')]})])],
}

NAME_CHOICE_BATCH5 = {
    'HV-P01-072': ['日向 翔陽', '孤爪 研磨'], 'HV-P01-073': ['月島 蛍', '黒尾 鉄朗'], 'HV-P02-078': ['澤村 大地', '黒尾 鉄朗'],
    'HV-P03-077': ['日向 翔陽', '百沢 雄大'], 'HV-PR-012': ['日向 翔陽', '影山 飛雄'], 'HV-PR-015': ['及川 徹', '岩泉 一'],
    'HV-PR-016': ['月島 蛍', '山口 忠'], 'HV-PR-038': ['西谷 夕', '東峰 旭'], 'HV-PR-041': ['影山 飛雄', '菅原 孝支'],
    'HV-PR-057': ['日向 翔陽', '西谷 夕'], 'HV-PR-060': ['日向 翔陽', '黄金川 貫至'], 'HV-PR-067': ['田中 龍之介', '澤村 大地'],
}
