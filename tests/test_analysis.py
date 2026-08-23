"""分析层计算的单元测试。"""

import pandas as pd

from grade_analyzer.analysis import (
    compute_average_rankings,
    compute_distribution,
    compute_group_comparison,
    compute_rankings,
    compute_subject_stats,
    compute_trends,
)
from grade_analyzer.config import AnalysisConfig


def _long_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "exam_name": ["期中", "期中", "期中", "期末", "期末", "期末"],
            "exam_date": ["2026-04-20"] * 3 + ["2026-06-20"] * 3,
            "subject": ["地理"] * 6,
            "student_id": ["S1", "S2", "S3"] * 2,
            "class_name": ["高一10班", "高一10班", "高一11班"] * 2,
            "class_level": ["A", "A", "B"] * 2,
            "school": ["示例一中"] * 6,
            "total_score": [70.0, 90.0, 50.0, 75.0, 95.0, 45.0],
            "total_ratio": [0.7, 0.9, 0.5, 0.75, 0.95, 0.45],
            "班次": [2, 1, 1, 2, 1, 1],
            "校次": [2, 1, 3, 2, 1, 3],
            "teacher": ["柯"] * 6,
        }
    )


def _config() -> AnalysisConfig:
    return AnalysisConfig(pass_ratio=0.6, excellent_ratio=0.85)


def test_subject_stats():
    stats = compute_subject_stats(_long_df(), _config())
    row = stats.iloc[0]
    assert row["考生数"] == 3
    assert row["平均分"] == 70.0
    assert row["最高分"] == 90.0
    assert row["最低分"] == 50.0
    assert abs(row["及格率"] - round(2 / 3, 5)) < 1e-9
    assert abs(row["优秀率"] - round(1 / 3, 5)) < 1e-9


def test_score_values_not_rounded():
    df = _long_df().copy()
    df["total_score"] = [70.34, 90.82, 50.71, 75.33, 95.81, 45.72]
    stats = compute_subject_stats(df, _config())
    row = stats.iloc[0]
    assert abs(row["平均分"] - (70.34 + 90.82 + 50.71) / 3) < 1e-9
    assert row["最高分"] == 90.82
    assert row["最低分"] == 50.71


def test_distribution_band_boundaries():
    dist = compute_distribution(_long_df(), _config())
    bands = dist[dist["考试名称"] == "期中"].set_index("分数段")["人数"].to_dict()
    assert bands["90+"] == 1
    assert bands["70-79"] == 1
    assert bands["50-59"] == 1  # 0.5 落入 50-59，不再并入 <60
    assert bands["<50"] == 0


def test_distribution_order_and_bottom_rule():
    ratios = [0.95, 0.85, 0.75, 0.65, 0.55, 0.45, 0.35, 0.25, 0.15, 0.05] * 3
    df = pd.DataFrame(
        {
            "exam_name": ["期中"] * 30,
            "subject": ["地理"] * 30,
            "total_ratio": ratios,
        }
    )
    dist = compute_distribution(df, _config())
    labels = dist[dist["考试名称"] == "期中"]["分数段"].tolist()
    assert labels == [
        "90+", "80-89", "70-79", "60-69",
        "50-59", "40-49", "30-39", "20-29", "10-19", "0-9",
    ]  # 降序且细分到底
    assert dist[dist["分数段"] == "0-9"]["占比"].iloc[0] == 0.1
    by_band = dist.set_index("分数段")
    assert by_band.loc["90+", "正向累计占比"] == 0.1
    assert by_band.loc["80-89", "正向累计占比"] == 0.2
    assert by_band.loc["0-9", "正向累计占比"] == 1.0
    assert by_band.loc["90+", "逆向累计占比"] == 1.0
    assert by_band.loc["0-9", "逆向累计占比"] == 0.1


def test_distribution_bottom_merges_when_small():
    ratios = [0.55] * 2 + [0.45] * 8 + [0.35] * 20
    df = pd.DataFrame(
        {
            "exam_name": ["期中"] * 30,
            "subject": ["地理"] * 30,
            "total_ratio": ratios,
        }
    )
    dist = compute_distribution(df, _config())
    labels = dist["分数段"].tolist()
    assert labels[-1] == "<30"  # 0-19 合计为 0，占比 0 < 0.1
    assert dist[dist["分数段"] == "50-59"]["人数"].iloc[0] == 2
    assert dist[dist["分数段"] == "40-49"]["人数"].iloc[0] == 8
    by_band = dist.set_index("分数段")
    assert by_band.loc["30-39", "正向累计占比"] == 1.0
    assert by_band.loc["50-59", "逆向累计占比"] == 1.0
    assert by_band.loc["<30", "逆向累计占比"] == 0.0


def test_rankings_single_exam():
    score = _long_df()[_long_df()["exam_name"] == "期中"]
    ranked = compute_rankings(score)
    assert ranked["总分"].iloc[0] == 90.0
    assert ranked["考号"].iloc[0] == "S2"


def test_average_rankings():
    avg = compute_average_rankings(_long_df())
    by_id = avg.set_index("考号")
    assert by_id.loc["S2", "平均得分率"] == 0.925
    assert by_id.loc["S1", "平均得分率"] == 0.725
    assert by_id.loc["S3", "平均得分率"] == 0.475
    assert by_id.loc["S2", "参考场次"] == 2


def test_group_comparison_within_level_rank():
    comp = compute_group_comparison(
        _long_df(), ["class_level", "class_name"], _config()
    )
    mid = comp[(comp["考试名称"] == "期中") & (comp["学情层次"] == "A")]
    assert len(mid) == 1  # 只有高一10班是 A 层
    assert mid.iloc[0]["组内排名"] == 1
    assert mid.iloc[0]["考生数"] == 2


def test_group_comparison_sorted_by_rank():
    df = _long_df().copy()
    df["class_name"] = ["高一10班", "高一10班", "高一11班", "高一12班", "高一10班", "高一11班"]
    df["class_level"] = ["A", "A", "A", "A", "A", "A"]
    comp = compute_group_comparison(
        df, ["class_level", "class_name"], _config()
    )
    mid = comp[comp["考试名称"] == "期中"]
    assert list(mid["组内排名"]) == sorted(mid["组内排名"])
    assert mid["组内排名"].iloc[0] == 1


def test_trends_and_progress():
    trends, progress = compute_trends(_long_df(), _config())
    assert len(trends) == 2
    assert trends.iloc[0]["考试名称"] == "期中"
    assert progress["状态"].value_counts().to_dict() == {
        "进步": 2,
        "退步": 1,
    }
    s1 = progress[progress["考号"] == "S1"].iloc[0]
    assert abs(s1["得分率变化"] - 0.05) < 1e-9
