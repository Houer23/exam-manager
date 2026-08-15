"""合并模块的单元测试。"""

import pandas as pd
import pytest
import yaml

from grade_analyzer.config import AnalysisConfig, ExamConfig
from grade_analyzer.consolidate import (
    merge_score_tables,
    resolve_current_exam,
    run_merge,
    select_exams,
)
from grade_analyzer.storage import write_parsed_tables


def _exam(name: str, date: str | None) -> ExamConfig:
    return ExamConfig(name=name, date=date)


def _score_df(exam_name, student_ids, totals, ratios, class_name, grade, school):
    n = len(student_ids)
    return pd.DataFrame(
        {
            "exam_name": [exam_name] * n,
            "exam_type": ["默认"] * n,
            "student_id": list(student_ids),
            "name": [""] * n,
            "class_name": [class_name] * n,
            "class_raw": [class_name] * n,
            "grade": [grade] * n,
            "school": [school] * n,
            "subject": ["地理"] * n,
            "total_score": list(totals),
            "objective_score": [0.0] * n,
            "subjective_score": [0.0] * n,
            "full_score": [100.0] * n,
            "objective_full_score": [55.0] * n,
            "subjective_full_score": [45.0] * n,
            "total_ratio": list(ratios),
            "objective_ratio": [0.0] * n,
            "subjective_ratio": [0.0] * n,
        }
    )


def test_select_exams_filters():
    exams = [
        ExamConfig(name="A", type="默认", semester="高一第二学期", subject="地理"),
        ExamConfig(name="B", type="模考", semester="高一第二学期", subject="地理"),
        ExamConfig(name="C", type="默认", semester="高一第一学期", subject="地理"),
        ExamConfig(name="D", type="默认", semester="高一第二学期", subject="数学"),
    ]
    assert [e.name for e in select_exams(exams, semester="高一第二学期")] == ["A", "B", "D"]
    assert [e.name for e in select_exams(exams, types=["默认"])] == ["A", "C", "D"]
    assert [e.name for e in select_exams(exams, subject="地理")] == ["A", "B", "C"]
    assert [
        e.name
        for e in select_exams(
            exams, semester="高一第二学期", types=["默认"], subject="地理"
        )
    ] == ["A"]


def test_merge_score_tables():
    e1 = ExamConfig(name="高一下地理期中联考", type="默认", semester="高一第二学期", date="2026-04-20")
    e2 = ExamConfig(name="高一下地理限时练一", type="默认", semester="高一第二学期", date="2026-03-25")
    df1 = _score_df(
        "高一下地理期中联考",
        ["250907010001", "250907010002"],
        [70.0, 80.0],
        [0.7, 0.8],
        "高一10班", "高一", "青田中学",
    )
    df2 = _score_df(
        "高一下地理限时练一",
        ["250907010001", "250907010003"],
        [84.0, 90.0],
        [0.84, 0.9],
        "高一13班", "高一", "遂昌中学",
    )
    long_df, wide = merge_score_tables([(e1, df1), (e2, df2)])

    assert len(long_df) == 4
    assert set(wide["student_id"]) == {"250907010001", "250907010002", "250907010003"}

    by_id = wide.set_index("student_id")
    row = by_id.loc["250907010001"]
    assert row["高一下地理期中联考_得分率"] == 0.7
    assert row["高一下地理限时练一_得分率"] == 0.84
    assert row["参考场次"] == 2
    assert abs(row["平均得分率"] - 0.77) < 1e-9
    assert row["班级"] == "高一10班"  # 最近一场（date 最大）

    row2 = by_id.loc["250907010002"]
    assert pd.isna(row2["高一下地理限时练一_得分率"])  # 未参加 = 空值
    assert row2["参考场次"] == 1


def _write_exam_yaml(exams_dir, semester, file_name, name, folder, file):
    folder_path = exams_dir / semester
    folder_path.mkdir(parents=True, exist_ok=True)
    (folder_path / f"{file_name}.yaml").write_text(
        f"name: {name}\n"
        f"type: 默认\n"
        f"folder: {folder}\n"
        f"file: {file}\n"
        f"subject: 地理\n"
        f"full_score: 100\n"
        f"objective_full_score: 55\n"
        f"subjective_full_score: 45\n",
        encoding="utf-8",
    )


