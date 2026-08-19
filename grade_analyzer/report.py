"""Excel 报告与统计导出。

- 每场统计工作簿：statistics/<学期>/<考试名称>.xlsx（多 sheet）
- 跨场汇总报告：reports/<学期>/成绩分析汇总.xlsx（多 sheet）
- 班级成绩汇总：路径已在 storage 预留（要求待定）
"""

from __future__ import annotations

from math import ceil

import pandas as pd
from openpyxl import load_workbook
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font as XlFont, Side
from openpyxl.utils import get_column_letter

from .analysis import (
    compute_average_rankings,
    compute_distribution,
    compute_group_comparison,
    compute_rankings,
    compute_subject_stats,
    compute_trends,
)
from .charts import (
    add_comparison_chart,
    add_distribution_chart,
    add_trend_chart,
)
from .consolidate import date_range_suffix
from pathlib import Path

from .cleaning import collect_quality_issues
from .config import AnalysisConfig, ExamConfig
from .io_utils import write_excel_report
from .outputs import reports_dir, statistics_excel_path
from .result_config import ClassSummaryConfig, ResultsConfig


def _table_border(
    left: bool = True,
    right: bool = True,
    top: bool = True,
    bottom: bool = True,
    style: str = "thin",
) -> Border:
    """细实线边框；某边 False 表示该边无线；样式可配置。"""
    def side(show: bool) -> Side | None:
        return Side(style=style) if show else None

    return Border(left=side(left), right=side(right), top=side(top), bottom=side(bottom))

_RATIO_COLUMNS = {
    "total_ratio", "平均得分率", "及格率", "优秀率", "占比",
    "正向累计占比", "逆向累计占比",
    "本次得分率", "上次得分率", "得分率变化", "得分率",
}
_SCORE_COLUMNS = {"total_score", "总分", "平均分", "最高分", "最低分", "标准差"}


def _sheet_formats(df: pd.DataFrame) -> dict[str, str]:
    """按列给出 Excel 数字格式：比率=百分比(2位小数)，分数=1位小数。"""
    return {
        col: (
            "0.00%"
            if col in _RATIO_COLUMNS
            else "0.0"
            if col in _SCORE_COLUMNS
            else None
        )
        for col in df.columns
    }


def _formats_for(
    sheets: dict[str, pd.DataFrame],
) -> dict[str, dict[str, str]]:
    return {name: _sheet_formats(df) for name, df in sheets.items()}


def _stat_sheets(
    score: pd.DataFrame, config: AnalysisConfig
) -> dict[str, pd.DataFrame]:
    """单场统计的五个 sheet。"""
    return {
        "科目统计": compute_subject_stats(score, config),
        "分数段分布": compute_distribution(score, config),
        "个人排名": compute_rankings(score),
        "班级对比": compute_group_comparison(
            score, ["class_level", "class_name"], config
        ),
        "教师对比": compute_group_comparison(score, ["teacher"], config),
    }


def build_exam_statistics(
    exam: ExamConfig, score: pd.DataFrame, config: AnalysisConfig
) -> str:
    """一场考试一个多 sheet Excel 工作簿，返回输出路径。"""
    path = statistics_excel_path(config.output, exam.semester, exam.name)
    sheets = _stat_sheets(score, config)
    write_excel_report(sheets, str(path), _formats_for(sheets))
    _embed_stat_charts(str(path), sheets)
    return str(path)


def _embed_stat_charts(path: str, sheets: dict[str, pd.DataFrame]) -> None:
    """每场统计工作簿内嵌：分数段柱状 + 班级对比 + 教师对比。"""
    wb = load_workbook(path)
    if "分数段分布" in wb.sheetnames:
        add_distribution_chart(wb["分数段分布"], sheets["分数段分布"])
    if "班级对比" in wb.sheetnames:
        add_comparison_chart(
            wb["班级对比"], sheets["班级对比"], "班级", anchor="K2"
        )
    if "教师对比" in wb.sheetnames:
        add_comparison_chart(
            wb["教师对比"], sheets["教师对比"], "教师", anchor="J2"
        )
    wb.save(path)


