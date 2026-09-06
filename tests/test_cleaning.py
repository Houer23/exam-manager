"""清洗层工具的单元测试。"""

import pandas as pd
import pytest

from grade_analyzer.cleaning import (
    add_question_type_scores,
    clean_score_table,
    classify_objective_types,
    collect_quality_issues,
    compute_ranks,
    enrich_metadata,
    filter_default_school,
    extract_grade,
    normalize_class_name,
    validate_student_ids,
    validate_total_score,
)
from grade_analyzer.config import AnalysisConfig, ExamConfig


def test_extract_grade_from_class():
    assert extract_grade("高一年级13班") == "高一"
    assert extract_grade("高一(10)") == "高一"
    assert extract_grade("高二(3)") == "高二"
    assert extract_grade("高三第二学期5班") == "高三"


def test_extract_grade_missing():
    assert extract_grade("4") is None
    assert extract_grade("") is None
    assert extract_grade(None) is None


def test_normalize_rule1():
    assert normalize_class_name("高一年级4班", "高一") == ("高一04班", "高一")
    assert normalize_class_name("高一年级16班", "高一") == ("高一16班", "高一")
    assert normalize_class_name("高二3班", "高一") == ("高二03班", "高二")


def test_normalize_rule2():
    assert normalize_class_name("高一(10)", "高一") == ("高一10班", "高一")
    assert normalize_class_name("高一（3）", "高一") == ("高一03班", "高一")


def test_normalize_rule3_uses_default_grade():
    assert normalize_class_name("4", "高一") == ("高一04班", "高一")
    assert normalize_class_name("3", "高二") == ("高二03班", "高二")


def test_normalize_unmatched():
    assert normalize_class_name("未知格式", "高一") == ("未知格式", None)
    assert normalize_class_name("", "高一") == ("", None)


def test_validate_student_ids_missing_raises():
    df = pd.DataFrame({"student_id": ["250907010001", "", "nan"]})
    with pytest.raises(ValueError, match="缺失"):
        validate_student_ids(df)


def test_validate_student_ids_bad_length_raises():
    df = pd.DataFrame({"student_id": ["250907010001", "123"]})
    with pytest.raises(ValueError, match="非 12 位"):
        validate_student_ids(df)


def test_validate_student_ids_duplicate_raises():
    df = pd.DataFrame({"student_id": ["250907010001", "250907010001"]})
    with pytest.raises(ValueError, match="重复"):
        validate_student_ids(df)


def test_validate_student_ids_ok():
    df = pd.DataFrame({"student_id": ["250907010001", "250907010002"]})
    validate_student_ids(df)  # 不抛异常


def test_validate_total_score_over_full_raises():
    df = pd.DataFrame(
        {"student_id": ["250907010001"], "total_score": [101.0]}
    )
    with pytest.raises(ValueError, match="越界"):
        validate_total_score(df, 100.0)


def test_validate_total_score_negative_raises():
    df = pd.DataFrame(
        {"student_id": ["250907010001"], "total_score": [-1.0]}
    )
    with pytest.raises(ValueError, match="越界"):
        validate_total_score(df, 100.0)


def test_validate_total_score_skips_missing():
    df = pd.DataFrame(
        {"student_id": ["250907010001"], "total_score": [float("nan")]}
    )
    validate_total_score(df, 100.0)  # 缺考跳过，不抛异常


def _score_df():
    return pd.DataFrame(
        {
            "student_id": ["250907010001", "250907010002"],
            "class_raw": ["高一年级13班", "4"],
            "school": ["示例二中", "示例二中"],
            "total_score": [84.0, 70.0],
            "objective_score": [74.0, 40.0],
            "subjective_score": [10.0, 30.0],
        }
    )


def test_clean_score_table_normalizes_and_no_issues():
    exam = ExamConfig(
        name="测试", full_score=100.0, objective_full_score=85.0,
        subjective_full_score=45.0,
    )
    cfg = AnalysisConfig(default_grade="高一")
    cleaned, issues = clean_score_table(_score_df(), exam, cfg)
    assert cleaned["class_name"].tolist() == ["高一13班", "高一04班"]
    assert cleaned["grade"].tolist() == ["高一", "高一"]
    assert len(issues) == 0


