"""CLI 配置修改操作的单元测试。"""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from grade_analyzer.config_ops import list_exams, validate_config_value


def test_number_value_valid():
    assert validate_config_value("pass_ratio", "0.65") == "0.65"


def test_number_out_of_range_raises():
    with pytest.raises(ValueError):
        validate_config_value("pass_ratio", "1.5")


def test_number_negative_raises():
    with pytest.raises(ValueError):
        validate_config_value("default_full_score", "-5")


def test_unknown_key_raises():
    with pytest.raises(ValueError):
        validate_config_value("nope", "1")


def test_text_value_ok():
    assert validate_config_value("current_semester", "高一第一学期") == "高一第一学期"


def _write_global(tmp_path: Path, exams_dir: Path, **overrides) -> Path:
    data = {
        "subjects": ["语文", "数学", "外语", "物理", "化学", "生物", "政治", "历史", "地理", "技术"],
        "subject_defaults": {
            "地理": {
                "full_score": 100,
                "objective_full_score": 50,
                "subjective_full_score": 50,
            }
        },
        "exams_dir": str(exams_dir),
        "parsed_dir": str(tmp_path / "parsed"),
        "parsed_format": "csv",
    }
    data.update(overrides)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return cfg


def _write_exam(
    exams_dir: Path, semester: str | None, file_name: str, **fields
) -> Path:
    folder = exams_dir if semester is None else exams_dir / semester
    folder.mkdir(parents=True, exist_ok=True)
    data = {"file": f"{file_name}.xlsx", "subject": "地理"}
    data.update(fields)
    f = folder / f"{file_name}.yaml"
    f.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return f


def _write_parsed(tmp_path: Path, semester: str, exam_name: str) -> None:
    parsed = tmp_path / "parsed" / semester / exam_name
    parsed.mkdir(parents=True, exist_ok=True)
    (parsed / "score_summary.csv").write_text("score", encoding="utf-8")
    (parsed / "question_detail.csv").write_text("question", encoding="utf-8")


def test_list_exams_status_columns(tmp_path):
    exams_dir = tmp_path / "exams"
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_exam(
        exams_dir, "高一第二学期", "周测",
        name="高一下周测", folder=str(raw_dir), date="2026-05-12",
    )
    _write_exam(
        exams_dir, "高一第二学期", "联考",
        name="高一下联考", folder=str(raw_dir),
    )
    (raw_dir / "周测.xlsx").write_text("raw", encoding="utf-8")
    _write_parsed(tmp_path, "高一第二学期", "高一下周测")

    cfg_path = str(_write_global(tmp_path, exams_dir))
    df = list_exams(cfg_path)
    assert len(df) == 2
    row = df[df["考试名称"] == "高一下周测"].iloc[0]
    assert row["学期"] == "高一第二学期"
    assert row["日期"] == "2026-05-12"
    assert row["满分"] == "100"
    assert row["检查"] == "可检查"
    assert row["成绩单"] == "已解析"
    row2 = df[df["考试名称"] == "高一下联考"].iloc[0]
    assert row2["检查"] == "文件缺失"
    assert row2["成绩单"] == "未解析"


def test_list_exams_filters(tmp_path):
    exams_dir = tmp_path / "exams"
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_exam(exams_dir, "高一第二学期", "周测", name="高一下周测", folder=str(raw_dir))
    _write_exam(exams_dir, "高一第二学期", "联考", name="高一下联考", folder=str(raw_dir))
    _write_exam(exams_dir, "高一第二学期", "模拟", name="高一下模拟", folder=str(raw_dir))
    (raw_dir / "周测.xlsx").write_text("raw", encoding="utf-8")
    (raw_dir / "联考.xlsx").write_text("raw", encoding="utf-8")
    _write_parsed(tmp_path, "高一第二学期", "高一下周测")

    cfg_path = str(_write_global(tmp_path, exams_dir))
    assert list(list_exams(cfg_path, checkable=True)["考试名称"]) == [
        "高一下周测", "高一下联考",
    ]
    assert list(list_exams(cfg_path, results_ready=True)["考试名称"]) == ["高一下周测"]
    assert list(
        list_exams(cfg_path, checkable=True, results_ready=True)["考试名称"]
    ) == ["高一下周测"]


def test_list_exams_stale_parsed(tmp_path):
    exams_dir = tmp_path / "exams"
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_exam(exams_dir, "高一第二学期", "周测", name="高一下周测", folder=str(raw_dir))
    _write_parsed(tmp_path, "高一第二学期", "高一下周测")
    # 原始文件后创建 => 解析表早于原始文件 => 已过期
    (raw_dir / "周测.xlsx").write_text("raw", encoding="utf-8")

    cfg_path = str(_write_global(tmp_path, exams_dir))
    df = list_exams(cfg_path)
    assert df.iloc[0]["检查"] == "可检查"
    assert df.iloc[0]["成绩单"] == "已过期"


def test_list_exams_semester_filter(tmp_path):
    exams_dir = tmp_path / "exams"
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_exam(exams_dir, "高一第二学期", "周测", name="高一下周测", folder=str(raw_dir))
    _write_exam(exams_dir, "高二第一学期", "周测", name="高二上周测", folder=str(raw_dir))
    (raw_dir / "周测.xlsx").write_text("raw", encoding="utf-8")

    cfg_path = str(_write_global(tmp_path, exams_dir))
    df = list_exams(cfg_path, semester="高二第一学期")
    assert list(df["考试名称"]) == ["高二上周测"]
    assert list(df["学期"]) == ["高二第一学期"]
