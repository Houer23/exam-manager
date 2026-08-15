"""数据统计图（组合图 PNG）的单元测试。"""

from pathlib import Path

import numpy as np
import pandas as pd

from grade_analyzer.chart_config import ChartsConfig
from grade_analyzer.config import ExamConfig, OutputConfig
from grade_analyzer.dist_charts import build_all_charts, compute_class_metrics


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


def test_build_all_charts(tmp_path):
    config = OutputConfig(dir=str(tmp_path / "out"))
    exam = ExamConfig(
        name="测试", semester="高一第二学期", full_score=100.0
    )
    paths = build_all_charts(exam, _score_df(), ChartsConfig(), config)
    assert len(paths) == 2
    for p in paths:
        assert Path(p).is_file()
        assert Path(p).stat().st_size > 0
    assert (tmp_path / "out" / "charts" / "高一第二学期" / "测试_按层次.png").is_file()
    assert (tmp_path / "out" / "charts" / "高一第二学期" / "测试_按教师.png").is_file()