def test_collect_quality_issues():
    df = _score_df()
    df.loc[1, "objective_score"] = 60.0  # 超客观满分 55
    df.loc[1, "subjective_score"] = 20.0
    df.loc[1, "total_score"] = 90.0  # 60+20=80 ≠ 90
    df.loc[1, "class_raw"] = "未知格式"
    exam = ExamConfig(
        name="测试", full_score=100.0, objective_full_score=55.0,
        subjective_full_score=45.0,
    )
    cfg = AnalysisConfig(default_grade="高一")
    cleaned, issues = clean_score_table(df, exam, cfg)
    types = set(issues["问题类型"])
    assert "客观分超满分" in types
    assert "客观+主观≠总分" in types
    assert "班级无法归一化" in types


def test_compute_ranks_competition_ranking():
    df = pd.DataFrame(
        {
            "student_id": ["250907010001", "250907010002", "250907010003", "250907010004"],
            "class_name": ["高一01班", "高一01班", "高一01班", "高一02班"],
            "school": ["示例二中", "示例二中", "示例二中", "示例二中"],
            "total_score": [90.0, 90.0, 80.0, 85.0],
        }
    )
    compute_ranks(df)
    by_id = df.set_index("student_id")
    assert by_id.loc["250907010001", "班次"] == 1
    assert by_id.loc["250907010002", "班次"] == 1  # 同分同名次
    assert by_id.loc["250907010003", "班次"] == 3  # 名次不连续
    assert by_id.loc["250907010004", "班次"] == 1  # 单独班级
    assert by_id.loc["250907010001", "校次"] == 1
    assert by_id.loc["250907010003", "校次"] == 4  # 90/90/85 在前


def test_compute_ranks_skips_missing_group():
    df = pd.DataFrame(
        {
            "student_id": ["250907010001", "250907010002"],
            "class_name": ["高一01班", ""],
            "school": ["示例二中", "示例二中"],
            "total_score": [80.0, 70.0],
        }
    )
    compute_ranks(df)
    assert pd.isna(df.loc[1, "班次"])
    assert df.loc[0, "班次"] == 1


def test_compute_ranks_group_by_school_and_class():
    df = pd.DataFrame(
        {
            "student_id": ["250907010001", "250907010002", "250907010003"],
            "class_name": ["高一10班", "高一10班", "高一10班"],
            "school": ["示例二中", "示例二中", "示例一中"],
            "total_score": [80.0, 70.0, 90.0],
        }
    )
    compute_ranks(df)
    by_id = df.set_index("student_id")
    assert by_id.loc["250907010001", "班次"] == 1
    assert by_id.loc["250907010002", "班次"] == 2
    assert by_id.loc["250907010003", "班次"] == 1  # 不同学校同名班级各自排名


def _question_df(ids, scores_by_q):
    rows = []
    for qid, scores in scores_by_q.items():
        for sid, s in zip(ids, scores):
            rows.append(
                {
                    "exam_name": "测试",
                    "student_id": sid,
                    "question_id": qid,
                    "question_type": "客观",
                    "score": s,
                    "full_score": None,
                }
            )
    return pd.DataFrame(rows)


def test_classify_objective_types_two_levels():
    q = _question_df(
        ["250907010001", "250907010002"],
        {"1": [2.0, 2.0], "2": [2.0, 0.0], "21": [3.0, 3.0], "22": [0.0, 3.0]},
    )
    q = classify_objective_types(q)
    types = q.set_index("question_id")["question_type"].to_dict()
    assert types["1"] == "单选"
    assert types["2"] == "单选"
    assert types["21"] == "多选"
    assert types["22"] == "多选"


def test_classify_objective_types_all_equal_no_multi():
    q = _question_df(
        ["250907010001"],
        {"1": [2.0], "2": [2.0], "3": [2.0]},
    )
    q = classify_objective_types(q)
    assert set(q["question_type"]) == {"客观"}  # 无多选，保持客观


