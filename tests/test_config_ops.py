"""CLI 配置修改操作的单元测试。"""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from grade_analyzer.config import load_config
from grade_analyzer.config_ops import (
    get_config_value,
    list_exams,
    set_config_value,
    validate_config_value,
)


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


def test_current_exam_integer_valid():
    assert validate_config_value("current_exam", "3") == "3"
    assert validate_config_value("current_exam", "0") == "0"
    assert validate_config_value("current_exam", "-2") == "-2"
    assert validate_config_value("current_exam", "") == ""  # 空值表示处理全部


def test_current_exam_integer_invalid():
    with pytest.raises(ValueError, match="整数"):
        validate_config_value("current_exam", "abc")
    with pytest.raises(ValueError, match="整数"):
        validate_config_value("current_exam", "1.5")


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
        name="高一下地理周测", folder=str(raw_dir), date="2026-05-12",
    )
    _write_exam(
        exams_dir, "高一第二学期", "联考",
        name="高一下地理联考", folder=str(raw_dir),
    )
    (raw_dir / "周测.xlsx").write_text("raw", encoding="utf-8")
    _write_parsed(tmp_path, "高一第二学期", "高一下地理周测")

    cfg_path = str(_write_global(tmp_path, exams_dir))
    df = list_exams(cfg_path)
    assert len(df) == 2
    row = df[df["考试名称"] == "高一下地理周测"].iloc[0]
    assert row["学期"] == "高一第二学期"
    assert row["日期"] == "2026-05-12"
    assert row["满分"] == "100"
    assert row["检查"] == "可检查"
    assert row["成绩单"] == "已解析"
    row2 = df[df["考试名称"] == "高一下地理联考"].iloc[0]
    assert row2["检查"] == "文件缺失"
    assert row2["成绩单"] == "未解析"


def test_list_exams_filters(tmp_path):
    exams_dir = tmp_path / "exams"
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_exam(exams_dir, "高一第二学期", "周测", name="高一下地理周测", folder=str(raw_dir))
    _write_exam(exams_dir, "高一第二学期", "联考", name="高一下地理联考", folder=str(raw_dir))
    _write_exam(exams_dir, "高一第二学期", "模拟", name="高一下地理模拟", folder=str(raw_dir))
    (raw_dir / "周测.xlsx").write_text("raw", encoding="utf-8")
    (raw_dir / "联考.xlsx").write_text("raw", encoding="utf-8")
    _write_parsed(tmp_path, "高一第二学期", "高一下地理周测")

    cfg_path = str(_write_global(tmp_path, exams_dir))
    assert list(list_exams(cfg_path, checkable=True)["考试名称"]) == [
        "高一下地理周测", "高一下地理联考",
    ]
    assert list(list_exams(cfg_path, results_ready=True)["考试名称"]) == ["高一下地理周测"]
    assert list(
        list_exams(cfg_path, checkable=True, results_ready=True)["考试名称"]
    ) == ["高一下地理周测"]


def test_list_exams_stale_parsed(tmp_path):
    exams_dir = tmp_path / "exams"
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_exam(exams_dir, "高一第二学期", "周测", name="高一下地理周测", folder=str(raw_dir))
    _write_parsed(tmp_path, "高一第二学期", "高一下地理周测")
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
    _write_exam(exams_dir, "高一第二学期", "周测", name="高一下地理周测", folder=str(raw_dir))
    _write_exam(exams_dir, "高二第一学期", "周测", name="高二上地理周测", folder=str(raw_dir))
    (raw_dir / "周测.xlsx").write_text("raw", encoding="utf-8")

    cfg_path = str(_write_global(tmp_path, exams_dir))
    df = list_exams(cfg_path, semester="高二第一学期")
    assert list(df["考试名称"]) == ["高二上地理周测"]
    assert list(df["学期"]) == ["高二第一学期"]


def test_get_config_value(tmp_path, capsys):
    exams_dir = tmp_path / "exams"
    exams_dir.mkdir()
    cfg_path = _write_global(
        tmp_path,
        exams_dir,
        analysis={"pass_ratio": 0.6, "excellent_ratio": 0.85},
        default_grade="高一",
    )
    get_config_value(str(cfg_path), "pass_ratio")
    assert "0.6" in capsys.readouterr().out
    get_config_value(str(cfg_path), "default_grade")
    assert "高一" in capsys.readouterr().out


