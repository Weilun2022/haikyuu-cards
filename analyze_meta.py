#!/usr/bin/env python3
"""
バボカ!! BREAK 競技分析 CLI

使用範例:
  python analyze_meta.py --school 稲荷崎 --vs-all --n 300
  python analyze_meta.py --find-counters --vs-archetype 攻擊型
  python analyze_meta.py --full-meta --n 200 --output output/meta_report.md
  python analyze_meta.py --build-advisor --school 音駒
  python analyze_meta.py --matchup 稲荷崎 音駒 --n 500
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from battle_simulator.analysis.archetype_classifier import Archetype, classify_deck, describe_archetype
from battle_simulator.analysis.matchup_matrix import MatchupMatrix, REPRESENTATIVE_SCHOOLS, SCHOOL_ARCHETYPE_MAP
from battle_simulator.analysis.counter_analyzer import analyze_counter
from battle_simulator.report.meta_report import generate_meta_report
from battle_simulator.report.build_advisor import recommend_deck
from battle_simulator.simulation.deck_sampler import build_school_deck
from battle_simulator.simulation.monte_carlo import run_simulation

ARCHETYPE_NAMES = {a.value: a for a in Archetype}

MAJOR_SCHOOLS = ['烏野', '稲荷崎', '音駒', '青葉城西', '白鳥沢', '梟谷', '伊達工業']


def cmd_matchup(args):
    school1, school2 = args.matchup
    deck1 = build_school_deck(school1)
    deck2 = build_school_deck(school2)
    print(f"模擬 {school1} vs {school2}（N={args.n}）...")
    result = run_simulation(deck1, deck2, n=args.n, deck1_name=school1, deck2_name=school2)
    print(result.summary())

    profile1 = classify_deck(deck1, school1)
    profile2 = classify_deck(deck2, school2)
    print(f"\n{school1} 類型: {profile1.archetype.value}")
    print(f"{school2} 類型: {profile2.archetype.value}")


def cmd_vs_all(args):
    school = args.school
    deck1 = build_school_deck(school)
    profile = classify_deck(deck1, school)
    print(f"\n{school}（{profile.archetype.value}）vs 全學校")
    print(describe_archetype(profile))
    print()

    opponents = [s for s in MAJOR_SCHOOLS if s != school]
    results = []
    for opp in opponents:
        deck2 = build_school_deck(opp)
        r = run_simulation(deck1, deck2, n=args.n, deck1_name=school, deck2_name=opp)
        results.append((opp, r))
        print(f"  vs {opp:<8}: {r.p1_win_rate:.1%} 勝率（avg {r.avg_turns:.1f}回合，{r.avg_p1_score:.1f}-{r.avg_p2_score:.1f}）")

    avg_wr = sum(r.p1_win_rate for _, r in results) / len(results)
    print(f"\n  平均勝率: {avg_wr:.1%}")
    best_opp = max(results, key=lambda x: x[1].p1_win_rate)
    worst_opp = min(results, key=lambda x: x[1].p1_win_rate)
    print(f"  最佳對局: {best_opp[0]}（{best_opp[1].p1_win_rate:.1%}）")
    print(f"  最難對局: {worst_opp[0]}（{worst_opp[1].p1_win_rate:.1%}）")


def cmd_find_counters(args):
    if args.vs_archetype:
        archetype = ARCHETYPE_NAMES.get(args.vs_archetype)
        if archetype is None:
            print(f"未知類型: {args.vs_archetype}")
            print(f"可用類型: {', '.join(ARCHETYPE_NAMES.keys())}")
            return
        target_school = REPRESENTATIVE_SCHOOLS.get(archetype, '')
    elif args.school:
        target_school = args.school
        deck = build_school_deck(target_school)
        archetype = classify_deck(deck, target_school).archetype
    else:
        print("請指定 --school 或 --vs-archetype")
        return

    print(f"分析克制 {archetype.value}（{target_school}）的方法...")
    report = analyze_counter(archetype, target_school, n_sim=args.n)
    print(report.format())


def cmd_full_meta(args):
    print(f"生成完整競技環境報告（N={args.n}/對局）...")
    print("這可能需要幾分鐘...\n")
    report = generate_meta_report(n_sim=args.n)

    if args.output:
        os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"報告已儲存至: {args.output}")
    else:
        print(report)


def cmd_build_advisor(args):
    if not args.school:
        print("請指定 --school")
        return

    threats = []
    if args.threats:
        for t in args.threats:
            a = ARCHETYPE_NAMES.get(t)
            if a:
                threats.append(a)

    result = recommend_deck(
        school=args.school,
        meta_threats=threats or None,
        budget=args.budget,
    )

    if args.output:
        os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"構築建議已儲存至: {args.output}")
    else:
        print(result)


def cmd_matrix(args):
    print(f"建立對局矩陣（N={args.n}/對局）...")
    matrix = MatchupMatrix(archetypes=list(Archetype))
    matrix.build(n=args.n)

    print("\n=== 對局矩陣 ===")
    print(matrix.format_table())
    print()

    print("=== Tier 排行 ===")
    for i, (archetype, avg_wr) in enumerate(matrix.tier_ranking(), 1):
        school = REPRESENTATIVE_SCHOOLS.get(archetype, '—')
        print(f"  #{i} {archetype.value}（{school}）: {avg_wr:.1%}")


def main():
    parser = argparse.ArgumentParser(
        description="バボカ!! BREAK 競技分析系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument('--school', help='目標學校名稱（烏野/稲荷崎/音駒/青葉城西/白鳥沢/梟谷/伊達工業）')
    parser.add_argument('--n', type=int, default=300, help='模擬局數（預設300）')
    parser.add_argument('--output', '-o', help='輸出檔案路徑（.md）')
    parser.add_argument('--budget', choices=['全部', '稀有以下', '普通卡'], default='全部', help='卡牌預算限制')

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--matchup', nargs=2, metavar=('SCHOOL1', 'SCHOOL2'), help='單場對局模擬')
    mode.add_argument('--vs-all', action='store_true', help='指定學校對戰所有主流學校')
    mode.add_argument('--find-counters', action='store_true', help='分析克制指定類型的方法')
    mode.add_argument('--full-meta', action='store_true', help='生成完整競技環境報告')
    mode.add_argument('--build-advisor', action='store_true', help='牌組構築建議')
    mode.add_argument('--matrix', action='store_true', help='生成對局矩陣')

    parser.add_argument('--vs-archetype', help='克制分析的目標類型（配合 --find-counters）')
    parser.add_argument('--threats', nargs='+', help='構築時需針對的威脅類型（配合 --build-advisor）')

    args = parser.parse_args()

    if args.matchup:
        cmd_matchup(args)
    elif args.vs_all:
        if not args.school:
            parser.error("--vs-all 需要指定 --school")
        cmd_vs_all(args)
    elif args.find_counters:
        cmd_find_counters(args)
    elif args.full_meta:
        cmd_full_meta(args)
    elif args.build_advisor:
        cmd_build_advisor(args)
    elif args.matrix:
        cmd_matrix(args)


if __name__ == '__main__':
    main()