def test_classify_objective_types_switch_off_keeps_objective():
    q = _question_df(
        ["250907010001", "250907010002"],
        {"1": [2.0, 2.0], "2": [2.0, 0.0], "21": [3.0, 3.0], "22": [0.0, 3.0]},
    )
    exam = ExamConfig(
        name="测试",
        format="joint",
        subject="地理",
        file="x.xlsx",
        auto_single_multi=False,
    )
    q = classify_objective_types(q, exam)
    assert set(q["question_type"]) == {"客观"}


def test_classify_objective_types_switch_on_splits():
    q = _question_df(
        ["250907010001", "250907010002"],
        {"1": [2.0, 2.0], "2": [2.0, 0.0], "21": [3.0, 3.0], "22": [0.0, 3.0]},
    )
    exam = ExamConfig(
        name="测试",
        format="joint",
        subject="地理",
        file="x.xlsx",
        auto_single_multi=True,
    )
    q = classify_objective_types(q, exam)
    types = q.set_index("question_id")["question_type"].to_dict()
    assert types["1"] == "单选"
    assert types["21"] == "多选"


def test_classify_objective_types_only_subjective_unchanged():
    q = pd.DataFrame(
        {
            "exam_name": ["测试"],
            "student_id": ["250907010001"],
            "question_id": ["26-1"],
            "question_type": ["主观"],
            "score": [3.0],
            "full_score": [None],
        }
    )
    q = classify_objective_types(q)
    assert q["question_type"].iloc[0] == "主观"


def test_add_question_type_scores():
    score = pd.DataFrame({"student_id": ["S1", "S2"]})
    q = _question_df(
        ["S1", "S2"],
        {"1": [2.0, 2.0], "2": [2.0, 0.0], "21": [3.0, 0.0], "26-1": [3.0, 2.0]},
    )
    q["question_type"] = ["单选", "单选", "单选", "单选", "多选", "多选", "主观", "主观"]
    score, q = add_question_type_scores(score, q)
    assert score.loc[0, "单选分"] == 4.0
    assert score.loc[0, "多选分"] == 3.0
    assert score.loc[0, "单选满分"] == 4.0  # 2 + 2
    assert score.loc[0, "多选满分"] == 3.0  # 3
    assert q.loc[q["question_id"] == "1", "full_score"].iloc[0] == 2.0
    assert q.loc[q["question_id"] == "26-1", "full_score"].iloc[0] == 3.0


def test_filter_default_school():
    score = pd.DataFrame(
        {
            "student_id": ["A1", "A2", "B1"],
            "school": ["示例一中", "示例一中", "示例二中"],
            "total_score": [70.0, 80.0, 90.0],
        }
    )
    questions = pd.DataFrame(
        {
            "student_id": ["A1", "A2", "B1", "B1"],
            "question_id": ["1", "1", "1", "2"],
        }
    )
    kept_score, kept_q = filter_default_school(score, questions, "示例一中")
    assert set(kept_score["student_id"]) == {"A1", "A2"}
    assert set(kept_q["student_id"]) == {"A1", "A2"}


def test_enrich_metadata():
    from grade_analyzer.config import ClassInfo, TeacherMap

    cfg = AnalysisConfig()
    cfg.class_infos = {
        ("高一第二学期", "高一10班"): ClassInfo(level="A", course="物化地")
    }
    cfg.teacher_maps = {
        ("高一第二学期", "地理"): TeacherMap(
            subject="地理",
            teacher_count=1,
            teacher_names={"A": "柯老师"},
            class_teachers={"高一10班": "A"},
        )
    }
    exam = ExamConfig(name="测试", semester="高一第二学期", subject="地理")
    score = pd.DataFrame(
        {"student_id": ["S1", "S2"], "class_name": ["高一10班", "高一11班"]}
    )
    enriched = enrich_metadata(score, exam, cfg)
    assert enriched.loc[0, "class_level"] == "A"
    assert enriched.loc[0, "course"] == "物化地"
    assert enriched.loc[0, "teacher"] == "柯老师"
    assert enriched.loc[1, "class_level"] == ""  # 未配置班级留空
    assert enriched.loc[1, "teacher"] == ""
