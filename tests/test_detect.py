"""文件名识别与格式识别的单元测试。"""

import pandas as pd

from grade_analyzer.adapters.joint import JointAdapter
from grade_analyzer.adapters.registry import auto_detect_format
from grade_analyzer.adapters.weekly import WeeklyAdapter
from grade_analyzer.detect import (
    detect_subject_from_filename,
    extract_exam_name_from_filename,
    resolve_exam_name,
)
from grade_analyzer.config import ExamConfig


def test_extract_exam_name():
    path = "data/input/测试样例/【教学班报告--高一下地理限时练一】所有班级学生小题得分明细.xlsx"
    assert extract_exam_name_from_filename(path) == "高一下地理限时练一"


def test_extract_exam_name_not_found():
    assert extract_exam_name_from_filename("data/input/地理原始数据.xlsx") is None


SUBJECTS = ["语文", "数学", "外语", "物理", "化学", "生物", "政治", "历史", "地理", "技术"]
ALIASES = {"外语": ["英语", "俄语", "日语"], "技术": ["信息技术", "通用技术"]}


def test_detect_subject_direct():
    assert detect_subject_from_filename("高一下地理限时练一.xlsx", SUBJECTS, ALIASES) == "地理"


def test_detect_subject_via_alias():
    assert detect_subject_from_filename("高一英语试卷.xlsx", SUBJECTS, ALIASES) == "外语"


def test_detect_subject_multiple_hits_returns_none():
    assert detect_subject_from_filename("地理与语文.xlsx", SUBJECTS, ALIASES) is None


def test_detect_subject_not_found():
    assert detect_subject_from_filename("未知.xlsx", SUBJECTS, ALIASES) is None


def test_resolve_exam_name_from_filename():
    exam = ExamConfig(
        folder="data/input/测试样例",
        file="【教学班报告--高一下地理限时练一】所有班级学生小题得分明细.xlsx",
        semester="高一第二学期",
    )
    assert resolve_exam_name(exam) == "高一下地理限时练一"


def test_resolve_exam_name_explicit_wins():
    exam = ExamConfig(
        name="高一下期中联考",
        folder="data/input/测试样例",
        file="地理原始数据.xlsx",
        semester="高一第二学期",
    )
    assert resolve_exam_name(exam) == "高一下期中联考"


def test_resolve_exam_name_not_found():
    exam = ExamConfig(folder="data/input", file="无标识.xlsx", semester="高一第二学期")
    assert resolve_exam_name(exam) is None


def test_resolve_exam_name_adds_subject():
    exam = ExamConfig(
        file="【测试--限时练一】学生成绩.xlsx",
        semester="高一第二学期",
        subject="地理",
    )
    assert resolve_exam_name(exam) == "高一下地理限时练一"


def test_resolve_exam_name_skips_subject_alias():
    exam = ExamConfig(
        file="【测试--英语周测】学生成绩.xlsx",
        semester="高一第二学期",
        subject="外语",
    )
    assert resolve_exam_name(exam, SUBJECTS, ALIASES) == "高一下英语周测"


def _weekly_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["标题"],
            ["序号", "姓名", "准考证号", "自定义考号", "班级", "总分", "客观分"],
            ["1", None, "123", "2509", "高一(1)", "84", "74"],
        ]
    )


def _joint_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["标题"],
            ["姓名", "考号", "学校", "班级", "1", "2", "3"],
            [None, "250902010001", "示例二中", "高一(10)", "C", "B", "AB"],
        ]
    )


def _unknown_df() -> pd.DataFrame:
    return pd.DataFrame([["a", "b"], [1, 2]])


def test_weekly_detect():
    assert WeeklyAdapter.detect(_weekly_df()) is True
    assert WeeklyAdapter.detect(_joint_df()) is False


def test_joint_detect():
    assert JointAdapter.detect(_joint_df()) is True
    assert JointAdapter.detect(_weekly_df()) is False


def test_auto_detect_format():
    assert auto_detect_format(_weekly_df()) == "weekly"
    assert auto_detect_format(_joint_df()) == "joint"
    assert auto_detect_format(_unknown_df()) is None