def test_get_config_value_lists_all_keys(tmp_path, capsys):
    exams_dir = tmp_path / "exams"
    exams_dir.mkdir()
    cfg_path = _write_global(
        tmp_path,
        exams_dir,
        analysis={"pass_ratio": 0.6, "excellent_ratio": 0.85},
        default_grade="高一",
        current_semester="高一第二学期",
        parsed_dir=str(tmp_path / "parsed"),
        parsed_format="csv",
    )
    get_config_value(str(cfg_path))
    out = capsys.readouterr().out
    assert "pass_ratio: 0.6" in out
    assert "excellent_ratio: 0.85" in out
    assert "default_grade: 高一" in out
    assert "current_semester: 高一第二学期" in out
    assert "parsed_dir:" in out
    assert "parsed_format: csv" in out


def test_get_config_value_unknown_key_raises(tmp_path):
    exams_dir = tmp_path / "exams"
    exams_dir.mkdir()
    cfg_path = _write_global(tmp_path, exams_dir)
    with pytest.raises(ValueError, match="不支持的配置键"):
        get_config_value(str(cfg_path), "nope")


def test_set_config_value_persists(tmp_path, capsys):
    exams_dir = tmp_path / "exams"
    exams_dir.mkdir()
    cfg_path = _write_global(tmp_path, exams_dir, default_grade="高一")
    set_config_value(str(cfg_path), "default_grade", "高二")
    out = capsys.readouterr().out
    assert "高二" in out
    assert load_config(str(cfg_path)).default_grade == "高二"
    text = cfg_path.read_text(encoding="utf-8")
    assert "default_grade: 高二" in text
    # 其余键与结构保留
    assert "exams_dir:" in text
    assert "subject_defaults:" in text


def test_set_number_written_as_number(tmp_path):
    exams_dir = tmp_path / "exams"
    exams_dir.mkdir()
    cfg_path = _write_global(
        tmp_path, exams_dir, analysis={"pass_ratio": 0.6, "excellent_ratio": 0.85}
    )
    set_config_value(str(cfg_path), "pass_ratio", "0.7")
    text = cfg_path.read_text(encoding="utf-8")
    assert "pass_ratio: 0.7" in text
    assert load_config(str(cfg_path)).pass_ratio == 0.7


def test_set_invalid_value_keeps_original(tmp_path):
    exams_dir = tmp_path / "exams"
    exams_dir.mkdir()
    cfg_path = _write_global(tmp_path, exams_dir)
    before = cfg_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        set_config_value(str(cfg_path), "pass_ratio", "1.5")
    assert cfg_path.read_text(encoding="utf-8") == before


def test_set_unknown_key_raises(tmp_path):
    exams_dir = tmp_path / "exams"
    exams_dir.mkdir()
    cfg_path = _write_global(tmp_path, exams_dir)
    with pytest.raises(ValueError, match="不支持的配置键"):
        set_config_value(str(cfg_path), "nope", "1")


def test_set_config_value_none_restores_default(tmp_path, capsys):
    exams_dir = tmp_path / "exams"
    exams_dir.mkdir()
    cfg_path = _write_global(
        tmp_path,
        exams_dir,
        analysis={"pass_ratio": 0.7, "excellent_ratio": 0.9},
    )
    set_config_value(str(cfg_path), "pass_ratio", None)
    text = cfg_path.read_text(encoding="utf-8")
    assert "pass_ratio: 0.6" in text
    assert load_config(str(cfg_path)).pass_ratio == 0.6
    assert "0.6" in capsys.readouterr().out


def test_set_config_value_none_restores_current_exam_empty(tmp_path):
    exams_dir = tmp_path / "exams"
    exams_dir.mkdir()
    cfg_path = _write_global(tmp_path, exams_dir, current_exam=3)
    set_config_value(str(cfg_path), "current_exam", None)
    assert load_config(str(cfg_path)).current_exam is None


def test_cli_config_set_without_value_parses():
    from grade_analyzer.cli import build_parser

    args = build_parser().parse_args(["config", "set", "pass_ratio"])
    assert args.config_command == "set"
    assert args.key == "pass_ratio"
    assert args.value is None


def test_set_invalid_combination_keeps_original(tmp_path):
    # 考试条目非法导致整体校验失败：set 应回滚，原文件不变
    exams_dir = tmp_path / "exams"
    (exams_dir / "高一第一学期").mkdir(parents=True)
    (exams_dir / "高一第一学期" / "测试.yaml").write_text(
        "file: ''\n", encoding="utf-8"
    )
    cfg_path = _write_global(tmp_path, exams_dir)
    before = cfg_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        set_config_value(str(cfg_path), "default_grade", "高二")
    assert cfg_path.read_text(encoding="utf-8") == before
    assert not Path(str(cfg_path) + ".tmp").exists()
