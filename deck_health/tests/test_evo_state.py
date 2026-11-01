"""演化面板快照：以 out_m1 實際紀錄的片段驗證 search.log + results.json → 面板資料。"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import evo_state

CARDS = {no: dict(img=no + '-N.webp', name=name, ev=ev) for no, name, ev in [
    ('HV-P04-063', '木兎', False), ('HV-P01-044', '木兎', False), ('HV-P04-064', '木葉', False),
    ('HV-P01-043', '木兎', False), ('HV-PR-013', '木兎・赤葦', False), ('HV-P01-045', '赤葦', False),
    ('HV-P04-066', '小見', False), ('HV-PR-047', '小見', False), ('HV-P01-090', '差別', True)]}
DECK0 = '{"HV-P04-063": 3, "HV-P04-064": 6}'
DECK1 = '{"HV-P04-063": 1, "HV-P04-064": 6, "HV-P01-044": 2}'
LOG = f'''== 禁用卡強制替換 HV-PR-013×3，候選25
複驗(含禁用卡勝率 37.9%): -3HV-PR-013+3HV-P01-045 +3.61±1.83
採用 -3HV-PR-013+3HV-P01-045（強制替換，+3.61，SE 1.83）
== 第1輪 k=2 候選271 目前牌組 {DECK0}
第一段前10: -2HV-P04-064+2HV-P01-043 +16.7  (97s)
-- 15:11 重啟（加入勝率紀錄），從第1輪牌組繼續
== 第1輪 k=2 候選271 目前牌組 {DECK0}
第一段前10: -2HV-P04-064+2HV-P01-043 +16.7  (101s)
粗篩前10: -2HV-P04-064+2HV-P01-043 +8.9  (326s)
複驗(目前勝率 38.8%): -2HV-P04-063+2HV-P01-044 +4.07±1.97 | -2HV-P04-064+2HV-P01-043 +2.96±1.74
採用 -2HV-P04-063+2HV-P01-044（+4.07，SE 1.97）
== 第2輪 k=2 候選295 目前牌組 {DECK1}
第一段前10: -2HV-P04-064+2HV-P01-043 +16.7  (114s)
粗篩前10: -2HV-P04-064+2HV-P01-043 +8.9  (331s)
複驗(目前勝率 41.0%): -2HV-P04-064+2HV-P01-043 +3.43±2.12
複驗未達 2×SE
改用單張替換
'''


def snap(log=LOG, results=()):
    return evo_state.snapshot(log, list(results), CARDS)


def test_rerun_round_replaces_the_interrupted_attempt():
    rounds = snap()['rounds']
    assert [r['round'] for r in rounds] == [1, 2]
    assert rounds[0]['funnel'] == [271, 30, 2]
    assert rounds[0]['stage_secs'] == [101, 326]


def test_round_records_rechecks_and_which_one_was_adopted():
    r1, r2 = snap()['rounds']
    first = r1['recheck'][0]
    assert first['k'] == 2 and first['out']['no'] == 'HV-P04-063' and first['in']['no'] == 'HV-P01-044'
    assert first['delta'] == pytest.approx(.0407) and first['se'] == pytest.approx(.0197)
    assert first['ratio'] == pytest.approx(4.07 / 1.97)
    assert [c['adopted'] for c in r1['recheck']] == [True, False]
    assert r2['adopted'] is None and r1['adopted'] == '-2HV-P04-063+2HV-P01-044'


def test_forced_replacement_is_kept_apart_from_rounds():
    forced = snap()['forced']
    assert forced['out']['no'] == 'HV-PR-013' and forced['in']['no'] == 'HV-P01-045'
    assert forced['k'] == 3 and forced['delta'] == pytest.approx(.0361)


D0, D1 = {'HV-P04-063': 3, 'HV-P04-064': 6}, {'HV-P04-063': 1, 'HV-P04-064': 6, 'HV-P01-044': 2}
D2 = {'HV-P04-063': 3, 'HV-P04-064': 4, 'HV-P01-043': 2}
D3 = {'HV-P04-063': 1, 'HV-P04-064': 4, 'HV-P01-044': 2, 'HV-P01-043': 2}
RESULTS = [
    dict(deck=D0, winrate=.388, n=1080, move='cur', stage='confirm', round=1, t=1000),
    dict(deck=D1, winrate=.429, n=1080, move='-2HV-P04-063+2HV-P01-044', stage='confirm', round=1, t=1000),
    dict(deck=D2, winrate=.418, n=1080, move='-2HV-P04-064+2HV-P01-043', stage='confirm', round=1, t=1000),
    dict(deck=D1, winrate=.410, n=1080, move='cur', stage='confirm', round=2, t=1458),
    dict(deck=D3, winrate=.444, n=1080, move='-2HV-P04-064+2HV-P01-043', stage='confirm', round=2, t=1458),
]


def test_round_winrate_comes_from_the_fresh_seed_recheck_of_the_current_deck():
    r1, r2 = snap(results=RESULTS)['rounds']
    assert r1['cur'] == dict(wr=.388, se=pytest.approx(.01483, abs=1e-4), n=1080)
    assert r2['cur']['wr'] == .410


def test_headline_is_the_latest_recheck_of_the_adopted_deck_not_the_selected_score():
    s = snap(results=RESULTS)
    assert s['final']['wr'] == .410
    assert s['final']['selected'] is False
    assert [x['wr'] for x in s['final']['rechecks']] == [.410]  # 挑中時的 .429 不算重驗


def test_just_adopted_deck_without_recheck_is_flagged_as_selected_score():
    log = LOG + '採用 -2HV-P04-064+2HV-P01-043（+3.43，SE 2.12）\n'
    s = snap(log, RESULTS)
    assert s['final']['wr'] == .444 and s['final']['selected'] is True


def test_empty_log_gives_empty_snapshot():
    s = snap('', [])
    assert s['rounds'] == [] and s['final'] is None and s['tops'] == [] and s['net'] == {'in': [], 'out': []}


def test_tops_show_the_adopted_deck_at_its_latest_recheck_and_label_each_deck():
    tops = snap(results=RESULTS)['tops']
    assert [(t['rank'], t['wr'], t['kind']) for t in tops] == [(1, .444, 'cand'), (2, .418, 'cand'), (3, .410, 'final')]
    assert tops[0]['why'] == '第 2 輪候選，差 0.38 個 SE 未過門檻，沒有再驗過，數字可能偏高。'
    assert tops[1]['why'] == '第 1 輪候選，差 0.30 個 SE 未過門檻，沒有再驗過，數字可能偏高。'
    assert tops[2]['why'] == '第 1 輪採用，之後重驗 41.0%±1.5。'


def test_adopted_deck_stays_in_the_top_list_when_candidates_outrank_it():
    extra = [dict(deck={'HV-P04-063': n}, winrate=.5 + n / 100, n=1080, move=f'-1X{n}', stage='confirm', round=2, t=1458) for n in (1, 2, 3)]
    tops = snap(results=RESULTS + extra)['tops']
    assert [(t['rank'], t['kind']) for t in tops] == [(1, 'cand'), (2, 'cand'), (6, 'final')]


def test_candidate_above_threshold_that_lost_its_round_says_so():
    log = LOG.replace('+2.96±1.74', '+4.00±1.74')
    assert snap(log, RESULTS)['tops'][1]['why'] == '第 1 輪候選，已過門檻（2.30 SE），但同輪輸給更高的候選。'


def test_top_deck_cards_list_characters_before_events_with_images():
    results = [dict(deck={'HV-P01-090': 8, 'HV-P04-064': 2}, winrate=.5, n=1080, move='cur', stage='confirm', round=1, t=1)]
    cs = snap(results=results)['tops'][0]['cards']
    assert [(c['no'], c['count'], c['ev']) for c in cs] == [('HV-P04-064', 2, False), ('HV-P01-090', 8, True)]
    assert cs[0]['img'] == 'HV-P04-064-N.webp'


def test_small_samples_stay_out_of_the_ranking():
    results = [dict(deck=D2, winrate=.9, n=100, move='cur', stage='confirm', round=1, t=1)]
    assert snap(results=results)['tops'] == []


def test_net_change_ignores_cards_swapped_out_and_back_in():
    log = (f'== 第1輪 k=2 候選1 目前牌組 {{"HV-P04-063": 3, "HV-P04-064": 2}}\n'
           f'== 第2輪 k=2 候選1 目前牌組 {{"HV-P04-063": 1, "HV-P04-064": 2, "HV-P01-044": 2}}\n')
    assert snap(log)['net'] == {'out': [dict(no='HV-P04-063', name='木兎', count=2)],
                                'in': [dict(no='HV-P01-044', name='木兎', count=2)]}


def test_stage_marks_where_the_current_round_is():
    assert snap(LOG.split('第一段前10')[0], [])['stage']['step'] == 0
    head = LOG[:LOG.rindex('粗篩前10')]
    assert snap(head, RESULTS)['stage']['step'] == 1
    assert snap(LOG[:LOG.rindex('複驗(')], RESULTS)['stage']['step'] == 2


def test_stage_estimate_uses_the_same_stage_of_the_previous_round():
    head = LOG[:LOG.rindex('粗篩前10')]
    assert snap(head, RESULTS)['stage']['expect_secs'] == 326 - 101
    third = LOG + f'== 第3輪 k=1 候選319 目前牌組 {DECK1}\n第一段前10: x  (110s)\n粗篩前10: x  (324s)\n'
    assert snap(third, RESULTS)['stage']['expect_secs'] == 458 - 331


def test_stage_has_no_estimate_in_the_first_round():
    head = LOG.split('== 第2輪')[0]
    assert snap(head[:head.rindex('粗篩前10')], [])['stage']['expect_secs'] is None


def test_finished_log_has_no_stage():
    assert snap(LOG + '結束 {}\n', RESULTS)['stage'] is None


def test_new_round_after_end_marker_means_the_search_is_running_again():
    s = snap(LOG + '結束 {}\n' + f'== 第3輪 k=1 候選319 目前牌組 {DECK1}\n', RESULTS)
    assert s['finished'] is False and s['stage']['round'] == 3


def test_forced_replacement_after_resume_does_not_leak_into_the_last_round():
    log = LOG + '== 禁用卡強制替換 HV-PR-013×3，候選25\n複驗(含禁用卡勝率 40.0%): -3HV-PR-013+3HV-P01-045 +1.00±1.00\n'
    assert len(snap(log)['rounds'][1]['recheck']) == 1


def test_rewinding_to_an_earlier_round_drops_the_later_rounds():
    s = snap(LOG + f'== 第1輪 k=2 候選271 目前牌組 {DECK0}\n', RESULTS)
    assert [r['round'] for r in s['rounds']] == [1] and s['stage']['round'] == 1


def test_round_winrate_uses_the_latest_attempt_of_a_rerun_round():
    again = dict(RESULTS[0], winrate=.5)
    assert snap(results=RESULTS + [again])['rounds'][0]['cur']['wr'] == .5


NO_ADOPT = LOG.replace('+3.43±2.12', '+3.43±2.12 | -2HV-P04-063+2HV-P01-044 +3.00±1.20')


def test_lower_candidate_that_passed_is_reported_when_the_top_one_failed():
    d = snap(NO_ADOPT)['decision']
    assert d['round'] == 2 and d['adopted'] is None
    assert d['passed']['ratio'] == pytest.approx(2.5)
    assert d['closest']['move'] == '-2HV-P04-064+2HV-P01-043' and d['gap'] == pytest.approx(2 - 3.43 / 2.12)


def test_passed_candidate_in_a_round_without_adoption_explains_why():
    results = RESULTS + [dict(deck={'HV-P04-063': 9}, winrate=.6, n=1080, move='-2HV-P04-063+2HV-P01-044', stage='confirm', round=2, t=1458)]
    why = snap(NO_ADOPT, results)['tops'][0]['why']
    assert why == '第 2 輪候選，已過門檻（2.50 SE），但同輪差值最高的候選沒過，所以沒採用。'


def test_decision_reports_the_adoption_when_the_last_round_adopted():
    log = LOG.split('== 第2輪')[0]
    d = snap(log)['decision']
    assert d['adopted']['move'] == '-2HV-P04-063+2HV-P01-044' and d['closest'] is None and d['gap'] is None


def test_no_positive_candidate_round_counts_as_a_decision_without_closest():
    log = f'== 第1輪 k=2 候選5 目前牌組 {DECK0}\n粗篩無正向候選\n'
    d = snap(log)['decision']
    assert d['round'] == 1 and d['adopted'] is None and d['closest'] is None
    assert snap(log)['rounds'][0]['no_candidate'] is True


def test_no_decision_before_the_first_recheck():
    assert snap(LOG.split('複驗(')[0])['decision'] is None


@pytest.mark.parametrize('s, want', [
    (dict(proc=None), 'unknown'),
    (dict(proc=dict(main=0), finished=True), 'done'),
    (dict(proc=dict(main=0), finished=False), 'dead'),
    (dict(proc=dict(main=1), finished=False, busy=.1, age=5, stage=None), 'stall'),
    (dict(proc=dict(main=1), finished=False, busy=1, age=5, stage=dict(expect_secs=200)), 'run'),
    (dict(proc=dict(main=1), finished=False, busy=1, age=601, stage=dict(expect_secs=200)), 'stall'),  # 下限 10 分
    (dict(proc=dict(main=1), finished=False, busy=1, age=901, stage=dict(expect_secs=300)), 'stall'),  # 3 倍同階段耗時
    (dict(proc=dict(main=1), finished=False, busy=1, age=899, stage=dict(expect_secs=300)), 'run'),
    (dict(proc=dict(main=1), finished=False, busy=1, age=1801, stage=dict(expect_secs=None)), 'stall'),  # 沒有耗時可參考
    (dict(proc=dict(main=1), finished=False, busy=None, age=1, stage=None), 'run'),
])
def test_verdict_tells_running_from_stalled_finished_and_dead(s, want):
    assert evo_state.verdict(s) == want


def test_only_the_search_writing_this_output_counts_as_this_run():
    assert evo_state.is_this_search(r'python -I search.py C:/x/dh start.json C:/t/out_m1', 'out_m1')
    assert not evo_state.is_this_search(r'python -I search.py C:/x/dh start.json C:/t/out_other', 'out_m1')
    assert not evo_state.is_this_search('python evo_panel.py C:/t/out_m1/search.log', 'out_m1')


WINRATE = dict(title='勝率對照', kind='log', log='w.log', proc='m1_winrate')


def test_log_step_reports_progress_and_eta_from_its_counter():
    job = evo_state.job_status(WINRATE, '1100 / 2520 1475 s\n1200 / 2520 1554 s\n', running=True, age=30)
    assert job['status'] == 'running' and (job['done'], job['total']) == (1200, 2520)
    assert job['pct'] == pytest.approx(47.6, abs=.1)
    assert job['eta_secs'] == pytest.approx(1042.8)  # 最近 100 批 79 秒，剩 1320 批


def test_log_step_eta_with_a_single_counter_line_uses_that_line():
    job = evo_state.job_status(WINRATE, '100 / 2520 129 s\n', running=True, age=30)
    assert job['eta_secs'] == pytest.approx(3121.8)  # 100 批 129 秒，剩 2420 批


def test_log_step_eta_ignores_pace_older_than_the_last_five_lines():
    rows = ['100 / 1000 1000 s', '200 / 1000 1100 s', '300 / 1000 1200 s', '400 / 1000 1300 s',
            '500 / 1000 1400 s', '600 / 1000 1500 s', '700 / 1000 1600 s']
    job = evo_state.job_status(WINRATE, '\n'.join(rows), running=True, age=30)
    assert job['eta_secs'] == pytest.approx(300)  # 最初那批的 1000 秒不算，近五段都是 100 批 100 秒


def test_log_step_is_done_after_its_done_line_even_with_no_process():
    text = '2500 / 2520 3100 s\ndone C:\\x\\winrate_2000.json 3125 s\n'
    job = evo_state.job_status(WINRATE, text, running=False, age=5)
    assert job['status'] == 'done' and job['pct'] == 100 and job['eta_secs'] == 0


def test_log_step_waits_with_its_estimate_before_it_starts():
    job = evo_state.job_status(dict(WINRATE, est=1800), None, running=False)
    assert job['status'] == 'pending' and job['pct'] is None and job['eta_secs'] == 1800


def test_empty_log_with_no_process_means_it_died_before_the_first_line():
    assert evo_state.job_status(WINRATE, '', running=False, age=60)['status'] == 'failed'


def test_started_process_with_no_progress_line_yet_is_running():
    job = evo_state.job_status(dict(WINRATE, est=1800), '', running=True, age=3)
    assert job['status'] == 'running' and job['eta_secs'] == 1800


def test_log_step_is_failed_when_process_is_gone_without_done_line():
    assert evo_state.job_status(WINRATE, '1200 / 2520 1554 s\n', running=False, age=60)['status'] == 'failed'


def test_log_step_is_unknown_when_process_list_is_unreadable():
    assert evo_state.job_status(WINRATE, '1200 / 2520 1554 s\n', running=None, age=60)['status'] == 'unknown'


def test_running_log_step_with_old_log_is_stalled():
    assert evo_state.job_status(WINRATE, '1200 / 2520 1554 s\n', running=True, age=1801)['status'] == 'stall'


BENCH = dict(title='效能量測', kind='lines', log='b.log', proc='m1_benchmark', total=3, est=300)


def test_lines_step_counts_finished_pairs():
    job = evo_state.job_status(BENCH, '{"pair": 1}\n{"pair": 2}\n', running=True, age=10)
    assert job['status'] == 'running' and (job['done'], job['total']) == (2, 3)
    assert job['pct'] == pytest.approx(66.7, abs=.1) and job['eta_secs'] == pytest.approx(100)


def test_lines_step_is_done_at_its_total():
    job = evo_state.job_status(BENCH, '{"a": 1}\n{"a": 2}\n{"a": 3}\n', running=False, age=10)
    assert job['status'] == 'done' and job['eta_secs'] == 0


def test_manual_step_keeps_the_status_written_in_the_pipeline_file():
    job = evo_state.job_status(dict(title='結果文件', kind='manual', status='pending', est=600))
    assert job['status'] == 'pending' and job['eta_secs'] == 600
    assert evo_state.job_status(dict(title='結果文件', kind='manual', status='done'))['eta_secs'] == 0


def test_running_manual_step_has_no_eta_because_nothing_counts_it_down():
    job = evo_state.job_status(dict(title='結果文件', kind='manual', status='running', est=600))
    assert job['eta_secs'] is None


@pytest.mark.parametrize('kind,status', [('run', 'running'), ('stall', 'stall'), ('done', 'done'), ('dead', 'failed'), ('unknown', 'unknown')])
def test_search_step_follows_the_search_verdict(kind, status):
    assert evo_state.job_status(dict(title='搜尋', kind='search'), '== 第1輪', search_kind=kind)['status'] == status


def test_search_step_waits_while_its_log_is_empty():
    assert evo_state.job_status(dict(title='搜尋', kind='search', est=60), '', search_kind='dead')['status'] == 'pending'


def test_pipeline_totals_remaining_time_from_known_estimates():
    done = dict(title='甲', status='done', eta_secs=0)
    run = dict(title='乙', status='running', eta_secs=1700)
    wait = dict(title='丙', status='pending', eta_secs=300)
    later = dict(title='丁', status='pending', eta_secs=None)
    p = evo_state.pipeline([done, run, wait, later], now=1000)
    assert p['kind'] == 'run' and p['current'] is run
    assert (p['done'], p['total']) == (1, 4)
    assert p['finish_at'] == 3000
    assert p['unestimated'] == ['丁']


def test_pipeline_is_waiting_when_nothing_runs_but_steps_remain():
    p = evo_state.pipeline([dict(title='甲', status='done', eta_secs=0), dict(title='乙', status='pending', eta_secs=None)], now=1)
    assert p['kind'] == 'wait' and p['current'] is None and p['finish_at'] is None


def test_pipeline_gives_no_finish_time_while_nothing_is_running():
    p = evo_state.pipeline([dict(title='甲', status='pending', eta_secs=900)], now=1)
    assert p['kind'] == 'wait' and p['finish_at'] is None


def test_pipeline_flags_a_failed_step_while_others_still_run():
    p = evo_state.pipeline([dict(title='甲', status='failed', eta_secs=None), dict(title='乙', status='running', eta_secs=10)], now=1)
    assert p['kind'] == 'dead' and p['current']['title'] == '乙'


def test_pipeline_is_done_when_every_step_is_done():
    p = evo_state.pipeline([dict(title='甲', status='done', eta_secs=0)], now=1)
    assert p['kind'] == 'done' and p['finish_at'] is None


def test_pipeline_is_absent_without_a_pipeline_file():
    assert evo_state.pipeline([], now=1) is None


def test_adoption_picks_the_highest_candidate_that_passes_the_threshold():
    ranked = [(.0407, .0204, '最高但沒過'), (.0287, .0115, '第二名有過'), (.0204, .0198, '沒過')]
    assert evo_state.adoption(ranked)[2] == '第二名有過'


def test_adoption_keeps_the_top_candidate_when_it_passes():
    assert evo_state.adoption([(.05, .02, '甲'), (.03, .01, '乙')])[2] == '甲'


def test_adoption_is_none_when_nothing_passes():
    assert evo_state.adoption([(.02, .02, '甲'), (-.01, .01, '乙')]) is None


def test_pipeline_gives_no_finish_time_while_the_current_step_has_no_estimate():
    p = evo_state.pipeline([dict(title='搜尋', status='running', eta_secs=None), dict(title='複驗', status='pending', eta_secs=300)], now=1)
    assert p['current']['title'] == '搜尋' and p['finish_at'] is None and p['unestimated'] == ['搜尋']


def test_holdout_summary_reads_the_final_deck_result():
    verify = dict(weighted=dict(base=.5488, final=.5673), diffs=dict(final=dict(diff=.0185, se=.0048)))
    assert evo_state.holdout_summary(verify) == dict(wr=.5673, diff=.0185, se=.0048)


def test_holdout_summary_is_none_before_verification():
    assert evo_state.holdout_summary(None) is None


SEARCH = dict(title='演化搜尋', kind='search')
ROUND2 = dict(round=2, k=1, stage=1, done=1200, total=2400, secs=600)


def test_round_progress_adds_finished_stages_and_planned_later_stages():
    p = evo_state.round_progress(3, 2, 1, 200, 400, [1000, 400, 900], 100.0, 160.0)
    assert (p['round'], p['k'], p['stage']) == (3, 2, 1)
    assert (p['done'], p['total'], p['secs']) == (1200, 2300, 60.0)


def test_round_progress_uses_the_real_size_of_a_shorter_stage():
    assert evo_state.round_progress(1, 2, 2, 0, 300, [1000, 400, 900], 0, 1)['total'] == 1700


def test_running_search_shows_how_far_this_round_is():
    job = evo_state.job_status(SEARCH, 'log', age=3, search_kind='run', progress=ROUND2)
    assert job['pct'] == 50 and (job['done'], job['total']) == (1200, 2400)
    assert job['label'] == '第 2 輪 · 粗篩' and job['round_eta'] == 600


def test_round_progress_stays_out_of_the_whole_flow_finish_time():
    assert evo_state.job_status(SEARCH, 'log', age=3, search_kind='run', progress=ROUND2)['eta_secs'] is None  # 總輪數未定


def test_search_without_progress_file_has_no_percentage():
    assert evo_state.job_status(SEARCH, 'log', age=3, search_kind='run')['pct'] is None


def test_finished_search_is_complete_whatever_the_last_progress_said():
    assert evo_state.job_status(SEARCH, 'log', age=3, search_kind='done', progress=ROUND2)['pct'] == 100
