"""Excel 报告与统计导出。

- 每场统计工作簿：statistics/<学期>/<考试名称>.xlsx（多 sheet）
- 跨场汇总报告：reports/<学期>/成绩分析汇总.xlsx（多 sheet）
- 班级成绩汇总：路径已在 storage 预留（要求待定）
"""

from __future__ import annotations

from math import ceil

import pandas as pd
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
from .cleaning import collect_quality_issues
from .config import AnalysisConfig, ExamConfig
from .io_utils import write_excel_report
from .outputs import reports_dir, statistics_excel_path
from .storage import parsed_exam_dir

_HEADER_FONT = XlFont(name="方正小标宋_GBK", size=12)
_DATA_FONT = XlFont(name="宋体", size=11)
_HEADER_ROW_HEIGHT = 20.0
_DATA_BAR_COLOR = "67C487"  # 浅绿色


def _table_border(
    left: bool = True, right: bool = True, top: bool = True, bottom: bool = True
) -> Border:
    """默认细实线边框；某边 False 表示该边无线。"""
    def side(show: bool) -> Side | None:
        return Side(style="thin") if show else None

    return Border(left=side(left), right=side(right), top=side(top), bottom=side(bottom))

_RATIO_COLUMNS = {
    "total_ratio", "平均得分率", "及格率", "优秀率", "占比",
    "正向累计占比", "逆向累计占比",
    "本次得分率", "上次得分率", "得分率变化",
}
_SCORE_COLUMNS = {"total_score", "平均分", "最高分", "最低分", "标准差"}


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
    return str(path)


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
    path = reports_dir(config.output) / semester / "成绩分析汇总.xlsx"
    write_excel_report(sheets, str(path), _formats_for(sheets))
    return str(path)


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
        "单选": cls["单选分"].tolist(),
        "多选": cls["多选分"].tolist(),
    }
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


def _append_average_rows(ws, frame: pd.DataFrame, n: int) -> None:
    """末尾追加 平均(全班)/平均(前半)/平均(后半) 三行（序号+姓名合并单元格）。"""
    numeric_cols = [
        c for c in frame.columns if c not in ("序号", "姓名", "校次", "班次")
    ]
    labels = ["平均(全班)", "平均(前半)", "平均(后半)"]
    halves = [slice(0, n), slice(0, ceil(n / 2)), slice(ceil(n / 2), n)]
    start = len(frame) + 2
    for k, (label, sl) in enumerate(zip(labels, halves)):
        row = start + k
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        label_cell = ws.cell(row=row, column=1, value=label)
        label_cell.font = _DATA_FONT
        for col_name in numeric_cols:
            col_idx = frame.columns.get_loc(col_name) + 1
            avg = frame.iloc[sl][col_name].mean()
            cell = ws.cell(
                row=row,
                column=col_idx,
                value=None if pd.isna(avg) else round(float(avg), 2),
            )
            cell.font = _DATA_FONT


def _apply_sheet_fonts(ws, frame: pd.DataFrame) -> None:
    """表头：方正小标宋_GBK 12；数据：宋体 11（平均行同样宋体 11）。"""
    for cell in ws[1]:
        cell.font = _HEADER_FONT
    for row in ws.iter_rows(min_row=2, max_row=len(frame) + 1):
        for cell in row:
            cell.font = _DATA_FONT


def _apply_column_widths(ws, frame: pd.DataFrame) -> None:
    """列宽：序号6 姓名8 总分6 客观7 主观7 单选5 多选5，题目列 6，校次/班次 5。"""
    n = len(frame.columns)
    widths = []
    for i in range(n):
        if i < 7:
            widths.append([6, 8, 6, 7, 7, 5, 5][i])
        elif i >= n - 2:
            widths.append(5)
        else:
            widths.append(6)
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _apply_alignment(ws, frame: pd.DataFrame) -> None:
    """表头行上下左右居中、行高 20；平均行首格与总分列左右居中。"""
    header_alignment = Alignment(horizontal="center", vertical="center")
    for cell in ws[1]:
        cell.alignment = header_alignment
    ws.row_dimensions[1].height = _HEADER_ROW_HEIGHT

    total_col = frame.columns.get_loc("总分") + 1
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            if cell.column == total_col:
                cell.alignment = Alignment(horizontal="center")

    start = len(frame) + 2
    for r in range(start, start + 3):
        ws.cell(row=r, column=1).alignment = Alignment(horizontal="center")


def _apply_data_bars(ws, frame: pd.DataFrame) -> None:
    """客观分/主观分/单选/多选及小题、大题列设置数据条（渐变浅绿）。

    范围：表头之下到平均行之上（末行 = 倒数第 4 行）；
    数据条最小值/最大值取该列范围内的实际最小值/最大值。
    """
    cols = list(frame.columns)
    start = cols.index("多选") + 1
    end = cols.index("校次")
    bar_cols = ["客观分", "主观分", "单选", "多选"] + cols[start:end]
    last_data_row = ws.max_row - 3
    for col in bar_cols:
        letter = get_column_letter(cols.index(col) + 1)
        rng = f"{letter}2:{letter}{last_data_row}"
        rule = DataBarRule(
            start_type="min",
            start_value=0,
            end_type="max",
            end_value=0,
            color=_DATA_BAR_COLOR,
            showValue=True,
        )
        ws.conditional_formatting.add(rng, rule)