def build_report(
    config: AnalysisConfig,
    long_df: pd.DataFrame,
    frames: list[tuple[ExamConfig, pd.DataFrame]],
) -> str:
    """生成跨场 Excel 汇总报告，返回输出路径。"""
    sheets: dict[str, pd.DataFrame] = {}
    sheets["科目统计"] = compute_subject_stats(long_df, config)
    sheets["分数段分布"] = compute_distribution(long_df, config)
    sheets["个人排名"] = pd.concat(
        [compute_rankings(score) for _, score in frames], ignore_index=True
    )
    sheets["班级对比"] = compute_group_comparison(
        long_df, ["class_level", "class_name"], config
    )
    sheets["教师对比"] = compute_group_comparison(long_df, ["teacher"], config)
    trends, progress = compute_trends(long_df, config)
    sheets["多场趋势"] = trends
    sheets["学生进退步"] = progress
    quality_frames = [
        collect_quality_issues(score, exam, config) for exam, score in frames
    ]
    sheets["数据质量"] = pd.concat(quality_frames, ignore_index=True)
    sheets["配置说明"] = _config_snapshot(config)

    semester = config.current_semester or (
        frames[0][0].semester if frames else "未指定"
    )
    suffix = date_range_suffix([e for e, _ in frames])
    stem = Path(config.output.excel_name).stem or "成绩分析汇总"
    ext = Path(config.output.excel_name).suffix or ".xlsx"
    name = f"{stem}_{suffix}{ext}" if suffix else f"{stem}{ext}"
    path = reports_dir(config.output) / semester / name
    write_excel_report(sheets, str(path), _formats_for(sheets))
    _embed_report_charts(str(path), sheets)
    return str(path)


def _embed_report_charts(path: str, sheets: dict[str, pd.DataFrame]) -> None:
    """汇总报告内嵌：多场趋势折线图。"""
    wb = load_workbook(path)
    if "多场趋势" in wb.sheetnames:
        add_trend_chart(wb["多场趋势"], sheets["多场趋势"])
    wb.save(path)


def _config_snapshot(config: AnalysisConfig) -> pd.DataFrame:
    rows = [
        ("当前学期", config.current_semester or ""),
        ("默认学校", config.default_school or ""),
        ("及格线得分率", config.pass_ratio),
        ("优秀线得分率", config.excellent_ratio),
        ("分数段上界", ",".join(str(b) for b in config.score_bands)),
        ("规范表目录", config.parsed_dir),
        ("输出目录", config.output.dir),
    ]
    return pd.DataFrame(rows, columns=["配置项", "值"])


def _subjective_pivot(
    questions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    """主观小题与主观大题汇总。

    返回 (小题宽表, 大题汇总宽表, 小题列顺序, 大题列顺序)；
    大题汇总 = 该大题各小题得分之和（如 26 = 26-1 + ... + 26-5）。
    """
    subj = questions[questions["question_type"] == "主观"]
    if subj.empty:
        return pd.DataFrame(), pd.DataFrame(), [], []
    subj = subj.copy()
    # 主观题号可能是纯数字（如配置客观题数后 21/22）或带小题（26-1），统一转字符串
    subj["question_id"] = subj["question_id"].astype(str)
    subj["大题号"] = subj["question_id"].str.split("-").str[0]

    def _qkey(qid: str) -> tuple[int, int]:
        parts = qid.split("-")
        return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)

    wide = subj.pivot_table(
        index="student_id", columns="question_id", values="score", aggfunc="first"
    )
    subj_cols = [str(c) for c in sorted(wide.columns, key=_qkey)]
    wide = wide[subj_cols]

    big = subj.groupby(["student_id", "大题号"])["score"].sum().unstack(fill_value=0)
    big_cols = [str(c) for c in sorted(big.columns, key=int)]
    big = big[big_cols]
    return wide, big, subj_cols, big_cols


def _display_qid(qid: str) -> str:
    """小题题号显示样式：26-1 -> 26(1)（参考文件样式，规范表仍用 26-1）。"""
    if "-" in qid:
        base, sub = qid.split("-", 1)
        return f"{base}({sub})"
    return qid


