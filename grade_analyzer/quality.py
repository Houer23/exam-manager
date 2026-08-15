"""质量结果落盘（output/quality/）。

- 数据质量.xlsx：多 sheet Excel，每场考试一个 sheet（一次写入，避免 IO 冲突）；
- check_<考试名称>.csv / check_汇总.csv：check 校验报告。
文件被占用（如 Excel 打开）时提示并跳过，不中断主流程。
"""

from __future__ import annotations

import pandas as pd

from .config import AnalysisConfig
from .io_utils import write_excel_report
from .outputs import type_dir


def write_quality_excel(
    config: AnalysisConfig, sheets: dict[str, pd.DataFrame]
) -> str | None:
    """多 sheet Excel 数据质量清单（每场考试一个 sheet），返回路径或 None。"""
    quality_dir = type_dir(config.output, "quality")
    quality_dir.mkdir(parents=True, exist_ok=True)
    path = quality_dir / "数据质量.xlsx"
    try:
        write_excel_report(sheets, str(path))
    except PermissionError as exc:
        print(f"[质量] 数据质量.xlsx 写入失败（文件可能被占用）: {exc}")
        return None
    return str(path)


def write_check_reports(
    config: AnalysisConfig,
    checks_by_exam: dict[str, list[tuple[str, str, str]]],
) -> list[str]:
    """check 报告落盘：每场 check_<考试名称>.csv + check_汇总.csv，返回已写路径。"""
    quality_dir = type_dir(config.output, "quality")
    quality_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    summary_rows: list[dict] = []

    for exam_name, checks in checks_by_exam.items():
        df = pd.DataFrame(checks, columns=["检查项", "状态", "说明"])
        p = quality_dir / f"check_{exam_name}.csv"
        try:
            df.to_csv(p, index=False, encoding="utf-8-sig")
            paths.append(str(p))
        except PermissionError as exc:
            print(f"[质量] {p.name} 写入失败（文件可能被占用）: {exc}")
        statuses = df["状态"].value_counts().to_dict()
        summary_rows.append(
            {
                "考试名称": exam_name,
                "检查项数": len(checks),
                "FAIL数": statuses.get("FAIL", 0),
                "WARN数": statuses.get("WARN", 0),
            }
        )

    summary = pd.DataFrame(
        summary_rows, columns=["考试名称", "检查项数", "FAIL数", "WARN数"]
    )
    sp = quality_dir / "check_汇总.csv"
    try:
        summary.to_csv(sp, index=False, encoding="utf-8-sig")
        paths.append(str(sp))
    except PermissionError as exc:
        print(f"[质量] {sp.name} 写入失败（文件可能被占用）: {exc}")
    return paths
