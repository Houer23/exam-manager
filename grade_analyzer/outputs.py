"""输出目录组织：按输出类型在 output 下分类分文件夹存储。

类型：
- merged:     合并长表/宽表
- reports:    Excel 汇总报告
- statistics: 统计结果（按学期子目录，单场文件带考试名称）
- charts:     图表
- quality:    质量报告
- run-info:   配置快照/运行信息
"""

from __future__ import annotations

from pathlib import Path

from .config import OutputConfig

OUTPUT_TYPES = ["merged", "reports", "statistics", "charts", "quality", "run-info"]


def type_dir(output: OutputConfig, out_type: str) -> Path:
    """返回某输出类型在 output 根目录下的子目录。"""
    if out_type not in OUTPUT_TYPES:
        raise ValueError(f"未知输出类型: {out_type}（可选 {OUTPUT_TYPES}）")
    return Path(output.dir) / out_type


def merged_dir(output: OutputConfig) -> Path:
    return type_dir(output, "merged")


def reports_dir(output: OutputConfig) -> Path:
    return type_dir(output, "reports")


def statistics_dir(output: OutputConfig, semester: str | None) -> Path:
    """统计结果目录：statistics/<学期>/（无学期则直接 statistics/）。"""
    base = type_dir(output, "statistics")
    return base / semester if semester else base


def statistics_path(
    output: OutputConfig, semester: str | None, exam_name: str, content: str
) -> Path:
    """单场统计文件路径：statistics/<学期>/<考试名称>_<内容>.csv。"""
    return statistics_dir(output, semester) / f"{exam_name}_{content}.csv"


def statistics_excel_path(
    output: OutputConfig, semester: str | None, exam_name: str
) -> Path:
    """单场统计工作簿路径：statistics/<学期>/<考试名称>.xlsx。"""
    return statistics_dir(output, semester) / f"{exam_name}.xlsx"