def _apply_table_borders(ws, frame: pd.DataFrame) -> None:
    """表格默认细实线框线；单选|多选之间、同一大题的相邻小题之间取消竖框线。"""
    cols = list(frame.columns)
    n = len(cols)
    remove_left: set[int] = set()
    remove_right: set[int] = set()

    def boundary(a: int, b: int) -> None:
        remove_right.add(a)
        remove_left.add(b)

    boundary(cols.index("单选"), cols.index("多选"))

    q_start = cols.index("多选") + 1
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
            )


def _format_date_cn(date_str: str | None) -> str:
    """日期转中文格式：2026-04-20 -> 2026年04月20日。"""
    if not date_str:
        return ""
    parts = str(date_str).split("-")
    if len(parts) == 3:
        return f"{parts[0]}年{parts[1]}月{parts[2]}日"
    return str(date_str)


def _write_teacher_summary(
    exam: ExamConfig,
    teacher: str,
    group: pd.DataFrame,
    wide: pd.DataFrame,
    big: pd.DataFrame,
    subj_cols: list[str],
    big_cols: list[str],
    exam_dir,
    grade_stats: dict,
) -> str:
    """同一教师所教班级写入一个 Excel，每班一个 sheet。"""
    path = exam_dir / f"{exam.name}_{teacher}_班级成绩汇总.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for class_name, cls in group.groupby("class_name", sort=True):
            frame = _class_frame(cls, wide, big, subj_cols, big_cols)
            frame.to_excel(writer, sheet_name=str(class_name), index=False)
            ws = writer.sheets[str(class_name)]
            _apply_sheet_fonts(ws, frame)
            _append_average_rows(ws, frame, len(cls))
            _apply_column_widths(ws, frame)
            _apply_alignment(ws, frame)
            _apply_data_bars(ws, frame)
            _apply_table_borders(ws, frame)
            _set_header_footer(
                ws, exam, str(class_name), cls["total_score"], grade_stats
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
) -> None:
    """设置 sheet 页眉（左=班级，中=考试名称，右=考试日期）与页脚（左右各两行）。"""
    ws.oddHeader.left.text = class_name
    ws.oddHeader.center.text = exam.name
    ws.oddHeader.right.text = _format_date_cn(exam.date)
    ws.oddHeader.left.font = "微软雅黑,bold"
    ws.oddHeader.left.size = 20
    ws.oddHeader.center.font = "方正小标宋_GBK"
    ws.oddHeader.center.size = 20
    ws.oddHeader.right.size = 14
    ws.oddFooter.left.size = 12

    cls_mean = totals.mean()
    cls_median = totals.median()
    cls_std = totals.std()
    left_footer = (
        f"班级平均分: {_fmt_stat(cls_mean)} (标准差: {_fmt_stat(cls_std)})\n"
        f" 年级平均分: {_fmt_stat(grade_stats['grade_mean'])} "
        f"({_fmt_stat(grade_stats['b_mean'])}|{_fmt_stat(grade_stats['a_mean'])})"
    )
    right_footer = (
        f"班级中位数: {_fmt_stat(cls_median)}\n"
        f"({_fmt_stat(grade_stats['b_median'])}|{_fmt_stat(grade_stats['a_median'])}) "
        f"年级中位数: {_fmt_stat(grade_stats['grade_median'])}"
    )
    ws.oddFooter.left.text = left_footer
    ws.oddFooter.right.text = right_footer


def _roster_check(score: pd.DataFrame, verify_roster: bool) -> list[str]:
    """学生名单核对接口：默认不启用，后续完善。"""
    if not verify_roster:
        return []
    raise NotImplementedError("学生名单核对功能将在后续实现")


def build_class_summaries(
    exam: ExamConfig,
    score: pd.DataFrame,
    questions: pd.DataFrame,
    config: AnalysisConfig,
    verify_roster: bool = False,
) -> list[str]:
    """按任课教师生成班级成绩汇总 Excel，返回输出文件路径列表。

    只保留有成绩的行；未配置教师的班级不生成（check 已 WARN）。
    """
    _roster_check(score, verify_roster)
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
    exam_dir = parsed_exam_dir(config.parsed_dir, exam)
    exam_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for teacher, group in valid.groupby("teacher", sort=True):
        if not teacher:
            continue
        paths.append(
            _write_teacher_summary(
                exam, teacher, group, wide, big, subj_cols, big_cols,
                exam_dir, grade_stats,
            )
        )
    return paths
