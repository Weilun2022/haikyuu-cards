"""混校研究 結構化第 7 批：手牌技（從手牌丟棄／放進 Event 區）、ボール拾い、結束攔網階段、側邊攔網特召、バックアタック（手牌）19 張。預設關閉（DH_BATCH7=1 啟用）。
手牌技：timing='hand_skill'，phases=可用階段，self_cost='drop'（丟棄這張）／'evz'（放進 Event 區）／'none'（留在手牌），once=ターン1（以卡名計）。"""
TO = 'next_opp_turn'
G = lambda n: [dict(type='guts', n=n)]
S = lambda stat, n, tg='this': dict(type='stat_add', target=tg, stat=stat, n=n)
ON = lambda zones, **kw: dict(timing='on_enter', zones=zones, **kw)
HS = lambda phases, **kw: dict(timing='hand_skill', phases=phases, **kw)
DRAW = lambda n=1: dict(type='draw', who='self', n=n)
RB = dict(type='receive_below_op')
SHORT = dict(type='block_short')
PYOUTH = dict(type='all_own_chars_affil', affil='疑似ユース')
OP8 = dict(type='opp_op_ge', n=8, of='any')

NAME_CHOICE_BATCH7 = {}
MANUAL_BATCH7 = {
    # ══ 接球階段：丟棄這張，加接球 ══
    # 芝山 P01-031：音駒角色接球 +2【策略：接不住才丟】
    'HV-P01-031': [HS(['receive'], use_if=[RB], effects=[S('rcv', 2, dict(school='音駒'))])],
    # 五色 P03-011：全是白鳥沢或全是疑似ユース、Event 區 ≥4 張 → 這張登場到接球區、接球 +4【策略：接不住才用】
    'HV-P03-011': [HS(['receive'], conditions=[dict(type='any_of', conds=[dict(type='all_own_chars_school', school='白鳥沢'), PYOUTH]),
                                                dict(type='evz_total_ge', n=4)], use_if=[RB],
                      effects=[dict(type='hand_card_enter', zone='receive', then=[S('rcv', 4)])])],
    # 日向 P04-072：疑似ユース角色接球 +2，棄牌區「日向以外」的疑似ユース角色 1 張放牌庫下【策略：接不住才用】
    'HV-P04-072': [HS(['receive'], use_if=[RB], effects=[
        S('rcv', 2, dict(affil='疑似ユース')),
        dict(type='deck_bottom_from_drop', filter=dict(affil='疑似ユース', exclude_name='日向 翔陽'))])],

    # ══ 攔網／接球階段：成田 ══
    # 成田 P02-011：烏野角色的一個參數 +1。【攔網階段：規劃攔網組合時當作 +1 攔網補強；接球階段：接不住才用】
    'HV-P02-011': [HS(['block'], blk_boost=1, use_if=[SHORT], effects=[S('any_phase', 1, dict(school='烏野'))]),
                   HS(['receive'], use_if=[RB], effects=[S('any_phase', 1, dict(school='烏野'))])],

    # ══ 攔網階段：伊達工業 ══
    # 作並 P02-041：牌庫頂 3 張丟棄，全是伊達工業 → 棄牌區無技能的伊達工業角色 1 張側邊攔網登場【策略：攔網不夠才用；牌庫不足 3 張視為不成立】
    'HV-P02-041': [HS(['block'], use_if=[SHORT, dict(type='side_slot_free', name='-')], effects=[
        dict(type='mill_all_then', n=3, school='伊達工業', then=[
            dict(type='side_summon_drop', filters=[dict(category='CHARACTER', school='伊達工業', no_skill=True)])])])],
    # 茂庭 PR-045：牌庫頂 2 張丟棄，全是伊達工業 → 伊達工業角色 1 人攔網 +2【策略：攔網不夠才用】
    'HV-PR-045': [HS(['block'], use_if=[SHORT], effects=[
        dict(type='mill_all_then', n=2, school='伊達工業', then=[S('blk', 2, dict(school='伊達工業'))])])],

    # ══ 登場技（攔網）══
    # 青根 P02-037：自己手牌側邊攔網登場時，這張放牌庫下，棄牌區的「青根」側邊攔網登場、攔網變 3【策略：攔網不夠、棄牌區有青根才用】
    'HV-P02-037': [ON(['block'], conditions=[dict(type='is_side_blocker'), dict(type='entered_from_hand'),
                                              dict(type='drop_has_char', filter=dict(name='青根 高伸'))], use_if=[SHORT],
                      effects=[dict(type='side_self_to_bottom'),
                               dict(type='side_summon_drop', filters=[dict(name='青根 高伸')], set_blk=3)])],
    # 茂庭 P04-058：攔網區沒有側邊攔網、手牌丟伊達工業 2 張 → 棄牌區的鎌先、笹谷各 1 張側邊攔網登場【策略：攔網不夠才用】
    'HV-P04-058': [ON(['block'], conditions=[dict(type='no_side_blockers')], auto_cost=True, use_if=[SHORT],
                      cost=[dict(type='discard_hand_filtered', n=2, filter=dict(school='伊達工業'))],
                      effects=[dict(type='side_summon_drop', filters=[dict(name='鎌先 靖志'), dict(name='笹谷 武仁')], by='茂庭 要')])],
    # 鎌先 P04-057：被茂庭叫出時，付 3 Guts（全是伊達工業）且攔網區有茂庭與笹谷 → 本回合攔網成功時ドシャット(8)
    'HV-P04-057': [ON(['block'], conditions=[dict(type='entered_by', card_name='茂庭 要')], cost=G(3),
                      effects=[dict(type='keyword', name='ドシャット', n=8,
                                    **{'if': [dict(type='paid_guts_all_school', school='伊達工業'),
                                              dict(type='block_has_names', names=['茂庭 要', '笹谷 武仁'])]})])],

    # ══ 登場技（結束攔網階段）══
    # 松川 P01-037：對手進攻 ≥8、付 1 Guts → 結束攔網階段（直接進自己的抽牌階段），本回合青葉城西接球角色登場 +3
    'HV-P01-037': [ON(['block'], conditions=[OP8], cost=G(1), effects=[
        dict(type='end_block'), dict(type='aura_turn', aura=dict(on='receive_enter', school='青葉城西', n=3))])],
    # 千鹿谷 P03-030：全場ユース、對手進攻 ≥8 → 結束攔網階段，本回合接球角色登場 +2
    'HV-P03-030': [ON(['block'], conditions=[dict(type='all_own_chars_affil', affil='ユース'), OP8], effects=[
        dict(type='end_block'), dict(type='aura_turn', aura=dict(on='receive_enter', n=2))])],

    # ══ ボール拾い（攻擊階段，放進 Event 區，ターン1）══
    # 日向 P03-001：全場疑似ユース → 抽 1；Event 區 ≥6 張（含剛放進去的這張）改成從棄牌區撿角色 1 張
    'HV-P03-001': [HS(['attack'], self_cost='evz', once=True, conditions=[PYOUTH], effects=[dict(type='draw_or_fetch', evz_ge=6)])],
    # 寒河江 P03-013：全場疑似ユース → 公開牌庫頂 2 張，其中角色 1 張進手牌，其餘放牌庫下
    'HV-P03-013': [HS(['attack'], self_cost='evz', once=True, conditions=[PYOUTH], effects=[dict(type='reveal_take', n=2, mode='char')])],
    # 赤倉 P03-014：全場疑似ユース → 公開牌庫頂 3 張，其中事件全部進手牌，其餘放牌庫下
    'HV-P03-014': [HS(['attack'], self_cost='evz', once=True, conditions=[PYOUTH], effects=[dict(type='reveal_take', n=3, mode='events')])],
    # 五色 P04-074：手牌的ボール拾い 1 張放進 Event 區 → 抽 1，這個角色一個參數 +2（發球區或攻擊區登場）
    'HV-P04-074': [ON(['serve', 'attack'], cost=[dict(type='hand_pos_to_evz', pos='ボール拾い')], effects=[DRAW(1), S('any', 2)])],

    # ══ 其他手牌技 ══
    # 田代 P03-056（攻擊階段、ターン1）：棄牌區烏野 3 年角色 1 張回手牌
    'HV-P03-056': [HS(['attack'], once=True, conditions=[dict(type='drop_has_char', filter=dict(school='烏野', grade=3))],
                      effects=[dict(type='drop_to_hand', who='self', filter=dict(school='烏野', grade=3, category='CHARACTER'), max=1)])],
    # 黒川 P03-057（抽牌階段）：本回合烏野 2、3 年角色登場到接球區，接球 +2，且不被減值【策略：手牌有烏野 2、3 年角色、且對手進攻 ≥2 才用】
    'HV-P03-057': [HS(['draw'], conditions=[dict(type='hand_has_char', filter=dict(school='烏野', grades=[2, 3])), dict(type='opp_op_ge', n=2, of='any')],
                      effects=[dict(type='aura_turn', aura=dict(on='receive_enter', school='烏野', grades=[2, 3], n=2, protect=True))])],
    # 温田 P04-031（抽牌階段、ターン1）：對手 Event 區可在〔ブロック／ドロー／レシーブ〕打的卡合計 ≥5 → 自己 Event 區青葉城西卡 1 張回手牌
    'HV-P04-031': [HS(['draw'], once=True, conditions=[dict(type='opp_evz_phase_ge', phases=['block', 'draw', 'receive'], n=5)],
                      effects=[dict(type='event_to_hand', who='self', filter=dict(school='青葉城西'))])],
    # 山本 PR-082（攻擊階段，留在手牌）：攻擊區付 3 Guts，攻擊角色是音駒且原本攻擊 3 → 山本自己バックアタック(5)【策略：目前攻擊 <5 才用】
    'HV-PR-082': [HS(['attack'], self_cost='none', cost=[dict(type='guts', n=3, zone='attack')],
                     conditions=[dict(type='attack_top_base', school='音駒', atk=3)], use_if=[dict(type='attack_below', n=5)],
                     effects=[dict(type='back_attack', n=5, src='hand')])],
}
