"""格式 A（平时/周测）适配器的单元测试。"""

import pandas as pd
import pytest

from grade_analyzer.adapters.weekly import WeeklyAdapter
from grade_analyzer.config import ExamConfig


def _real_exam() -> ExamConfig:
    return ExamConfig(
        name="高一下地理限时练一",
        format="weekly",
        subject="地理",
        folder="data/input/测试样例",
        file="【教学班报告--高一下地理限时练一】所有班级学生小题得分明细.xlsx",
        semester="高一第二学期",
        full_score=100.0,
        objective_full_score=50.0,
        subjective_full_score=50.0,
    )


def test_parse_real_weekly_file():
    score, questions = WeeklyAdapter().parse(_real_exam())
    assert len(score) > 400
    assert score["student_id"].str.fullmatch(r"\d{12}").all()
    assert "name" in score.columns
    assert (
        score["objective_score"] + score["subjective_score"] - score["total_score"]
    ).abs().max() < 1e-6
    assert score["total_ratio"].notna().all()
    assert score["total_ratio"].dropna().round(5).equals(score["total_ratio"].dropna())
    assert score["objective_ratio"].dropna().round(5).equals(
        score["objective_ratio"].dropna()
    )
    assert score["subjective_ratio"].dropna().round(5).equals(
        score["subjective_ratio"].dropna()
    )
    assert len(questions) == len(score) * 29
    assert set(questions["question_type"]) == {"客观", "主观"}
    assert questions["question_id"].str.fullmatch(r"(\d+|\d+-\d+)").all()
    assert (questions[questions["question_id"] == "26-1"]["score"] > 0).any()


def test_parse_requires_name_and_subject():
    with pytest.raises(ValueError, match="名称"):
        WeeklyAdapter().parse(
            ExamConfig(format="weekly", subject="地理", file="x.xlsx")
        )
    with pytest.raises(ValueError, match="科目"):
        WeeklyAdapter().parse(
            ExamConfig(format="weekly", name="测试", file="x.xlsx")
        )


def test_parse_missing_header_raises(tmp_path):
    f = tmp_path / "bad.xlsx"
    pd.DataFrame([["a", "b"], [1, 2]]).to_excel(f, index=False, header=False)
    exam = ExamConfig(
        name="测试",
        format="weekly",
        subject="地理",
        folder=str(tmp_path),
        file="bad.xlsx",
    )
    with pytest.raises(ValueError, match="表头"):
        WeeklyAdapter().parse(exam)


def test_parse_subjective_header_variants(tmp_path):
    f = tmp_path / "variants.xlsx"
    pd.DataFrame(
        [
            ["标题"],
            ["序号", "姓名", "准考证号", "自定义考号", "班级", "总分", "客观分",
             "主观分", "单选题", "多选题", "解答题",
             "1", "2", "26", "26(1)", "26（2）", "27-1"],
            ["1", None, "123", "250907010001", "高一(1)", "84", "74", "10",
             "54", "20", "10", "3", "3", "10", "3", "3", "4"],
        ]
    ).to_excel(f, index=False, header=False)
    exam = ExamConfig(
        name="测试",
        format="weekly",
        subject="地理",
        folder=str(tmp_path),
        file="variants.xlsx",
        full_score=100.0,
        objective_full_score=85.0,
        subjective_full_score=15.0,
    )
    score, questions = WeeklyAdapter().parse(exam)
    assert len(score) == 1
    assert set(questions["question_id"]) == {"1", "2", "26-1", "26-2", "27-1"}
    assert set(questions["question_type"]) == {"客观", "主观"}
    assert "26" not in set(questions["question_id"])  # 大题汇总列已跳过
