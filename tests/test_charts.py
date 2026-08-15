"""图表（Excel 内嵌）的单元测试。"""

import pandas as pd
from openpyxl import Workbook, load_workbook

from grade_analyzer.charts import (
    add_comparison_chart,
    add_distribution_chart,
    add_trend_chart,
)


def _write_sheet(wb, name: str, df: pd.DataFrame) -> None:
    ws = wb.create_sheet(name)
    ws.append(list(df.columns))
    for _, row in df.iterrows():
        ws.append([None if pd.isna(v) else v for v in row.tolist()])
    return ws


def test_add_distribution_chart(tmp_path):
    wb = Workbook()
    wb.remove(wb.active)
    dist = pd.DataFrame(
        {
            "考试名称": ["期中"] * 3,
            "科目": ["地理"] * 3,
            "分数段": ["90+", "80-89", "<60"],
            "人数": [10, 20, 5],
        }
    )
    ws = _write_sheet(wb, "分数段分布", dist)
    add_distribution_chart(ws, dist)
    path = tmp_path / "a.xlsx"
    wb.save(path)
    wb2 = load_workbook(path)
    charts = wb2["分数段分布"]._charts
    assert len(charts) == 1
    assert charts[0].type == "col"
    assert "分数段分布" in str(charts[0].title)


def test_add_comparison_chart(tmp_path):
    wb = Workbook()
    wb.remove(wb.active)
    comp = pd.DataFrame(
        {
            "考试名称": ["期中"] * 2,
            "teacher": ["柯", "叶"],
            "平均得分率": [0.6, 0.7],
        }
    )
    ws = _write_sheet(wb, "教师对比", comp)
    add_comparison_chart(ws, comp, "teacher")
    path = tmp_path / "b.xlsx"
    wb.save(path)
    wb2 = load_workbook(path)
    charts = wb2["教师对比"]._charts
    assert len(charts) == 1
    assert charts[0].type == "bar"


def test_add_trend_chart(tmp_path):
    wb = Workbook()
    wb.remove(wb.active)
    trends = pd.DataFrame(
        {
            "考试名称": ["周测", "联考"],
            "科目": ["地理", "地理"],
            "日期": ["2026-03-25", "2026-04-20"],
            "考生数": [403, 379],
            "平均得分率": [0.579, 0.555],
            "及格率": [0.484, 0.380],
            "优秀率": [0.0, 0.003],
        }
    )
    ws = _write_sheet(wb, "多场趋势", trends)
    add_trend_chart(ws, trends)
    path = tmp_path / "c.xlsx"
    wb.save(path)
    wb2 = load_workbook(path)
    charts = wb2["多场趋势"]._charts
    assert len(charts) == 1
    assert "lineChart" in charts[0].tagname
