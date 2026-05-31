"""Generate competitive meta analysis report."""
from __future__ import annotations

import datetime
from ..analysis.archetype_classifier import Archetype, classify_deck, describe_archetype
from ..analysis.matchup_matrix import MatchupMatrix, REPRESENTATIVE_SCHOOLS
from ..simulation.deck_sampler import build_school_deck
from ..simulation.monte_carlo import run_simulation

ALL_ARCHETYPES = list(Archetype)

ARCHETYPE_DESCRIPTIONS = {
    Archetype.AGG:     "高速得分，靠SRV/ATK在對手穩定前搶佔分差",
    Archetype.DEF:     "高BLK/RCV消耗對手攻擊資源，以對手失誤穩定得分",
    Archetype.COMBO:   "透過技能鏈爆發大量得分，依賴關鍵手牌組合",
    Archetype.TEMPO:   "高TOS效率與穩定資源循環，節奏型中速策略",
    Archetype.CONTROL: "技能干擾限制對手出牌，控制場面主導比賽走向",
    Archetype.HYBRID:  "全面均衡型，無明顯弱點，靈活應對不同對局",
}


def generate_meta_report(n_sim: int = 300) -> str:
    today = datetime.date.today().isoformat()
    matrix = MatchupMatrix(archetypes=ALL_ARCHETYPES)
    matrix.build(n=n_sim)

    tiers = matrix.tier_ranking()

    lines = [
        f"# バボカ!! BREAK 競技環境分析報告",
        f"生成日期: {today} | 模擬局數/對局: {n_sim}",
        "",
        "---",
        "",
        "## 一、Tier 排行",
        "",
    ]

    tier_bands = [(0.55, "Tier 1"), (0.50, "Tier 2"), (0.45, "Tier 3"), (0.0, "Tier 4")]
    current_tier = None
    for archetype, avg_wr in tiers:
        for threshold, tier_name in tier_bands:
            if avg_wr >= threshold:
                if tier_name != current_tier:
                    current_tier = tier_name
                    lines.append(f"### {tier_name}")
                break
        school = REPRESENTATIVE_SCHOOLS.get(archetype, "—")
        lines.append(
            f"- **{archetype.value}**（代表：{school}）"
            f" — 平均勝率 {avg_wr:.1%}"
        )
        lines.append(f"  {ARCHETYPE_DESCRIPTIONS.get(archetype, '')}")

    lines += [
        "",
        "---",
        "",
        "## 二、對局矩陣（橫向為進攻方，縱向為防守方）",
        "",
        "```",
        matrix.format_table(),
        "```",
        "",
        "> 數值 = 橫向類型對縱向類型的勝率；50% 以上代表橫向佔優",
        "",
        "---",
        "",
        "## 三、克制環分析",
        "",
    ]

    for archetype in ALL_ARCHETYPES:
        best_counter = matrix.best_counter(archetype)
        wr = matrix.get_win_rate(best_counter, archetype)
        lines.append(
            f"- **{archetype.value}** 的最佳剋星：**{best_counter.value}**"
            f"（勝率 {wr:.1%}）"
        )

    lines += [
        "",
        "---",
        "",
        "## 四、各類型詳細側檔",
        "",
    ]

    for archetype in ALL_ARCHETYPES:
        school = REPRESENTATIVE_SCHOOLS.get(archetype, "烏野")
        deck = build_school_deck(school)
        profile = classify_deck(deck, school)
        best_counter = matrix.best_counter(archetype)
        worst_matchup_wr = matrix.get_win_rate(archetype, best_counter)

        lines += [
            f"### {archetype.value}（代表學校：{school}）",
            "",
            describe_archetype(profile),
            "",
            f"最佳對局：{matrix.best_counter(best_counter).value} "
            f"（勝率 {matrix.get_win_rate(archetype, matrix.best_counter(best_counter)):.1%}）",
            f"最差對局：{best_counter.value} "
            f"（勝率 {worst_matchup_wr:.1%}）",
            "",
            ARCHETYPE_DESCRIPTIONS.get(archetype, ""),
            "",
        ]

    return "\n".join(lines)
