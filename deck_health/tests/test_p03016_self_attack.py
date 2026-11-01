# 2026-10-26 P03-016 漏洞：百沢接球→古牧舉球付 1 Guts 回手牌→同一張 P03-016 攻擊
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
rng = random.Random(5)
def board():
    FILL = 'HV-P04-033'  # 角川百沢（無技能）當 Guts，全員角川條件才成立
    Pd = sim2.Player([C(FILL)] * 20, rng, 'X'); o = sim2.Player([C('HV-P01-050')] * 20, rng, 'O')
    Pd.hand = [C('HV-P03-016'), C('HV-P04-034'), C('HV-D01-011')]
    Pd.zones['receive'] = [C(FILL)]; Pd.zones['toss'] = [C(FILL), C(FILL)]
    return Pd, o
Pd, o = board()
best = sim2.receive_best(Pd, o, 4, 'attack')
ok('P03-016 接球＋古牧舉球＋同一張回手牌攻擊：接得住', best is not None)
if best: ok('送出 8 點（實際 %s）' % best[2], best[2] == 8)
# 對照：沒有古牧（舉球位無法觸發回手）時不能憑空自己攻擊
Pd, o = board(); Pd.hand = [C('HV-P03-016'), C('HV-P04-033'), C('HV-D01-011')]
best = sim2.receive_best(Pd, o, 4, 'attack')
ok('換成無技能舉球手時不會誤用自攻路線（結果 %s）' % (best and best[2]), best is None or best[2] != 8)
print('FAILS:', fails)
def test_all(): assert not fails, fails  # pytest 收集時用（原本模組層級 sys.exit 會讓 pytest INTERNALERROR）
if __name__ == '__main__': sys.exit(1 if fails else 0)
