"""数据读取与写出（底层工具）。

适配器负责把原始格式解析为规范表；
本模块只提供底层 Excel/CSV 读取与多 sheet 写出工具。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

def read_raw_sheet(path: str, sheet: str | None = None) -> pd.DataFrame:
    """读取原始 Excel/CSV 的指定 sheet（默认第一个），不做表头处理。"""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"成绩文件不存在: {p}")
    ext = p.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(p, header=None, dtype=object)
    if ext in {".xlsx", ".xls"}:
        return pd.read_excel(p, sheet_name=0 if sheet is None else sheet, header=None)
    raise ValueError(f"不支持的文件扩展名: {ext}（支持 .xlsx/.xls/.csv）")


def write_parsed_table(df: pd.DataFrame, path: str, fmt: str = "csv") -> None:
    """按指定格式写规范表（当前实现 csv，接口保留扩展，如 parquet）。"""
    if fmt != "csv":
        raise ValueError(f"不支持的规范表格式: {fmt}（当前支持 csv）")
    df.to_csv(path, index=False, encoding="utf-8-sig")


def read_parsed_table(path: str, fmt: str = "csv") -> pd.DataFrame:
    """按指定格式读规范表。"""
    if fmt != "csv":
        raise ValueError(f"不支持的规范表格式: {fmt}（当前支持 csv）")
    return pd.read_csv(path, encoding="utf-8-sig")


def write_excel_report(
    data: dict[str, pd.DataFrame],
    path: str,
    formats: dict[str, dict[str, str]] | None = None,
) -> str:
    """将多个 DataFrame 按 sheet 写入 Excel；formats 为 {sheet: {列: 数字格式}}。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(p, engine="openpyxl") as writer:
        for sheet_name, df in data.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        if formats:
            for sheet_name, col_formats in formats.items():
                ws = writer.sheets.get(sheet_name)
                if ws is None or sheet_name not in data:
                    continue
                df = data[sheet_name]
                for col_idx, col_name in enumerate(df.columns, start=1):
                    fmt = col_formats.get(col_name)
                    if not fmt:
                        continue
                    for row in range(2, len(df) + 2):
                        ws.cell(row=row, column=col_idx).number_format = fmt
    return str(p)
