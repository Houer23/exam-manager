"""格式 B（联考）适配器的单元测试。"""

import pandas as pd
import pytest

from grade_analyzer.adapters.joint import JointAdapter
from grade_analyzer.config import ExamConfig


def _real_exam() -> ExamConfig:
    return ExamConfig(
        name="高一下期中联考",
        format="joint",
        subject="地理",
        folder="data/input/测试样例",
        file="地理原始数据.xlsx",
        semester="高一第二学期",
        full_score=100.0,
        objective_full_score=55.0,
        subjective_full_score=45.0,
    )


def test_parse_real_joint_file():
    score, questions = JointAdapter().parse(_real_exam())
    assert len(score) > 1300
    assert score["student_id"].str.fullmatch(r"\d{12}").all()
    assert "name" in score.columns
    assert (score["school"] != "").all()

    valid = score.dropna(subset=["total_score", "objective_score", "subjective_score"])
    assert valid["objective_score"].max() <= 55.0 + 1e-9
    assert valid["subjective_score"].max() <= 45.0 + 1e-9
    assert valid["total_score"].max() <= 100.0 + 1e-9
    assert (valid["total_score"] - valid["objective_score"] - valid["subjective_score"]).abs().max() < 1e-6
    assert score["total_ratio"].dropna().round(5).equals(score["total_ratio"].dropna())
    assert score["objective_ratio"].dropna().round(5).equals(
        score["objective_ratio"].dropna()
    )
    assert score["subjective_ratio"].dropna().round(5).equals(
        score["subjective_ratio"].dropna()
    )

    assert len(questions) == len(score) * 34
    assert set(questions["question_type"]) == {"客观", "主观"}
    assert questions["question_id"].str.fullmatch(r"(\d+|\d+-\d+)").all()
    assert (questions["question_id"] == "27-4").any()


def test_parse_requires_name_and_subject():
    with pytest.raises(ValueError, match="名称"):
        JointAdapter().parse(
            ExamConfig(format="joint", subject="地理", file="x.xlsx")
        )
    with pytest.raises(ValueError, match="科目"):
        JointAdapter().parse(
            ExamConfig(format="joint", name="联考", file="x.xlsx")
        )


def test_parse_missing_header_raises(tmp_path):
    f = tmp_path / "bad.xlsx"
    pd.DataFrame([["a", "b"], [1, 2]]).to_excel(f, index=False, header=False)
    exam = ExamConfig(
        name="联考",
        format="joint",
        subject="地理",
        folder=str(tmp_path),
        file="bad.xlsx",
    )
    with pytest.raises(ValueError, match="表头"):
        JointAdapter().parse(exam)


def test_parse_subjective_header_variants(tmp_path):
    f = tmp_path / "variants.xlsx"
    pd.DataFrame(
        [
            ["标题"],
            ["姓名", "考号", "学校", "班级",
             "1", "2", "1.0", "2.0", "26(1)", "26（2）", "27-1"],
            [None, "250902010001", "示例二中", "高一(10)", "C", "B", "3", "2", "3", "2", "4"],
            [None, "250902010002", "示例二中", "高一(11)", "A", "D", "2", "2", "2", "2", "6"],
        ]
    ).to_excel(f, index=False, header=False)
    exam = ExamConfig(
        name="联考",
        format="joint",
        subject="地理",
        folder=str(tmp_path),
        file="variants.xlsx",
        full_score=100.0,
        objective_full_score=55.0,
        subjective_full_score=45.0,
    )
    score, questions = JointAdapter().parse(exam)
    assert len(score) == 2
    assert set(questions["question_id"]) == {"1", "2", "26-1", "26-2", "27-1"}
    assert set(questions["question_type"]) == {"客观", "主观"}
    assert score.iloc[0]["objective_score"] == 5.0
    assert score.iloc[0]["subjective_score"] == 9.0


def _en_like_exam(tmp_path, file_name="en.xlsx") -> ExamConfig:
    return ExamConfig(
        name="高二上英语返校考",
        format="joint",
        subject="英语",
        folder=str(tmp_path),
        file=file_name,
        semester="高二第一学期",
        full_score=150.0,
        objective_question_count=3,
        binary_split=False,
        question_types={
            "客观题": [1, 2, 3],
            "主观题": ["语法填空56-65", "应用文", "续写"],
        },
    )


def _write_en_like_file(
    path, extra_numeric_col: str | None = None
) -> None:
    header = [
        "姓名", "考号", "学校", "班级",
        "1", "2", "3",            # 答案列（字母）
        "1.0", "2.0", "3.0",      # 客观得分列
        "语法填空56-65", "应用文", "续写",
    ]
    if extra_numeric_col:
        header.append(extra_numeric_col)
    rows = [
        ["张三", "250907010001", "示例二中", "01",
         "C", "B", "A", 3, 3, 3, 12, 10, 18,
         *( [99] if extra_numeric_col else [] )],
        ["李四", "250907010002", "示例二中", "02",
         "A", "C", "D", 2, 3, 1, 15, 11, 16,
         *( [88] if extra_numeric_col else [] )],
    ]
    pd.DataFrame(
        [["标题"], header, *rows]
    ).to_excel(path, index=False, header=False)


def test_parse_chinese_big_question_columns(tmp_path):
    f = tmp_path / "en.xlsx"
    _write_en_like_file(f)
    score, questions = JointAdapter().parse(_en_like_exam(tmp_path))
    assert len(score) == 2
    assert score.iloc[0]["objective_score"] == 9.0
    assert score.iloc[0]["subjective_score"] == 40.0
    assert score.iloc[0]["total_score"] == 49.0
    assert set(questions["question_id"]) == {
        "1", "2", "3", "语法填空56-65", "应用文", "续写"
    }
    assert set(questions["question_type"]) == {"客观", "主观"}
    assert len(questions) == 12


def test_missing_configured_column_raises_with_hint(tmp_path):
    f = tmp_path / "en.xlsx"
    _write_en_like_file(f)
    exam = _en_like_exam(tmp_path)
    exam.question_types["主观题"] = ["语法填空56-65", "写作", "续写"]
    with pytest.raises(ValueError, match="不存在.*写作"):
        JointAdapter().parse(exam)


def test_unparsed_numeric_column_warns(tmp_path):
    f = tmp_path / "en.xlsx"
    _write_en_like_file(f, extra_numeric_col="附加分")
    score, _ = JointAdapter().parse(_en_like_exam(tmp_path))
    warnings = score.attrs.get("warnings", [])
    assert any("附加分" in w for w in warnings)
