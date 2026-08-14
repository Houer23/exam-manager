"""输出目录组织的单元测试。"""

import pytest

from grade_analyzer.config import ExamConfig, OutputConfig
from grade_analyzer.outputs import (
    OUTPUT_TYPES,
    merged_dir,
    statistics_dir,
    statistics_path,
    type_dir,
)
from grade_analyzer.storage import class_summary_path


def _output() -> OutputConfig:
    return OutputConfig(dir="data/output")


def test_output_types():
    assert OUTPUT_TYPES == ["merged", "reports", "statistics", "charts", "quality", "run-info"]
    for t in OUTPUT_TYPES:
        assert type_dir(_output(), t).name == t


def test_unknown_type_raises():
    with pytest.raises(ValueError, match="未知输出类型"):
        type_dir(_output(), "nope")


def test_merged_dir():
    assert merged_dir(_output()) == type_dir(_output(), "merged")


def test_statistics_dir_semester():
    assert statistics_dir(_output(), "高一第二学期").name == "高一第二学期"
    assert statistics_dir(_output(), None).name == "statistics"


def test_statistics_path_with_exam_name():
    p = statistics_path(_output(), "高一第二学期", "高一下期中联考", "科目统计")
    assert p.name == "高一下期中联考_科目统计.csv"
    assert p.parent.name == "高一第二学期"


def test_class_summary_path():
    exam = ExamConfig(name="高一下期中联考", semester="高一第二学期")
    p = class_summary_path("data/parsed", exam)
    assert p.name == "class_summary.csv"
    assert "高一第二学期" in p.parts
    assert "高一下期中联考" in p.parts
