"""混校研究 結構化第 8 批：フェイント、ユース組（星海・佐久早）、天童／山口（對手加牌我抽）、西谷／日向（被技能叫出才有效）、
事件（探せ、戦術的ワンポイントツーセッター!!!、スタートライン）14 張。預設關閉（DH_BATCH8=1 啟用）。
略過：P04-100「勝てよ…!」與 PR-063「ジャンバル最高!!」（雙方都抽 2，依你的指示不做）。"""
TO = 'next_opp_turn'
G = lambda n: [dict(type='guts', n=n)]
S = lambda stat, n, tg='this': dict(type='stat_add', target=tg, stat=stat, n=n)
ON = lambda zones, **kw: dict(timing='on_enter', zones=zones, **kw)
EV = lambda phases, **kw: dict(timing='event', phases=phases, **kw)
DRAW = lambda n=1: dict(type='draw', who='self', n=n)
RB = dict(type='receive_below_op')
YOUTH = dict(type='all_own_chars_affil', affil='ユース')
PYOUTH = dict(type='all_own_chars_affil', affil='疑似ユース')
YEV = dict(type='evz_drop', n=1, affil='ユース')

NAME_CHOICE_BATCH8 = {}
MANUAL_BATCH8 = {
    # ══ フェイント ══
    # 国見 P01-041：全場青葉城西、對手手牌 ≤3、付 1 Guts → フェイント(4)【策略：比目前進攻值高才用】
    'HV-P01-041': [ON(['attack'], conditions=[dict(type='all_own_chars_school', school='青葉城西'), dict(type='opp_hand_le', n=3)],
                      cost=G(1), use_if=[dict(type='offense_below', n=4)], effects=[dict(type='feint', n=4)])],
    # 東山 P04-043：牌庫頂最多 3 張丟棄；事件 1 張→フェイント(4)，≥2 張→フェイント(7)【策略：進攻值 <4 才用；牌庫頂固定丟 3 張】
    'HV-P04-043': [ON(['attack'], use_if=[dict(type='offense_below', n=4)], effects=[dict(type='mill_feint', n=3)])],

    # ══ ユース組 ══
    # 星海 P03-023：全場ユース → Event 區丟ユース 1 張，一個參數 +3（攔網／接球／攻擊區登場）【策略：攔網不夠／接不住才用；攻擊一律用】
    'HV-P03-023': [ON(['block'], conditions=[YOUTH], cost=[YEV], use_if=[dict(type='block_short')], effects=[S('any', 3)]),
                   ON(['receive'], conditions=[YOUTH], cost=[YEV], use_if=[RB], effects=[S('any', 3)]),
                   ON(['attack'], conditions=[YOUTH], cost=[YEV], effects=[S('any', 3)])],
    # 佐久早 P03-026：Event 區丟ユース 1 張，攔網 +2（攔網區登場）【策略：一律使用（登場時還不知道後面側邊攔網夠不夠）】
    'HV-P03-026': [ON(['block'], cost=[YEV], effects=[S('blk', 2)])],
    # 星海 P04-076：付 2 Guts，付的全是ユース的 S → 抽 1、舉球 +1、棄牌區ユース事件 1 張放進 Event 區
    'HV-P04-076': [ON(['toss'], cost=G(2), effects=[
        dict(type='draw', who='self', n=1, **{'if': [dict(type='paid_guts_all_affil_pos', affil='ユース', position='S')]}),
        dict(type='stat_add', target='this', stat='tos', n=1, **{'if': [dict(type='paid_guts_all_affil_pos', affil='ユース', position='S')]}),
        dict(type='drop_to_evz', filter=dict(category='EVENT', affil='ユース'), **{'if': [dict(type='paid_guts_all_affil_pos', affil='ユース', position='S')]})])],
    # 佐久早 PR-081：全場ユース → Event 區丟ユース事件 1 或 2 張，一個參數 +2；丟 2 張再加攻擊 +1 並ブロックアウト(2)【策略：有 2 張就丟 2 張】
    'HV-PR-081': [ON(['serve', 'attack'], conditions=[YOUTH], cost=[dict(type='evz_drop_upto', n=2, affil='ユース')], effects=[
        S('any', 2),
        dict(type='stat_add', target='this', stat='atk', n=1, **{'if': [dict(type='evz_paid_ge', n=2), dict(type='entering_zone', zone='attack')]}),
        dict(type='keyword', name='ブロックアウト', n=2, **{'if': [dict(type='evz_paid_ge', n=2)]})])],

    # ══ 對手加牌我抽 ══
    # 天童 P01-057：下個對手回合，對手每次以「抽牌以外」的方法加牌，自己抽 1
    'HV-P01-057': [ON(['block'], effects=[dict(type='restrict_opp', who='opp', rule='owner_draw_nondraw', duration=TO)])],
    # 山口 P02-004：疊在烏野角色上登場時，對手可以放 1 張事件到 Event 區；沒放的話下個對手回合對手每次加牌（含抽牌），自己抽 1
    # 依你的指示：對手手牌有事件時，60% 機率會放一張到 Event 區（效果不生效）；沒事件可放就一定生效。※對手放的那張牌沒有實際移到對手 Event 區（搜尋分支不改動對手）
    'HV-P02-004': [ON(['serve'], conditions=[dict(type='enter_on_top_school', school='烏野')],
                      effects=[dict(type='lock_unless_opp_places', p_place=0.6, lock=dict(rule='owner_draw_any', duration=TO))])],

    # ══ 被技能叫出才有效 ══
    # 西谷 P02-005：被「助けてもらう!!!」叫出、付 2 Guts → 接球 +2，棄牌區「木下 久志」1 張回手牌
    'HV-P02-005': [ON(['receive'], conditions=[dict(type='entered_by', card_name='助けてもらう!!!')], cost=G(2), effects=[
        S('rcv', 2), dict(type='drop_to_hand', who='self', filter=dict(name='木下 久志', category='CHARACTER'), max=1)])],
    # 日向 P04-001：全場烏野、手牌丟烏野 2 張；被「影山 飛雄」的技能叫出時攻擊 +3，下個對手回合中間攔網登場 −3
    # 【策略：只在被影山叫出時才付代價（不然白丟 2 張）】
    'HV-P04-001': [ON(['attack'], conditions=[dict(type='all_own_chars_school', school='烏野')], use_if=[dict(type='entered_by', card_name='影山 飛雄')],
                      cost=[dict(type='discard_hand_filtered', n=2, filter=dict(school='烏野'))], effects=[
        S('atk', 3), dict(type='restrict_opp', who='opp', rule='center_blocker_blk_add', n=-3, duration=TO)])],
    # 月島 P03-003：付 2 Guts，全場烏野或全場疑似ユース、Event 區 ≥6 張 → 攻擊 +3，下個對手回合中間攔網登場 −3
    'HV-P03-003': [ON(['attack'], conditions=[dict(type='any_of', conds=[dict(type='all_own_chars_school', school='烏野'), PYOUTH]),
                                              dict(type='evz_total_ge', n=6)], cost=G(2), effects=[
        S('atk', 3), dict(type='restrict_opp', who='opp', rule='center_blocker_blk_add', n=-3, duration=TO)])],

    # ══ 事件 ══
    # 探せ P03-080（抽牌階段）：接球／舉球／攻擊區各付 2 Guts → Event 區「探せ」以外的卡最多 2 張回手牌
    'HV-P03-080': [EV(['draw'], ecost=[dict(type='guts_each', zones=['receive', 'toss', 'attack'], n=2)],
                      effects=[dict(type='evz_to_hand_n', n=2, exclude_name='探せ')])],
    # …これで スタートラインだ…!! P04-082（攻擊階段，ターン1）：舉球影山、攻擊日向 → 一人攻擊 +1；下個對手回合對手 LOSS 時，棄牌區的影山成舉球區 Guts、日向回手牌
    'HV-P04-082': [EV(['attack'], once_per_turn=True,
                      conditions=[dict(type='self_role_name', role='toss', name='影山 飛雄'), dict(type='self_role_name', role='attack', name='日向 翔陽')],
                      effects=[S('atk', 1, dict(who='self', count=1)),
                               dict(type='restrict_opp', who='opp', rule='on_loss_fetch', duration=TO)])],
    # 戦術的ワンポイントツーセッター!!! P04-083（舉球階段）：舉球角色是影山 → 舉球角色回手牌，手牌的菅原登場到舉球區，舉球變 3
    # 【策略：手牌有菅原且目前舉球 <3 才打】
    'HV-P04-083': [EV(['toss'], toss_use=True, conditions=[dict(type='self_role_name', role='toss', name='影山 飛雄')],
                      use_if=[dict(type='hand_has_char', filter=dict(name='菅原 孝支')), dict(type='toss_below', n=3)],
                      effects=[dict(type='swap_toss', name='菅原 孝支', value=3)])],
}
