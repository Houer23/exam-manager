"""数据统计图（组合图 PNG）的单元测试。"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from grade_analyzer.chart_config import ChartsConfig
from grade_analyzer.config import ChartOutputOverride, ExamConfig, OutputConfig
from grade_analyzer.dist_charts import (
    _chart_out_dir,
    _order_groups,
    _resolve_output_layout,
    _resolve_series_layout,
    build_all_charts,
    build_exam_series_chart,
    compute_class_metrics,
)


def _score_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "student_id": ["S1", "S2", "S3", "S4", "S5", "S6"],
            "class_name": ["高一10班", "高一10班", "高一10班", "高一11班", "高一11班", "高一11班"],
            "class_level": ["A", "A", "A", "B", "B", "B"],
            "teacher": ["柯", "柯", "柯", "叶", "叶", "叶"],
            "total_score": [80.0, 90.0, 70.0, 60.0, 50.0, 100.0],
        }
    )


def test_compute_class_metrics():
    metrics = compute_class_metrics(_score_df())
    by_class = metrics.set_index("班级")
    assert by_class.loc["高一10班", "平均分"] == 80.0
    assert by_class.loc["高一10班", "中位数"] == 80.0
    assert by_class.loc["高一11班", "Q1"] == 55.0
    assert by_class.loc["高一11班", "Q3"] == 80.0
    assert by_class.loc["高一10班", "层次"] == "A"
    assert by_class.loc["高一11班", "教师"] == "叶"


def test_chart_out_dir_layout_switches(tmp_path):
    output = OutputConfig(dir=str(tmp_path / "out"))
    cfg = ChartsConfig(
        output_dir="",
        folder_semester=True,
        folder_exam=True,
        folder_type=True,
        type_folder_name="统计图",
    )
    layout = _resolve_output_layout(cfg)
    assert _chart_out_dir(
        layout, output, semester="高一第二学期", exam_name="高一下期中联考"
    ) == Path(
        tmp_path / "out" / "charts" / "高一第二学期" / "高一下期中联考" / "统计图"
    )
    # 自定义根目录且关闭全部层级：直接落到自定义目录
    cfg.output_dir = str(tmp_path / "图片")
    cfg.folder_semester = False
    cfg.folder_exam = False
    cfg.folder_type = False
    layout = _resolve_output_layout(cfg)
    assert _chart_out_dir(
        layout, output, semester="高一第二学期", exam_name="高一下期中联考"
    ) == Path(tmp_path / "图片")
    # 自定义“统计图”文件夹名
    cfg.folder_semester = True
    cfg.folder_type = True
    cfg.type_folder_name = "统计图表"
    layout = _resolve_output_layout(cfg)
    assert _chart_out_dir(layout, output, semester="高一第二学期") == Path(
        tmp_path / "图片" / "高一第二学期" / "统计图表"
    )


def test_exam_charts_override_output_layout(tmp_path):
    output = OutputConfig(dir=str(tmp_path / "out"))
    cfg = ChartsConfig(
        output_dir=str(tmp_path / "全局图片"),
        folder_semester=True,
        folder_exam=True,
        folder_type=True,
        type_folder_name="全局统计",
    )
    # 未设置：使用全局
    exam = ExamConfig(name="考试", semester="高一第二学期", subject="地理")
    layout = _resolve_output_layout(cfg, exam)
    assert layout.output_dir == str(tmp_path / "全局图片")
    assert layout.type_folder_name == "全局统计"
    # 空字符串 output_dir：回退默认目录（忽略全局自定义）
    exam.charts = ChartOutputOverride(output_dir="")
    layout = _resolve_output_layout(cfg, exam)
    assert layout.output_dir == ""
    assert _chart_out_dir(
        layout, output, semester="高一第二学期", exam_name="考试"
    ) == Path(tmp_path / "out" / "charts" / "高一第二学期" / "考试" / "全局统计")
    # 非空覆盖整套输出配置
    exam.charts = ChartOutputOverride(
        output_dir=str(tmp_path / "考试图片"),
        folder_semester=False,
        folder_exam=True,
        folder_type=True,
        type_folder_name="统计图表",
    )
    layout = _resolve_output_layout(cfg, exam)
    assert _chart_out_dir(
        layout, output, semester="高一第二学期", exam_name="考试"
    ) == Path(tmp_path / "考试图片" / "考试" / "统计图表")


def test_series_layout_subject_rule(tmp_path):
    cfg = ChartsConfig(
        output_dir="",
        folder_semester=True,
        folder_exam=True,
        folder_type=True,
        type_folder_name="统计图",
    )
    geo = [
        ExamConfig(name="地理A", semester="高一第二学期", subject="地理"),
        ExamConfig(name="地理B", semester="高一第二学期", subject="地理"),
    ]
    layout = _resolve_series_layout(cfg, geo)
    assert layout.folder_semester is True
    assert layout.folder_exam is False
    assert layout.folder_type is False
    with pytest.raises(ValueError, match="同一学科"):
        _resolve_series_layout(
            cfg,
            [
                ExamConfig(name="地理A", semester="高一第二学期", subject="地理"),
                ExamConfig(name="化学B", semester="高一第二学期", subject="化学"),
            ],
        )


def test_build_all_charts(tmp_path):
    config = OutputConfig(dir=str(tmp_path / "out"))
    exam = ExamConfig(
        name="测试", semester="高一第二学期", full_score=100.0,
        date="2026-04-20",
    )
    paths = build_all_charts(exam, _score_df(), ChartsConfig(), config)
    assert len(paths) == 2
    for p in paths:
        assert Path(p).is_file()
        assert Path(p).stat().st_size > 0
    assert (tmp_path / "out" / "charts" / "高一第二学期" / "按层次_20260420_测试.png").is_file()
    assert (tmp_path / "out" / "charts" / "高一第二学期" / "按教师_20260420_测试.png").is_file()


def test_order_groups_by_avg_metric():
    """组间按各组平均指标降序（与组内方向一致），而非按组名。"""
    df = pd.DataFrame(
        {
            "student_id": ["S1", "S2", "S3", "S4", "S5", "S6"],
            "class_name": ["高一10班"] * 3 + ["高一11班"] * 3,
            "class_level": ["A"] * 3 + ["B"] * 3,
            "teacher": ["柯"] * 3 + ["叶"] * 3,
            "total_score": [40.0, 50.0, 60.0, 80.0, 90.0, 100.0],
        }
    )
    metrics = compute_class_metrics(df)
    # 组内排序指标为中位数：A=50、B=90 → 组间降序应为 [B, A]（组名排序为 [A, B]）
    assert _order_groups(metrics, "层次", "中位数") == ["B", "A"]


def test_build_exam_series_chart(tmp_path):
    from grade_analyzer.config import ExamConfig

    config = OutputConfig(dir=str(tmp_path / "out"))
    exams = [
        ExamConfig(
            name="A", short_name="限时练一", semester="高一第二学期",
            date="2026-03-25", full_score=100.0,
        ),
        ExamConfig(
            name="B", short_name="期中联考", semester="高一第二学期",
            date="2026-04-20", full_score=100.0,
        ),
    ]

    def _score(base):
        return pd.DataFrame(
            {
                "student_id": ["S1", "S2", "S3"],
                "class_name": ["高一10班"] * 3,
                "total_score": [base, base + 10, base + 20],
            }
        )

    path = build_exam_series_chart(
        exams, [_score(60.0), _score(70.0)], ["高一10班"], ChartsConfig(), config
    )
    assert path.endswith("按班级_20260325-20260420_高一10班.png")
    assert Path(path).is_file()


def test_build_exam_series_chart_multi_class(tmp_path):
    from grade_analyzer.config import ExamConfig

    config = OutputConfig(dir=str(tmp_path / "out"))
    exams = [
        ExamConfig(
            name="A", short_name="限时练一", semester="高一第二学期",
            date="2026-03-25", full_score=100.0,
        ),
        ExamConfig(
            name="B", short_name="期中联考", semester="高一第二学期",
            date="2026-04-20", full_score=100.0,
        ),
    ]

    def _score(base, cls):
        return pd.DataFrame(
            {
                "student_id": ["S1", "S2", "S3"],
                "class_name": [cls] * 3,
                "total_score": [base, base + 10, base + 20],
            }
        )

    path = build_exam_series_chart(
        exams,
        [_score(60.0, "高一10班"), _score(70.0, "高一11班")],
        ["高一10班", "高一11班"],
        ChartsConfig(),
        config,
    )
    assert path.endswith("按班级_20260325-20260420_高一10、11班.png")
    assert Path(path).is_file()


def test_build_exam_series_chart_skips_missing_class(tmp_path):
    """某班级在所有考试中都缺失时跳过该班，不报错。"""
    from grade_analyzer.config import ExamConfig

    config = OutputConfig(dir=str(tmp_path / "out"))
    exams = [
        ExamConfig(
            name="A", short_name="限时练一", semester="高一第二学期",
            date="2026-03-25", full_score=100.0,
        ),
        ExamConfig(
            name="B", short_name="期中联考", semester="高一第二学期",
            date="2026-04-20", full_score=100.0,
        ),
    ]
    score = pd.DataFrame(
        {
            "student_id": ["S1", "S2", "S3"],
            "class_name": ["高一10班"] * 3,
            "total_score": [60.0, 70.0, 80.0],
        }
    )
    # 高一11班在两场考试中都无数据 → 被跳过，图仍生成
    path = build_exam_series_chart(
        exams, [score, score], ["高一10班", "高一11班"], ChartsConfig(), config
    )
    assert path.endswith("按班级_20260325-20260420_高一10、11班.png")
    assert Path(path).is_file()


def test_class_label_format():
    from grade_analyzer.dist_charts import _class_label

    assert _class_label(["高一13班"]) == "高一13班"  # 单班级用全称
    assert _class_label(["高一10班", "高一11班"]) == "高一10、11班"
    assert _class_label(["高一10班", "高一13班", "高一16班"]) == "高一10、13、16班"