def _class_frame(
    cls: pd.DataFrame,
    wide: pd.DataFrame,
    big: pd.DataFrame,
    subj_cols: list[str],
    big_cols: list[str],
    type_cols: list[str],
) -> pd.DataFrame:
    """按固定列顺序组装单个班级的明细表（不含平均行）。"""
    cls = cls.sort_values(
        ["total_score", "name", "student_id"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    data = {
        "序号": list(range(1, len(cls) + 1)),
        "姓名": cls["name"].fillna("").tolist(),
        "总分": cls["total_score"].tolist(),
        "客观分": cls["objective_score"].tolist(),
        "主观分": cls["subjective_score"].tolist(),
    }
    for t in type_cols:
        data[t] = cls[f"{t}分"].tolist()
    for col in subj_cols:
        label = _display_qid(col)
        data[label] = (
            cls["student_id"].map(wide[col]).tolist()
            if col in wide.columns
            else [float("nan")] * len(cls)
        )
    for col in big_cols:
        data[col] = (
            cls["student_id"].map(big[col]).tolist()
            if col in big.columns
            else [float("nan")] * len(cls)
        )
    data["校次"] = cls["校次"].tolist()
    data["班次"] = cls["班次"].tolist()
    return pd.DataFrame(data)


def _question_type_cols(cls: pd.DataFrame) -> list[str]:
    """得分表动态题型分列显示名（去掉 分 后缀，排除 客观分/主观分/满分列）。"""
    return [
        c[:-1]
        for c in cls.columns
        if c.endswith("分")
        and not c.endswith("满分")
        and c not in ("客观分", "主观分")
    ]


def _append_average_rows(
    ws, frame: pd.DataFrame, n: int, cs: ClassSummaryConfig
) -> None:
    """末尾追加平均行（序号+姓名合并单元格），标签/小数位/前半口径来自配置。"""
    numeric_cols = [
        c for c in frame.columns if c not in ("序号", "姓名", "校次", "班次")
    ]
    labels = list(cs.average_rows.labels)
    front = ceil(n / 2) if cs.average_rows.half_ceil else n // 2
    halves = [slice(0, n), slice(0, front), slice(front, n)]
    avg_font = XlFont(
        name=cs.fonts.average.name,
        size=cs.fonts.average.size,
        bold=cs.fonts.average.bold,
    )
    start = len(frame) + 2
    for k, (label, sl) in enumerate(zip(labels, halves)):
        row = start + k
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        label_cell = ws.cell(row=row, column=1, value=label)
        label_cell.font = avg_font
        for col_name in numeric_cols:
            col_idx = frame.columns.get_loc(col_name) + 1
            avg = frame.iloc[sl][col_name].mean()
            cell = ws.cell(
                row=row,
                column=col_idx,
                value=None if pd.isna(avg) else round(float(avg), cs.average_rows.decimals),
            )
            cell.font = avg_font


def _apply_sheet_fonts(ws, frame: pd.DataFrame, cs: ClassSummaryConfig) -> None:
    """表头/数据字体来自配置。"""
    header_font = XlFont(
        name=cs.fonts.header.name, size=cs.fonts.header.size, bold=cs.fonts.header.bold
    )
    data_font = XlFont(
        name=cs.fonts.data.name, size=cs.fonts.data.size, bold=cs.fonts.data.bold
    )
    for cell in ws[1]:
        cell.font = header_font
    for row in ws.iter_rows(min_row=2, max_row=len(frame) + 1):
        for cell in row:
            cell.font = data_font


def _apply_column_widths(ws, frame: pd.DataFrame, cs: ClassSummaryConfig) -> None:
    """列宽来自配置：前7列 / 题目列 / 末2列。"""
    n = len(frame.columns)
    first7 = cs.column_widths.first7
    last2 = cs.column_widths.last2
    widths = []
    for i in range(n):
        if i < 7:
            widths.append(first7[i])
        elif i >= n - 2:
            widths.append(last2[i - (n - 2)])
        else:
            widths.append(cs.column_widths.question_cols)
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _apply_alignment(ws, frame: pd.DataFrame, cs: ClassSummaryConfig) -> None:
    """对齐来自配置：表头（center_center）、总分列、平均行首格。"""
    header_align = cs.alignment.header
    for cell in ws[1]:
        if header_align == "center_center":
            cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = cs.row_height.header

    if cs.alignment.total_col == "center":
        total_col = frame.columns.get_loc("总分") + 1
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
            for cell in row:
                if cell.column == total_col:
                    cell.alignment = Alignment(horizontal="center")

    if cs.alignment.average_label == "center":
        start = len(frame) + 2
        for r in range(start, start + 3):
            ws.cell(row=r, column=1).alignment = Alignment(horizontal="center")


def _apply_data_bars(
    ws, frame: pd.DataFrame, cs: ClassSummaryConfig, type_cols: list[str]
) -> None:
    """客观/主观/题型分列及题目列数据条（启用与颜色来自配置）。"""
    if not cs.data_bar.enabled:
        return
    cols = list(frame.columns)
    start = 5 + len(type_cols)
    end = cols.index("校次")
    bar_cols = ["客观分", "主观分"] + type_cols + cols[start:end]
    last_data_row = ws.max_row - 3
    for col in bar_cols:
        letter = get_column_letter(cols.index(col) + 1)
        rng = f"{letter}2:{letter}{last_data_row}"
        rule = DataBarRule(
            start_type="min",
            start_value=0,
            end_type="max",
            end_value=0,
            color=cs.data_bar.color,
            showValue=True,
        )
        ws.conditional_formatting.add(rng, rule)


def _apply_table_borders(
    ws, frame: pd.DataFrame, cs: ClassSummaryConfig, type_cols: list[str]
) -> None:
    """表格框线来自配置；题型分列间与同大题小题去竖线可开关。"""
    if not cs.borders.enabled:
        return
    cols = list(frame.columns)
    n = len(cols)
    remove_left: set[int] = set()
    remove_right: set[int] = set()

    def boundary(a: int, b: int) -> None:
        remove_right.add(a)
        remove_left.add(b)

    if cs.borders.remove_single_multi and "单选" in cols and "多选" in cols:
        boundary(cols.index("单选"), cols.index("多选"))
    if cs.borders.remove_same_big:
        q_start = 5 + len(type_cols)
        q_end = cols.index("校次")
        sub_idx = [i for i in range(q_start, q_end) if "(" in cols[i]]
        for a, b in zip(sub_idx, sub_idx[1:]):
            if cols[a].split("(")[0] == cols[b].split("(")[0]:
                boundary(a, b)

    for r in range(1, ws.max_row + 1):
        for i in range(n):
            cell = ws.cell(row=r, column=i + 1)
            cell.border = _table_border(
                left=i not in remove_left,
                right=i not in remove_right,
                top=True,
                bottom=True,
                style=cs.borders.style,
            )


def _format_date_cn(date_str: str | None, fmt: str = "%Y年%m月%d日") -> str:
    """按格式转换日期：2026-04-20 -> 2026年04月20日。"""
    if not date_str:
        return ""
    try:
        from datetime import datetime

        return datetime.strptime(str(date_str), "%Y-%m-%d").strftime(fmt)
    except ValueError:
        return str(date_str)


def _hf_font(fs) -> str | None:
    """页眉页脚字体字符串（如 微软雅黑,bold）。"""
    name = (fs.name or "").strip()
    if not name:
        return None
    return f"{name},bold" if fs.bold else name


def _write_class_summary_file(
    exam: ExamConfig,
    filename: str,
    class_groups: list[tuple[str, pd.DataFrame]],
    wide: pd.DataFrame,
    big: pd.DataFrame,
    subj_cols: list[str],
    big_cols: list[str],
    exam_dir,
    grade_stats: dict,
    cs: ClassSummaryConfig,
) -> str:
    """一个班级汇总文件（每班一个 sheet）。"""
    path = exam_dir / filename
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for class_name, cls in class_groups:
            type_cols = _question_type_cols(cls)
            frame = _class_frame(cls, wide, big, subj_cols, big_cols, type_cols)
            frame.to_excel(writer, sheet_name=str(class_name), index=False)
            ws = writer.sheets[str(class_name)]
            _apply_sheet_fonts(ws, frame, cs)
            _append_average_rows(ws, frame, len(cls), cs)
            _apply_column_widths(ws, frame, cs)
            _apply_alignment(ws, frame, cs)
            _apply_data_bars(ws, frame, cs, type_cols)
            _apply_table_borders(ws, frame, cs, type_cols)
            _set_header_footer(
                ws, exam, str(class_name), cls["total_score"], grade_stats, cs
            )
    return str(path)


def _fmt_stat(value: float | None) -> str:
    """统计值格式化为 2 位小数；缺失显示 --。"""
    if value is None or pd.isna(value):
        return "--"
    return f"{value:.2f}"


def _set_header_footer(
    ws,
    exam: ExamConfig,
    class_name: str,
    totals: pd.Series,
    grade_stats: dict,
    cs: ClassSummaryConfig,
) -> None:
    """设置 sheet 页眉（左=班级，中=考试名称，右=考试日期）与页脚（左右各两行）。"""
    ws.oddHeader.left.text = class_name
    ws.oddHeader.center.text = exam.name
    ws.oddHeader.right.text = _format_date_cn(exam.date, cs.header.date_format)
    ws.oddHeader.left.font = _hf_font(cs.header.left_font)
    ws.oddHeader.left.size = cs.header.left_font.size
    ws.oddHeader.center.font = _hf_font(cs.header.center_font)
    ws.oddHeader.center.size = cs.header.center_font.size
    ws.oddHeader.right.font = _hf_font(cs.header.right_font)
    ws.oddHeader.right.size = cs.header.right_font.size
    ws.oddFooter.left.size = cs.footer.left_font_size

    cls_mean = totals.mean()
    cls_median = totals.median()
    cls_std = totals.std()
    colon = ":" if cs.footer.half_width else "："
    lp, rp = ("(", ")") if cs.footer.half_width else ("（", "）")
    left_footer = (
        f"班级平均分{colon} {_fmt_stat(cls_mean)} {lp}标准差{colon} {_fmt_stat(cls_std)}{rp}\n"
        f" 年级平均分{colon} {_fmt_stat(grade_stats['grade_mean'])} "
        f"{lp}{_fmt_stat(grade_stats['b_mean'])}|{_fmt_stat(grade_stats['a_mean'])}{rp}"
    )
    right_footer = (
        f"班级中位数{colon} {_fmt_stat(cls_median)}\n"
        f"{lp}{_fmt_stat(grade_stats['b_median'])}|{_fmt_stat(grade_stats['a_median'])}{rp} "
        f"年级中位数{colon} {_fmt_stat(grade_stats['grade_median'])}"
    )
    ws.oddFooter.left.text = left_footer
    ws.oddFooter.right.text = right_footer


def build_class_summaries(
    exam: ExamConfig,
    score: pd.DataFrame,
    questions: pd.DataFrame,
    config: AnalysisConfig,
    results_cfg: ResultsConfig,
    verify_roster: bool = False,
) -> list[str]:
    """按配置生成班级成绩汇总 Excel，返回输出文件路径列表。

    只保留有成绩的行；未配置教师的班级不生成（check 已 WARN）。
    """
    if verify_roster:
        from .roster import verify_exam

        verify_exam(exam, score, config)
    valid = score[score["total_score"].notna()].copy()
    if valid.empty:
        return []
    wide, big, subj_cols, big_cols = _subjective_pivot(questions)
    per_class = valid.groupby("class_name")["total_score"].agg(
        ["mean", "median", "std"]
    )
    level_map = {
        cls: info.level
        for cls in per_class.index
        if (info := config.class_info(exam.semester, cls)) is not None
    }

    def _level_stat(level: str, col: str, fn) -> float | None:
        idx = [c for c in per_class.index if level_map.get(c) == level]
        vals = per_class.loc[idx, col] if idx else pd.Series(dtype=float)
        return fn(vals) if len(vals) else None

    grade_stats = {
        "grade_mean": per_class["mean"].mean(),
        "grade_median": per_class["median"].median(),
        "b_mean": _level_stat("B", "mean", lambda s: s.mean()),
        "a_mean": _level_stat("A", "mean", lambda s: s.mean()),
        "b_median": _level_stat("B", "median", lambda s: s.median()),
        "a_median": _level_stat("A", "median", lambda s: s.median()),
    }
    cs = results_cfg.class_summary
    exam_dir = Path(config.results_dir) / (exam.semester or "") / exam.name
    exam_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    if cs.group_by_teacher:
        for teacher, group in valid.groupby("teacher", sort=True):
            if not teacher:
                continue
            groups = [(cn, g) for cn, g in group.groupby("class_name", sort=True)]
            paths.append(
                _write_class_summary_file(
                    exam, f"{exam.name}_{teacher}_班级成绩汇总.xlsx",
                    groups, wide, big, subj_cols, big_cols,
                    exam_dir, grade_stats, cs,
                )
            )
    if cs.all_classes_summary:
        groups = [(cn, g) for cn, g in valid.groupby("class_name", sort=True)]
        paths.append(
            _write_class_summary_file(
                exam, f"{exam.name}_全部班级_班级成绩汇总.xlsx",
                groups, wide, big, subj_cols, big_cols,
                exam_dir, grade_stats, cs,
            )
        )
    return paths
