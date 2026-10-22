"""混校研究 結構化第 6 批：觸發型技能（「○○登場時／被疊上時／事件被打出時」才發動）23 張。預設關閉（DH_BATCH6=1 啟用），等使用者驗收。
引擎機制見 sim2.py「第 6～8 批通用機制」：timing='when'；ev = enter（別的角色登場）／enter_on_top（有角色疊在這張上面）／event_play（事件被打出）。
holder = 這張卡所在的區域；ezones = 登場區域；ef = 對登場者的限制（school／name／base_atk／from_hand…）。"""
TO = 'next_opp_turn'
G = lambda n: [dict(type='guts', n=n)]
S = lambda stat, n, tg='this': dict(type='stat_add', target=tg, stat=stat, n=n)
W = lambda ev, holder, ezones, **kw: dict(timing='when', ev=ev, holder=holder, ezones=ezones, **kw)
DRAW = lambda n=1: dict(type='draw', who='self', n=n)
ALLOW = dict(type='allow_discard')
SHORT = dict(type='block_short')
BELOW = lambda n: dict(type='attack_below', n=n)
SIDE = dict(type='holder_move', to='block', side=True)

NAME_CHOICE_BATCH6 = {}
MANUAL_BATCH6 = {
    # ══ 音駒 ══
    # 灰羽 D02-004：自己的攔網角色登場時，若這張在攻擊區，付 2 Guts 就側邊攔網登場。【策略：攔網值不夠才用（會離開攻擊區）；規劃攔網組合時把它的攔網值當作額外加成】
    'HV-D02-004': [W('enter', 'attack', ['block'], ef={}, blk_bonus=True, cost=G(2), use_if=[SHORT], effects=[SIDE])],
    # 研磨 P01-019：原本攻擊值 3 的攻擊角色登場 → 付 2 Guts，攻擊區的音駒 Guts 1 張登場、攻擊 +2
    'HV-P01-019': [W('enter', 'toss', ['attack'], ef=dict(base_atk=3), cost=G(2),
                     use_if=[dict(type='guts_pull_better', **{'from': ['attack']}, filter=dict(school='音駒'), to='attack', add=2)],
                     effects=[dict(type='summon_from_guts', **{'from': ['attack']}, filter=dict(school='音駒'), to='attack', add=2, by='研磨P01-019',
                                   then=[S('atk', 2)])])],
    # 夜久 P01-023：接球角色上疊了「夜久以外」的音駒角色 → 把夜久丟棄，那個角色接球 +2【策略：接不住才用】
    'HV-P01-023': [W('enter_on_top', 'receive', ['receive'], ef=dict(school='音駒', not_name='夜久 衛輔'),
                     cost=[dict(type='drop_holder')], use_if=[dict(type='receive_below_op')], effects=[S('rcv', 2)])],
    # 山本 P01-028：攻擊角色上疊了「灰羽 リエーフ」→ 手牌丟 1 張音駒，那個角色攻擊 +1
    'HV-P01-028': [W('enter_on_top', 'attack', ['attack'], ef=dict(name='灰羽 リエーフ'),
                     cost=[dict(type='discard_hand_filtered', n=1, filter=dict(school='音駒'))], use_if=[ALLOW], effects=[S('atk', 1)])],
    # 芝山 PR-023：攻擊區登場「灰羽 リエーフ」→ 付 2 Guts，那個角色攻擊 +1
    'HV-PR-023': [W('enter', 'receive', ['attack'], ef=dict(name='灰羽 リエーフ'), cost=G(2), effects=[S('atk', 1, 'entered')])],
    # 黒尾 P03-033：音駒的攻擊角色登場 → 付 1 Guts，這張バックアタック(4)【策略：比目前的攻擊值高才用】
    'HV-P03-033': [W('enter', 'serve', ['attack'], ef=dict(school='音駒'), cost=G(1), use_if=[BELOW(4)],
                     effects=[dict(type='back_attack', n=4)])],
    # 海 P04-056：攻擊區登場「黒尾 鉄朗」→ 付 2 Guts，抽 2、手牌 1 張放牌庫下、舉球 +1
    'HV-P04-056': [W('enter', 'toss', ['attack'], ef=dict(name='黒尾 鉄朗'), cost=G(2),
                     effects=[DRAW(2), dict(type='hand_to_deck_bottom', n=1), S('tos', 1)])],

    # ══ 烏野 ══
    # 田中 P02-007：自己的「超インナークロス!!!」被打出 → 付 3 Guts，攻擊 +4，下個對手回合對手接球角色登場 −2
    'HV-P02-007': [W('event_play', 'attack', [], ename='超インナークロス!!!', cost=G(3),
                     effects=[S('atk', 4), dict(type='restrict_opp', who='opp', rule='opp_rcv_add', n=-2, duration=TO)])],
    # 木下 P02-010：自己的接球區登場「西谷 夕」→ 把這張丟棄，西谷接球 +1【策略：接不住才用】
    'HV-P02-010': [W('enter', 'serve', ['receive'], ef=dict(name='西谷 夕'), cost=[dict(type='drop_holder')],
                     use_if=[dict(type='receive_below_op')], effects=[S('rcv', 1, 'entered')])],
    # 影山(P03-020)：原本攻擊 3 的攻擊角色登場，這張在接球區 → Event 區丟 1 張ユース，バックアタック(4)
    'HV-P03-020': [W('enter', 'receive', ['attack'], ef=dict(base_atk=3), cost=[dict(type='evz_drop', n=1, affil='ユース')],
                     use_if=[BELOW(4)], effects=[dict(type='back_attack', n=4), dict(type='no_stat_minus')])],
    # 影山 P04-002：手牌登場「日向 翔陽」到攻擊區 → 舉球區與攻擊區各付 2 Guts，抽 1，棄牌區的日向 1 張登場、攻擊 +2
    'HV-P04-002': [W('enter', 'toss', ['attack'], ef=dict(name='日向 翔陽', from_hand=True),
                     cost=[dict(type='guts_each', zones=['toss', 'attack'], n=2)],
                     effects=[DRAW(1), dict(type='drop_to_zone', zone='attack', name='日向 翔陽', by='影山 飛雄', then=S('atk', 2))])],
    # 菅原 P04-011：手牌登場非Li的烏野攻擊角色，Event 區 ≤5 張 → 同時多發位置差攻擊〈烏野〉(3)
    'HV-P04-011': [W('enter', 'toss', ['attack'], ef=dict(school='烏野', not_li=True, from_hand=True),
                     conditions=[dict(type='evz_total_le', n=5)], effects=[dict(type='synchro', school='烏野', n=3)])],

    # ══ 青葉城西 ══
    # 及川 P04-016：手牌登場原本攻擊 3 的攻擊角色，全員青葉城西 → 付 2 Guts，Guts 的岩泉 1 張登場、攻擊變 4【策略：比現在的攻擊值高才用】
    'HV-P04-016': [W('enter', 'toss', ['attack'], ef=dict(base_atk=3, from_hand=True), conditions=[dict(type='all_own_chars_school', school='青葉城西')],
                     cost=G(2), use_if=[dict(type='guts_pull_better', **{'from': 'any'}, filter=dict(name='岩泉 一'), to='attack', set_to=4)],
                     effects=[dict(type='summon_from_guts', **{'from': 'any'}, filter=dict(name='岩泉 一'), to='attack', set_to=4, by='及川P04-016',
                                   then=[dict(type='stat_set_zone', zone='attack', value=4)])])],
    # 岩泉 P04-021：疊在這張攻擊角色上的青葉城西角色，參數不會被減（對手的 研磨 D02-001 等「攻擊 −」無效）
    'HV-P04-021': [W('enter_on_top', 'attack', ['attack'], ef=dict(school='青葉城西'), protect=True, effects=[])],
    # 金田一 P04-022：手牌登場原本攻擊 3 的攻擊角色 → 手牌丟 1 張青葉城西，這張從攔網區移到攻擊區、攻擊 +3（金田一自己攻擊值 1，所以變 4）【策略：目前攻擊值 <4 才用】
    'HV-P04-022': [W('enter', 'block', ['attack'], ef=dict(base_atk=3, from_hand=True),
                     cost=[dict(type='discard_hand_filtered', n=1, filter=dict(school='青葉城西'))], use_if=[ALLOW, BELOW(4)],
                     effects=[dict(type='holder_move', to='attack', then=[S('atk', 3)])])],
    # 矢巾 P04-028：攻擊區登場「京谷 賢太郎」→ 付 2 Guts，抽 1、舉球 +2
    'HV-P04-028': [W('enter', 'toss', ['attack'], ef=dict(name='京谷 賢太郎'), cost=G(2), effects=[DRAW(1), S('tos', 2)])],

    # ══ 角川 ══
    # 百沢系：古牧 P04-034：攔網區或攻擊區登場「百沢 雄大」，全員角川 → 付 2 Guts，那個角色的參數 +2
    'HV-P04-034': [W('enter', 'toss', ['block', 'attack'], ef=dict(name='百沢 雄大'), conditions=[dict(type='all_own_chars_school', school='角川')],
                     cost=G(2), effects=[S('any', 2, 'entered')])],
    # 温川 P04-038：攔網區登場「百沢 雄大」→ 付 2 Guts，這張側邊攔網登場，百沢的攔網 +2【※百沢是中間攔網才算到 +2】
    'HV-P04-038': [W('enter', 'receive', ['block'], ef=dict(name='百沢 雄大'), cost=G(2),
                     effects=[dict(type='holder_move', to='block', side=True, then=[S('blk', 2, dict(name='百沢 雄大'))])])],
    # 百沢 P03-016：自己的舉球角色登場，全員角川或全員疑似ユース → 付 1 Guts，這張回手牌，本回合「百沢 雄大」登場攻擊 +2【※只在本拍預定的攻擊手是百沢時才用】
    'HV-P03-016': [W('enter', 'receive', ['toss'], conditions=[dict(type='any_of', conds=[
        dict(type='all_own_chars_school', school='角川'), dict(type='all_own_chars_affil', affil='疑似ユース')])],
                     cost=G(1), use_if=[dict(type='plan_attack_name', name='百沢 雄大')],
                     effects=[dict(type='holder_to_hand'), dict(type='aura_on_enter', name='百沢 雄大', n=2)])],

    # ══ 和久谷南 ══
    # 川渡 P04-048：攻擊角色上疊了「川渡以外」的和久谷南角色 → 下個對手回合，原本攔網 ≥3 的對手攔網角色每次登場，自己抽 1
    'HV-P04-048': [W('enter_on_top', 'attack', ['attack'], ef=dict(school='和久谷南', not_name='川渡 瞬己'),
                     effects=[dict(type='restrict_opp', who='opp', rule='opp_block_draw', base_ge=3, duration=TO)])],

    # ══ 稲荷崎 ══
    # 角名 P03-044：稲荷崎的攔網角色登場，這張在攻擊區 → 丟手牌 1 張，這張側邊攔網登場【策略：攔網值不夠才用】
    'HV-P03-044': [W('enter', 'attack', ['block'], ef=dict(school='稲荷崎'), blk_bonus=True, cost=[dict(type='discard_hand', n=1)],
                     use_if=[SHORT], effects=[SIDE])],
    # 侑 P03-039：【策略 never】手牌的稲荷崎事件被打出時要丟 Event 區兩張可 [=サーブ] 的稲荷崎卡換 +1，代價太大，設為不使用
    'HV-P03-039': [W('event_play', 'serve', [], ename=None, conditions=[dict(type='never')], effects=[S('srv', 1)])],

    # ══ 井闥山／ユース ══
    # 古森 P03-028：自己的ユース舉球角色登場，這張在接球區 → 接球區 Guts 的「影山 飛雄」疊到這張上面，本回合バックアタック登場的角色攻擊 +1
    # 【策略：場上有會バックアタック的角色才用；Guts 的影山接球值不低於現在的】
    'HV-P03-028': [W('enter', 'receive', ['toss'], ef=dict(affil='ユース'),
                     cost=[dict(type='guts_name_on_top', zone='receive', name='影山 飛雄', not_worse=True)],
                     use_if=[dict(type='backattack_user')], effects=[dict(type='aura_turn', aura=dict(on='backattack', n=1))])],
}
