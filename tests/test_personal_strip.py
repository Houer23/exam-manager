"""个人成绩单生成的单元测试。"""

import pandas as pd

from grade_analyzer.config import AnalysisConfig, ExamConfig, OutputConfig, TeacherMap
from grade_analyzer.personal_strip import build_personal_strips
from grade_analyzer.result_config import ResultsConfig


def _exam() -> ExamConfig:
    return ExamConfig(
        name="高一下期中联考",
        short_name="联考",
        semester="高一第二学期",
        subject="地理",
        date="2026-04-20",
        full_score=100.0,
    )


def _score() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "student_id": ["S1", "S2", "S3", "S4"],
            "name": ["", "", "", ""],
            "class_name": ["高一10班", "高一10班", "高一11班", "高一11班"],
            "class_level": ["A", "A", "B", "B"],
            "teacher": ["柯", "柯", "叶", "叶"],
            "total_score": [80.0, 70.0, 90.0, 60.0],
            "objective_score": [50.0, 40.0, 55.0, 30.0],
            "subjective_score": [30.0, 30.0, 35.0, 30.0],
            "单选分": [40.0, 30.0, 44.0, 25.0],
            "多选分": [10.0, 10.0, 11.0, 5.0],
            "班次": [1, 2, 1, 2],
            "校次": [2, 5, 1, 8],
        }
    )


def _questions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "student_id": ["S1", "S2", "S3", "S4"] * 2,
            "question_id": ["26-1"] * 4 + ["26-2"] * 4,
            "question_type": ["主观"] * 8,
            "score": [3.0, 2.0, 4.0, 1.0, 2.0, 3.0, 1.0, 2.0],
            "full_score": [None] * 8,
        }
    )


def _config(tmp_path) -> AnalysisConfig:
    cfg = AnalysisConfig(results_dir=str(tmp_path / "results"))
    cfg.teacher_maps = {
        ("高一第二学期", "地理"): TeacherMap(
            subject="地理",
            teacher_count=2,
            teacher_names={"A": "柯", "B": "叶"},
            class_teachers={"高一10班": "A", "高一11班": "B"},
        )
    }
    return cfg


def test_build_all_scope(tmp_path):
    paths = build_personal_strips(
        _exam(), _score(), _questions(), ResultsConfig(), _config(tmp_path)
    )
    assert len(paths) == 1
    assert paths[0].endswith("20260420_高一下期中联考_全部班级_个人成绩单.xlsx")


def test_build_teacher_scope(tmp_path):
    cfg = ResultsConfig()
    cfg.personal.scope.mode = "teacher"
    cfg.personal.scope.teachers = ["柯"]
    paths = build_personal_strips(
        _exam(), _score(), _questions(), cfg, _config(tmp_path)
    )
    assert len(paths) == 1
    assert paths[0].endswith("_柯_个人成绩单.xlsx")


def test_build_teacher_scope_letter_code(tmp_path):
    cfg = ResultsConfig()
    cfg.personal.scope.mode = "teacher"
    cfg.personal.scope.teachers = ["A"]  # 字母代号 -> 柯
    paths = build_personal_strips(
        _exam(), _score(), _questions(), cfg, _config(tmp_path)
    )
    assert len(paths) == 1
    assert paths[0].endswith("_柯_个人成绩单.xlsx")


def test_build_teacher_invalid_raises(tmp_path):
    import pytest

    cfg = ResultsConfig()
    cfg.personal.scope.mode = "teacher"
    cfg.personal.scope.teachers = ["Z"]
    with pytest.raises(ValueError, match="教师配置无效"):
        build_personal_strips(
            _exam(), _score(), _questions(), cfg, _config(tmp_path)
        )


def test_build_custom_scope_label(tmp_path):
    cfg = ResultsConfig()
    cfg.personal.scope.mode = "custom"
    cfg.personal.scope.classes = ["高一10班"]
    paths = build_personal_strips(
        _exam(), _score(), _questions(), cfg, _config(tmp_path)
    )
    assert len(paths) == 1
    assert paths[0].endswith("_柯_个人成绩单.xlsx")  # 与柯老师任教班级一致


def test_build_merged_mode(tmp_path):
    exam = _exam()
    exam.question_display = "merged"
    exam.show_big_questions = True
    cfg = ResultsConfig()
    cfg.personal.merged_prefix = "M"
    cfg.personal.big_score_prefix = "S"
    paths = build_personal_strips(
        exam, _score(), _questions(), cfg, _config(tmp_path)
    )
    import openpyxl

    ws = openpyxl.load_workbook(paths[0])["个人成绩单"]
    header = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    assert "M26" in header  # 合并列：前缀+大题题号
    assert "S26" in header  # 大题总分列：前缀+大题题号
    assert "26(1)" not in header
    merged = ws.cell(2, header.index("M26") + 1).value
    assert merged == "3|2"  # 按[班级,总分,考号]排序后首位为 高一10班 S1
    assert ws.cell(2, header.index("S26") + 1).value == 5.0  # 3+2
    assert ws.column_dimensions["K"].width == 8  # 合并小题列宽
    assert ws.column_dimensions["L"].width == 4  # 大题列宽


def test_strip_style(tmp_path):
    import openpyxl

    paths = build_personal_strips(
        _exam(), _score(), _questions(), ResultsConfig(), _config(tmp_path)
    )
    ws = openpyxl.load_workbook(paths[0])["个人成绩单"]
    assert ws.cell(1, 1).font.name == "宋体"
    assert ws.cell(1, 1).border.top.style == "medium"  # 表头上框线略粗
    assert ws.cell(2, 1).border.top.style == "thin"  # 数据行正常
    assert ws.cell(2, 6).alignment.horizontal == "center"  # 总分居中
    assert ws.cell(2, 7).alignment.horizontal == "right"  # 客观分右对齐
    assert ws.cell(2, 1).alignment.vertical == "center"  # 垂直居中


def test_strip_sorted_by_class_score_id(tmp_path):
    import openpyxl

    paths = build_personal_strips(
        _exam(), _score(), _questions(), ResultsConfig(), _config(tmp_path)
    )
    ws = openpyxl.load_workbook(paths[0])["个人成绩单"]
    assert ws.cell(2, 1).value == "高一10班"  # 第一块为高一10班
    assert ws.cell(2, 6).value == 80.0  # S1 总分（降序）
    assert ws.cell(5, 1).value == "高一10班"  # 第二块仍为高一10班（S2）
    assert ws.cell(5, 6).value == 70.0
    assert ws.cell(8, 1).value == "高一11班"  # 第三块为高一11班
    assert ws.cell(8, 6).value == 90.0  # S3 总分


def test_strip_widths_and_bold(tmp_path):
    import openpyxl

    paths = build_personal_strips(
        _exam(), _score(), _questions(), ResultsConfig(), _config(tmp_path)
    )
    ws = openpyxl.load_workbook(paths[0])["个人成绩单"]
    header = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    assert ws.column_dimensions["A"].width == 10  # 班级
    assert ws.column_dimensions["J"].width == 6  # 多选（前10列末列）
    sub_idx = header.index("26(1)") + 1
    assert ws.column_dimensions[chr(64 + sub_idx)].width == 4  # 单独小题列宽
    assert ws.cell(2, 6).font.bold is True  # 总分加粗
    assert ws.cell(2, 1).font.bold is False
