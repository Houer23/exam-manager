"""个人成绩单生成。

每个学生一个"成绩条"（表头+数据 2 行，条间空行）；
范围由 config/results/config.yaml 的 personal.scope 决定；
样式按参考文件（Calibri 11、行高 20、参考列宽、纵向打印）。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

from .config import AnalysisConfig, ExamConfig
from .consolidate import date_range_suffix
from .report import _display_qid, _subjective_pivot
from .result_config import ResultsConfig

_PAPER_SIZE = {"A4": 9, "A3": 8, "Letter": 1}
_MERGED_COLS = [
    "班级", "姓名", "考试", "班次", "校次",
    "总分", "客观分", "主观分", "单选", "多选", "主观题",
]


def _teacher_sets(config: AnalysisConfig, exam: ExamConfig) -> dict[str, set[str]]:
    """当前学期+科目范围内，教师名 -> 任教班级集合。"""
    tm = config.teacher_maps.get((exam.semester, exam.subject))
    by_teacher: dict[str, set[str]] = {}
    if not tm:
        return by_teacher
    for cls, code in tm.class_teachers.items():
        name = tm.teacher_names.get(code, code)
        by_teacher.setdefault(name, set()).add(cls)
    return by_teacher


def _label_for(
    classes: set[str],
    all_classes: set[str],
    teacher_sets: dict[str, set[str]],
) -> str:
    if classes == all_classes:
        return "全部班级"
    for teacher, tset in teacher_sets.items():
        if classes == tset:
            return teacher
    return "自定义"


def _resolve_teacher(entry: str, teacher_names: dict[str, str]) -> str:
    """教师代号（A/B/C）转教师名称；已是名称则原样返回；无效则报错。"""
    if entry in teacher_names:
        return teacher_names[entry]
    if entry in set(teacher_names.values()):
        return entry
    raise ValueError(
        f"教师配置无效: {entry!r}（应为教师代号 A/B/C... 或教师名称）"
    )


def _build_strip_rows(
    valid: pd.DataFrame,
    exam: ExamConfig,
    wide: pd.DataFrame,
    big: pd.DataFrame,
    subj_cols: list[str],
    big_cols: list[str],
    classes: set[str],
    cfg: ResultsConfig,
) -> tuple[list[str], list[list[object]], list[float]]:
    """构建 表头+数据（每学生一组，含空行），返回 (列名, 行列表, 列宽)。"""
    p = cfg.personal
    wide_s = wide.copy()
    wide_s.index = wide_s.index.astype(str)
    big_s = big.copy()
    big_s.index = big_s.index.astype(str)
    subj_by_base: dict[str, list[str]] = {}
    for c in subj_cols:
        subj_by_base.setdefault(c.split("-")[0], []).append(c)
    sub = valid[valid["class_name"].isin(classes)].copy()
    sub = sub.sort_values(
        ["class_name", "total_score", "student_id"],
        ascending=[True, not p.sort_by_score_desc, True],
    )

    cols = ["班级", "姓名", "考试", "班次", "校次", "总分", "客观分", "主观分", "单选", "多选"]
    cw = p.layout.column_widths
    widths = list(cw["first10"])
    if exam.question_display == "merged":
        merged_cols = [f"{p.merged_prefix}{b}{p.merged_suffix}" for b in big_cols]
        cols += merged_cols
        widths += [cw["merged_question_cols"]] * len(merged_cols)
    else:
        sub_disp = [_display_qid(c) for c in subj_cols]
        cols += sub_disp
        widths += [cw["split_question_cols"]] * len(sub_disp)
    if exam.show_big_questions:
        big_disp = [f"{p.big_score_prefix}{b}{p.big_score_suffix}" for b in big_cols]
        cols += big_disp
        widths += [cw["big_question_cols"]] * len(big_disp)

    rows: list[list[object]] = []
    for _, srow in sub.iterrows():
        sid = str(srow["student_id"])
        data = [
            srow["class_name"],
            srow["name"] if not pd.isna(srow["name"]) else "",
            exam.effective_short_name,
            srow["班次"],
            srow["校次"],
            srow["total_score"],
            srow["objective_score"],
            srow["subjective_score"],
            srow["单选分"],
            srow["多选分"],
        ]
        if exam.question_display == "merged":
            for base, subs in subj_by_base.items():
                vals = [
                    wide_s.loc[sid, c] if sid in wide_s.index else None
                    for c in subs
                ]
                data.append(
                    "|".join("" if pd.isna(v) else str(int(v)) for v in vals)
                )
        else:
            for c in subj_cols:
                data.append(wide_s.loc[sid, c] if sid in wide_s.index else None)
        if exam.show_big_questions:
            for c in big_cols:
                data.append(big_s.loc[sid, c] if sid in big_s.index else None)
        rows.append(list(cols))  # 表头
        rows.append(data)
        for _ in range(p.layout.blank_rows_between):
            rows.append([None] * len(cols))
    return cols, rows, widths


def _write_strip_file(
    exam: ExamConfig,
    valid: pd.DataFrame,
    wide: pd.DataFrame,
    big: pd.DataFrame,
    subj_cols: list[str],
    big_cols: list[str],
    classes: set[str],
    label: str,
    cfg: ResultsConfig,
    config: AnalysisConfig,
) -> str:
    p = cfg.personal
    out_dir = Path(config.results_dir) / (exam.semester or "")
    out_dir.mkdir(parents=True, exist_ok=True)
    date_part = str(exam.date or "").replace("-", "")
    path = out_dir / f"{date_part}_{exam.name}_{label}_个人成绩单.xlsx"

    wb = Workbook()
    wb.remove(wb.active)
    if p.single_sheet:
        ws = wb.create_sheet("个人成绩单")
        _write_sheet(ws, *_build_strip_rows(
            valid, exam, wide, big, subj_cols, big_cols, classes, cfg
        ), cfg)
    else:
        for cls in sorted(classes):
            sub_valid = valid[valid["class_name"] == cls]
            if sub_valid.empty:
                continue
            ws = wb.create_sheet(str(cls))
            _write_sheet(ws, *_build_strip_rows(
                sub_valid, exam, wide, big, subj_cols, big_cols, {cls}, cfg
            ), cfg)
    wb.save(path)
    return str(path)


def _write_sheet(
    ws,
    cols: list[str],
    rows: list[list[object]],
    widths: list[float],
    cfg: ResultsConfig,
    header_rows: set[int] | None = None,
) -> None:
    lay = cfg.personal.layout
    for row in rows:
        ws.append(row)
    header_font = Font(
        name=lay.font["header"].name,
        size=lay.font["header"].size,
        bold=lay.font["header"].bold,
    )
    data_font = Font(
        name=lay.font["data"].name,
        size=lay.font["data"].size,
        bold=lay.font["data"].bold,
    )
    bold_total = cfg.personal.bold_total_score
    bold_font = Font(
        name=lay.font["data"].name,
        size=lay.font["data"].size,
        bold=True,
    )
    right_from_idx = len(cols)
    if lay.alignment["right_from"] in cols:
        right_from_idx = cols.index(lay.alignment["right_from"])
    center_cols = set(lay.alignment["center_cols"])
    block = 2 + lay.blank_rows_between
    for r in range(1, ws.max_row + 1):
        if header_rows is None:
            pos = (r - 1) % block
            is_header = pos == 0
            is_data = pos == 1
        else:
            is_header = r in header_rows
            is_data = not is_header and any(c.value is not None for c in ws[r])
        for cidx, cell in enumerate(ws[r], start=1):
            if is_header:
                cell.font = header_font
            elif is_data and bold_total and cidx - 1 == 5:
                cell.font = bold_font  # 总分值加粗
            else:
                cell.font = data_font
            if is_header:
                if lay.alignment["header"] == "center_center":
                    cell.alignment = Alignment(horizontal="center", vertical="center")
            elif is_data:
                col_name = cols[cidx - 1]
                if col_name in center_cols:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif cidx - 1 >= right_from_idx:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                elif lay.alignment["data_vertical"] == "center":
                    cell.alignment = Alignment(vertical="center")
        if lay.borders["enabled"] and (is_header or is_data):
            top_style = (
                lay.borders["header_top_style"] if is_header else lay.borders["style"]
            )
            for cell in ws[r]:
                cell.border = Border(
                    top=Side(style=top_style),
                    bottom=Side(style=lay.borders["style"]),
                )
        ws.row_dimensions[r].height = lay.row_height

    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    hf = cfg.personal.header_footer
    if hf.enabled:
        ws.oddHeader.left.text = hf.header.left
        ws.oddHeader.center.text = hf.header.center
        ws.oddHeader.right.text = hf.header.right
        ws.oddFooter.left.text = hf.footer.left
        ws.oddFooter.center.text = hf.footer.center
        ws.oddFooter.right.text = hf.footer.right
        hl = hf.fonts["header_left"]
        ws.oddHeader.left.font = hl.name or None
        ws.oddHeader.left.size = hl.size
        hc = hf.fonts["header_center"]
        ws.oddHeader.center.font = hc.name or None
        ws.oddHeader.center.size = hc.size
        hr = hf.fonts["header_right"]
        ws.oddHeader.right.font = hr.name or None
        ws.oddHeader.right.size = hr.size
        fl = hf.fonts["footer_left"]
        ws.oddFooter.left.font = fl.name or None
        ws.oddFooter.left.size = fl.size

    pr = cfg.personal.print
    ws.page_setup.orientation = pr.orientation
    ws.page_setup.paperSize = _PAPER_SIZE.get(pr.paper_size, 9)
    ws.page_margins.left = pr.margin["left"]
    ws.page_margins.right = pr.margin["right"]
    ws.page_margins.top = pr.margin["top"]
    ws.page_margins.bottom = pr.margin["bottom"]
    if pr.fit_to_width:
        ws.page_setup.fitToWidth = 1
        ws.sheet_properties.pageSetUpPr.fitToPage = True


def build_personal_strips(
    exam: ExamConfig,
    score: pd.DataFrame,
    questions: pd.DataFrame,
    cfg: ResultsConfig,
    config: AnalysisConfig,
) -> list[str]:
    """按范围生成个人成绩单文件，返回路径列表。"""
    valid = score[score["total_score"].notna()]
    if valid.empty:
        return []
    wide, big, subj_cols, big_cols = _subjective_pivot(questions)
    scope = cfg.personal.scope
    all_classes = set(valid["class_name"])
    teacher_sets = _teacher_sets(config, exam)

    tasks: list[tuple[str, set[str]]] = []
    if scope.mode == "teacher":
        tm = config.teacher_maps.get((exam.semester, exam.subject))
        teacher_names = tm.teacher_names if tm else {}
        for tname in scope.teachers:
            name = _resolve_teacher(tname, teacher_names)
            classes = teacher_sets.get(name, set()) & all_classes
            if classes:
                tasks.append((name, classes))
    elif scope.mode == "custom":
        classes = set(scope.classes) & all_classes
        if classes:
            tasks.append((_label_for(classes, all_classes, teacher_sets), classes))
    else:
        tasks.append(("全部班级", all_classes))

    paths = []
    for label, classes in tasks:
        paths.append(
            _write_strip_file(
                exam, valid, wide, big, subj_cols, big_cols,
                classes, label, cfg, config,
            )
        )
    return paths


def build_merged_personal_strips(
    exams: list[ExamConfig],
    scores: list[pd.DataFrame],
    questions_list: list[pd.DataFrame],
    cfg: ResultsConfig,
    config: AnalysisConfig,
) -> list[str]:
    """多场个人成绩单合并：每个学生一个表头，每场考试一行。

    列固定：班级/姓名/考试/班次/校次/总分/客观分/主观分/单选/多选/主观题；
    主观题列为该场各大题得分合并字符串（竖线分隔）。仅多场（>=2）时生成。
    """
    if not exams or len(exams) < 2:
        return []
    valid_list = [s[s["total_score"].notna()].copy() for s in scores]
    all_classes: set[str] = set()
    for v in valid_list:
        all_classes |= set(v["class_name"])
    teacher_sets = _teacher_sets(config, exams[0])

    tasks: list[tuple[str, set[str]]] = []
    scope = cfg.personal.scope
    if scope.mode == "teacher":
        tm = config.teacher_maps.get((exams[0].semester, exams[0].subject))
        teacher_names = tm.teacher_names if tm else {}
        for tname in scope.teachers:
            name = _resolve_teacher(tname, teacher_names)
            classes = teacher_sets.get(name, set()) & all_classes
            if classes:
                tasks.append((name, classes))
    elif scope.mode == "custom":
        classes = set(scope.classes) & all_classes
        if classes:
            tasks.append((_label_for(classes, all_classes, teacher_sets), classes))
    else:
        tasks.append(("全部班级", all_classes))

    paths: list[str] = []
    for label, classes in tasks:
        paths.append(
            _write_merged_strip_file(
                exams, valid_list, questions_list, classes, label, cfg, config
            )
        )
    return paths


def _write_merged_strip_file(
    exams: list[ExamConfig],
    valid_list: list[pd.DataFrame],
    questions_list: list[pd.DataFrame],
    classes: set[str],
    label: str,
    cfg: ResultsConfig,
    config: AnalysisConfig,
) -> str:
    p = cfg.personal
    out_dir = Path(config.results_dir) / (exams[0].semester or "")
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = date_range_suffix(exams)
    path = out_dir / f"{suffix}_{label}_个人成绩单.xlsx"

    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("个人成绩单")
    cols, rows, widths, header_rows = _build_merged_rows(
        exams, valid_list, questions_list, classes, cfg
    )
    _write_sheet(ws, cols, rows, widths, cfg, header_rows=header_rows)
    wb.save(path)
    return str(path)


def _build_merged_rows(
    exams: list[ExamConfig],
    valid_list: list[pd.DataFrame],
    questions_list: list[pd.DataFrame],
    classes: set[str],
    cfg: ResultsConfig,
) -> tuple[list[str], list[list[object]], list[float], set[int]]:
    """构建合并成绩单：每个学生一个表头 + 各场一行数据。"""
    p = cfg.personal
    cols = list(_MERGED_COLS)
    widths = list(p.layout.column_widths["first10"]) + [
        p.layout.column_widths["merged_question_cols"]
    ]

    per_exam: list[tuple[ExamConfig, pd.DataFrame, dict[str, str]]] = []
    for exam, valid, questions in zip(exams, valid_list, questions_list):
        _wide, big, _subj_cols, big_cols = _subjective_pivot(questions)
        big_s = big.copy()
        big_s.index = big_s.index.astype(str)
        subj_str: dict[str, str] = {}
        for sid in big_s.index:
            vals = [
                big_s.loc[sid, c] if sid in big_s.index else None
                for c in big_cols
            ]
            subj_str[sid] = "|".join(
                "" if pd.isna(v) else str(int(v)) for v in vals
            )
        v = valid[valid["class_name"].isin(classes)].copy()
        v["_sid"] = v["student_id"].astype(str)
        per_exam.append((exam, v, subj_str))

    all_sids: set[str] = set()
    meta: dict[str, tuple[str, str]] = {}
    total_sum: dict[str, float] = {}
    total_cnt: dict[str, int] = {}
    for _, v, _ in per_exam:
        for _, row in v.iterrows():
            sid = row["_sid"]
            all_sids.add(sid)
            if sid not in meta:
                meta[sid] = (
                    str(row["class_name"]),
                    "" if pd.isna(row["name"]) else str(row["name"]),
                )
            total_sum[sid] = total_sum.get(sid, 0.0) + float(row["total_score"])
            total_cnt[sid] = total_cnt.get(sid, 0) + 1

    def avg(sid: str) -> float:
        return total_sum.get(sid, 0.0) / max(total_cnt.get(sid, 1), 1)

    students = sorted(all_sids, key=lambda s: (meta[s][0], -avg(s), s))

    rows: list[list[object]] = []
    header_rows: set[int] = set()
    for sid in students:
        header_rows.add(len(rows) + 1)
        rows.append(list(cols))
        cls, name = meta[sid]
        for exam, v, subj_str in per_exam:
            row = v[v["_sid"] == sid]
            if row.empty:
                continue  # 该生未参加本场
            srow = row.iloc[0]
            rows.append(
                [
                    cls,
                    name,
                    exam.effective_short_name,
                    srow["班次"],
                    srow["校次"],
                    srow["total_score"],
                    srow["objective_score"],
                    srow["subjective_score"],
                    srow["单选分"],
                    srow["多选分"],
                    subj_str.get(sid, ""),
                ]
            )
        for _ in range(p.layout.blank_rows_between):
            rows.append([None] * len(cols))
    return cols, rows, widths, header_rows