def _write_config(tmp_path, exams_dir, parsed_dir, out_dir):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        yaml.safe_dump(
            {
                "subjects": ["语文", "数学", "外语", "物理", "化学", "生物", "政治", "历史", "地理", "技术"],
                "exams_dir": str(exams_dir),
                "parsed_dir": str(parsed_dir),
                "current_semester": "高一第二学期",
                "output": {"dir": str(out_dir), "excel_name": "成绩分析汇总.xlsx"},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return str(cfg)


def test_run_merge_writes_outputs(tmp_path):
    exams_dir = tmp_path / "exams"
    parsed = tmp_path / "parsed"
    out = tmp_path / "out"

    e1 = ExamConfig(name="高一下地理期中联考", type="默认", semester="高一第二学期", date="2026-04-20")
    e2 = ExamConfig(name="高一下地理限时练一", type="默认", semester="高一第二学期", date="2026-03-25")
    write_parsed_tables(
        str(parsed), e1,
        _score_df("高一下地理期中联考", ["250907010001", "250907010002"], [70.0, 80.0], [0.7, 0.8], "高一10班", "高一", "青田中学"),
        pd.DataFrame(columns=["exam_name", "student_id", "question_id", "question_type", "score", "full_score"]),
    )
    write_parsed_tables(
        str(parsed), e2,
        _score_df("高一下地理限时练一", ["250907010001"], [84.0], [0.84], "高一13班", "高一", "遂昌中学"),
        pd.DataFrame(columns=["exam_name", "student_id", "question_id", "question_type", "score", "full_score"]),
    )
    _write_exam_yaml(exams_dir, "高一第二学期", "联考", "高一下地理期中联考", "data/input/测试样例", "地理原始数据.xlsx")
    _write_exam_yaml(exams_dir, "高一第二学期", "周测", "高一下地理限时练一", "data/input/测试样例", "周测.xlsx")

    cfg_path = _write_config(tmp_path, exams_dir, parsed, out)
    run_merge(cfg_path)

    wide_path = out / "merged" / "merged_wide.csv"
    long_path = out / "merged" / "merged_long.csv"
    assert wide_path.is_file()
    assert long_path.is_file()
    wide = pd.read_csv(wide_path, encoding="utf-8-sig")
    assert {"student_id", "平均得分率", "参考场次", "高一下地理期中联考_得分率", "高一下地理限时练一_得分率"} <= set(wide.columns)
    assert len(wide) == 2


def test_run_merge_with_baseline(tmp_path):
    exams_dir = tmp_path / "exams"
    parsed = tmp_path / "parsed"
    out = tmp_path / "out"

    e1 = ExamConfig(name="高一下地理期中联考", type="默认", semester="高一第二学期", date="2026-04-20")
    e2 = ExamConfig(name="高一上地理基准", type="默认", semester="高一第一学期", date="2026-01-10")
    write_parsed_tables(
        str(parsed), e1,
        _score_df("高一下地理期中联考", ["250907010001"], [70.0], [0.7], "高一10班", "高一", "青田中学"),
        pd.DataFrame(columns=["exam_name", "student_id", "question_id", "question_type", "score", "full_score"]),
    )
    write_parsed_tables(
        str(parsed), e2,
        _score_df("高一上地理基准", ["250907010001"], [60.0], [0.6], "高一02班", "高一", "青田中学"),
        pd.DataFrame(columns=["exam_name", "student_id", "question_id", "question_type", "score", "full_score"]),
    )
    _write_exam_yaml(exams_dir, "高一第二学期", "联考", "高一下地理期中联考", "data/input/测试样例", "地理原始数据.xlsx")
    _write_exam_yaml(exams_dir, "高一第一学期", "基准", "高一上地理基准", "data/input/测试样例", "基准.xlsx")

    cfg_path = _write_config(tmp_path, exams_dir, parsed, out)
    run_merge(cfg_path, baseline_exams="高一上地理基准")

    wide = pd.read_csv(out / "merged" / "merged_wide.csv", encoding="utf-8-sig")
    assert "高一上地理基准_得分率" in wide.columns
    assert len(wide) == 1


def test_cli_exam_overrides_config():
    exams = [_exam("A", "2026-05-01"), _exam("B", "2026-06-01")]
    cfg = AnalysisConfig(current_exam="A")
    assert resolve_current_exam(exams, explicit="B", config=cfg).name == "B"


def test_config_exam_wins_over_date():
    exams = [_exam("A", "2026-05-01"), _exam("B", "2026-06-01")]
    cfg = AnalysisConfig(current_exam="A")
    assert resolve_current_exam(exams, explicit=None, config=cfg).name == "A"


def test_fallback_to_latest_date():
    exams = [_exam("A", "2026-05-01"), _exam("B", "2026-06-01")]
    cfg = AnalysisConfig()
    assert resolve_current_exam(exams, explicit=None, config=cfg).name == "B"


def test_same_date_keeps_last_in_order():
    exams = [_exam("A", "2026-05-01"), _exam("B", "2026-05-01")]
    cfg = AnalysisConfig()
    assert resolve_current_exam(exams, explicit=None, config=cfg).name == "B"


def test_explicit_not_found_raises():
    exams = [_exam("A", "2026-05-01")]
    cfg = AnalysisConfig()
    with pytest.raises(ValueError):
        resolve_current_exam(exams, explicit="X", config=cfg)
