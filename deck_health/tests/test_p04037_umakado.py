# 2026-10-27 馬門 P04-037：
# 1. 攔網時一觸的路線也要能付「棄 1 張角川手牌」的代價（原本策略只在攻擊階段付手牌代價 → 037 永遠不發動）
# 2. 發動後「本回合自己的接球區不能登場百沢 雄大」（原本沒模擬 → 同回合還能打 P03-016 接球 combo）
import os, sys, random
for k in ('DH_BATCH5', 'DH_BATCH6', 'DH_BATCH7', 'DH_BATCH8'): os.environ[k] = '1'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim2
U = sim2.load_cards(os.path.join(os.path.dirname(HERE), 'cards_data.js'))
C = lambda no: sim2.Card(U[no])
fails = []
def ok(name, v):
    print(('OK   ' if v else 'FAIL ') + name)
    if not v: fails.append(name)
rng = random.Random(7)
FILL = 'HV-P04-033'  # 角川百沢（無技能）
opp = sim2.Player([C('HV-P01-050')] * 20, rng, 'O')

def player(hand, drop=()):
    P = sim2.Player([C(FILL)] * 20, rng, 'A')
    P.hand = [C(x) for x in hand]; P.drop = [C(x) for x in drop]
    for z in ('block', 'receive', 'toss', 'attack'): P.zones[z] = [C(FILL)]
    return P

# 1. 單獨中間攔網、允許付代價：棄 1 張角川手牌，從棄牌區撿回百沢，一觸 2，並鎖住接球區的百沢
P = player(['HV-P04-035', 'HV-P04-036'], drop=['HV-P04-032'])
T = sim2.newT(opp, 8, 'attack'); T['phase'] = 'block'; T['allow_discard_cost'] = True
sim2.enter(P, T, 'block', C('HV-P04-037'), True)
ok('037 一觸 2', T.get('onetouch') == 2)
ok('從棄牌區撿回 P04-032', any(c.no == 'HV-P04-032' for c in P.hand))
ok('手牌棄掉 1 張角川（手牌 2→1 再撿回 1 → 2）', len(P.hand) == 2)
ok('本回合 P03-016 不能登場到接球區', not sim2.can_enter(P, 'receive', C('HV-P03-016')))
ok('本回合 P04-033（同名百沢）也不能登場到接球區', not sim2.can_enter(P, 'receive', C('HV-P04-033')))
ok('其他角色照常能登場到接球區', sim2.can_enter(P, 'receive', C('HV-P04-036')))
ok('百沢仍能登場到攻擊區', sim2.can_enter(P, 'attack', C('HV-P04-032')))

# 2. 整回合決策：攔不住、一般接球也接不住（R6 < 8），只有 037 一觸後 R6 ≥ 8−2 才活得下來
P = player(['HV-P04-037', 'HV-P04-036', 'HV-P04-034', 'HV-P04-035', 'HV-P04-033'])
r = sim2.take_turn(P, opp, 8, 'attack')
ok('只有一觸能活時會用 037（結果 %s）' % (r[0] if r[0] == 'loss' else r[6]), r[0] == 'ok' and r[6] == 'onetouch')
if r[0] == 'ok':
    ok('037 技能有記錄', r[1].stats.get('技能:HV-P04-037', 0) == 1)
    ok('回合結束後限制清空，不帶到下一回合', r[1].restrict == [])

# 3. 鎖住時接球路線不能走 P03-016 combo（對照組：沒鎖時會走）
def combo_fired(best): return best is not None and best[1].stats.get('觸發:HV-P03-016', 0) > 0
hand = ['HV-P03-016', 'HV-P04-034', 'HV-P04-035', 'HV-P04-033']
best = sim2.receive_best(player(hand), opp, 1, 'attack')
ok('對照：沒鎖時會打 P03-016 combo', combo_fired(best))
P = player(hand); P.restrict = [dict(rule='cannot_enter_name', role='receive', name='百沢 雄大')]
best = sim2.receive_best(P, opp, 1, 'attack')
ok('鎖住時不會打 P03-016 combo', best is not None and not combo_fired(best))

# 4. 雙名卡 P03-077「日向・百沢」：被鎖時仍可登場接球，但名字只能選「日向 翔陽」
LOCK = [dict(rule='cannot_enter_name', role='receive', name='百沢 雄大')]
P = player([]); P.restrict = LOCK
ok('P03-077 被鎖時仍能登場接球區（可改叫日向）', sim2.can_enter(P, 'receive', C('HV-P03-077')))
ok('被鎖時接球手名字不會選百沢', sim2.line_names(C('HV-P03-077'), C('HV-P04-034'), C('HV-P04-035'), ban_receive={'百沢 雄大'})[0] == '日向 翔陽')
ok('沒鎖時照舊可選百沢', '百沢 雄大' in [sim2.line_names(C('HV-P03-077'), C('HV-P04-034'), None)[0], *C('HV-P03-077').alts])
P = player(['HV-P03-077', 'HV-P04-034', 'HV-P04-035']); P.restrict = LOCK
T = sim2.newT(opp, 1, 'attack')
sim2.do_receive_line(P, T, P.hand[0], P.hand[1], P.hand[2], False)
ok('整條接球路線：P03-077 以日向登場（實際 %s）' % T['names'].get('receive'), T['names'].get('receive') == '日向 翔陽')

print('FAILS:', fails)
def test_all(): assert not fails, fails  # pytest 收集時用（原本模組層級 sys.exit 會讓 pytest INTERNALERROR）
if __name__ == '__main__': sys.exit(1 if fails else 0)
