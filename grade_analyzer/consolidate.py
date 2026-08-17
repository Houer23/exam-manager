"""规范表合并。

合并键：12 位考号；学生集合并集；未参加某场 = 缺失（区别于 0 分）；
班级取最近一场（按 date）；跨场比较一律用得分率。

产出两种形态：
- 长表：各场 score_summary 拼接（小题明细不拼接）；
- 宽表：考号 × 场次（原始分 + 得分率 + 平均得分率 + 参加场次 + 班级）。

合并范围可按 学期/考试类型/科目 筛选；
run/merge 默认当前学期，可用 baseline_exams 加入历史场次作比较基准。
"""

from __future__ import annotations

import pandas as pd

from .config import AnalysisConfig, ExamConfig, load_config
from .detect import resolve_exam_name
from .io_utils import write_parsed_table
from .outputs import merged_dir
from .storage import read_score_summary


def select_exams(
    exams: list[ExamConfig],
    semester: str | None = None,
    types: list[str] | None = None,
    subject: str | None = None,
) -> list[ExamConfig]:
    """按学期/考试类型/科目筛选考试。"""
    result = list(exams)
    if semester:
        result = [e for e in result if e.semester == semester]
    if types:
        result = [e for e in result if e.type in types]
    if subject:
        result = [e for e in result if e.subject == subject]
    return result


def load_score_tables(
    exams: list[ExamConfig], config: AnalysisConfig
) -> list[tuple[ExamConfig, pd.DataFrame]]:
    """读取各场科目总分表，返回 [(考试, 规范表)]。"""
    result: list[tuple[ExamConfig, pd.DataFrame]] = []
    for exam in exams:
        try:
            df = read_score_summary(config.parsed_dir, exam, config.parsed_format)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"{exam.name}: 规范表不存在，请先运行 parse（{exc}）")
        result.append((exam, df))
    return result


def merge_score_tables(
    frames: list[tuple[ExamConfig, pd.DataFrame]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """合并多场科目总分表，返回 (长表, 宽表)。

    宽表：学生并集；每场两列（<考试>_总分 / <考试>_得分率，按 date 升序）；
    附 班级/年级/学校（最近一场）、平均得分率、参考场次；缺考为空值。
    """
    if not frames:
        raise ValueError("无可用规范表，无法合并")
    ordered = sorted(frames, key=lambda t: (t[0].date or "", frames.index(t)))

    long_df = pd.concat([df for _, df in ordered], ignore_index=True)

    all_ids = pd.concat([df["student_id"] for _, df in ordered]).unique()
    wide = pd.DataFrame({"student_id": all_ids}).set_index("student_id")
    for exam, df in ordered:
        by_id = df.set_index("student_id")
        wide[f"{exam.name}_总分"] = by_id["total_score"]
        wide[f"{exam.name}_得分率"] = by_id["total_ratio"]

    latest = ordered[-1][1].set_index("student_id")
    wide["班级"] = latest["class_name"]
    wide["年级"] = latest["grade"]
    wide["学校"] = latest["school"]

    ratio_cols = [f"{e.name}_得分率" for e, _ in ordered]
    wide["平均得分率"] = wide[ratio_cols].mean(axis=1, skipna=True)
    wide["参考场次"] = wide[ratio_cols].notna().sum(axis=1)
    return long_df, wide.reset_index()


def sort_exams_by_date(exams: list[ExamConfig]) -> list[ExamConfig]:
    """按考试日期升序、同日期按考试名称排序，用于场次编号。"""
    return [
        exam
        for _, exam in sorted(
            enumerate(exams),
            key=lambda pair: (
                pair[1].date or "",
                pair[1].name or "",
                pair[0],
            ),
        )
    ]


def resolve_exam_by_index(
    exams: list[ExamConfig], index: int
) -> ExamConfig:
    """按序号取考试：1-n 按日期升序；0=第一场；负数=倒数第 |index| 场。

    边界：正数过大取最后一场；负数绝对值过大取第一场。
    """
    if not exams:
        raise ValueError("无可用考试，无法按序号选择当前场次")
    ordered = sort_exams_by_date(exams)
    n = len(ordered)
    if index > 0:
        pos = min(index, n) - 1
    elif index == 0:
        pos = 0
    else:
        pos = max(n + index, 0)
    return ordered[pos]


def describe_exam_list(exams: list[ExamConfig]) -> list[str]:
    """生成带序号（按日期升序）的考试列表文本，供 run/results 提示使用。"""
    return [
        f"{i}. {exam.name or ''}（{exam.date or ''}）"
        for i, exam in enumerate(sort_exams_by_date(exams), 1)
    ]


def date_range_suffix(exams: list[ExamConfig]) -> str:
    """考试列表的日期范围标注：最早-最晚（YYYYMMDD，短横线）；单场返回该场日期。"""
    dates = sorted(e.date or "" for e in exams)
    if not dates or not dates[0]:
        return ""
    if len(dates) == 1:
        return dates[0].replace("-", "")
    return f"{dates[0].replace('-', '')}-{dates[-1].replace('-', '')}"


def run_merge(
    config_path: str = "config/config.yaml",
    semester: str | None = None,
    types: str | None = None,
    subject: str | None = None,
    baseline_exams: str | None = None,
) -> None:
    """合并命令入口：读规范表 -> 长表/宽表 -> 输出到 merged 目录。"""
    config = load_config(config_path)
    long_df, wide_df, frames = merge_to_output(
        config,
        semester=semester,
        types=types,
        subject=subject,
        baseline_exams=baseline_exams,
    )
    print(f"[完成] 合并 {len(frames)} 场考试，{len(wide_df)} 名学生")
    out_dir = merged_dir(config.output)
    if len(frames) >= 2:
        suffix = date_range_suffix([e for e, _ in frames])
        print(f"  长表: {out_dir / f'merged_long_{suffix}.csv'}")
        print(f"  宽表: {out_dir / f'merged_wide_{suffix}.csv'}")
    else:
        print("[提示] 单场考试，跳过合并落盘")


def merge_to_output(
    config: AnalysisConfig,
    semester: str | None = None,
    types: str | None = None,
    subject: str | None = None,
    baseline_exams: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[tuple[ExamConfig, pd.DataFrame]]]:
    """读规范表合并并落盘，返回 (长表, 宽表, [(考试, 规范表)])。"""
    for exam in config.exams:
        if exam.name is None:
            exam.name = resolve_exam_name(exam, config.subjects, config.subject_aliases)
    semester = semester or config.current_semester
    types_list = [t.strip() for t in types.split(",")] if types else None
    selected = select_exams(
        config.exams, semester=semester, types=types_list, subject=subject
    )

    if baseline_exams:
        names = {e.name for e in selected}
        for raw_name in baseline_exams.split(","):
            name = raw_name.strip()
            if name in names:
                continue
            for exam in config.exams:
                if exam.name == name:
                    selected.append(exam)
                    names.add(name)
                    break
            else:
                print(f"[警告] 基准场次未找到: {name}")

    if not selected:
        raise ValueError("筛选后无考试可合并")

    frames = load_score_tables(selected, config)
    long_df, wide_df = merge_score_tables(frames)

    # 单场考试不做 merge 落盘（长表即 score_summary 本身，已在 data/parsed 保存）
    if len(selected) >= 2:
        out_dir = merged_dir(config.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = date_range_suffix(selected)
        long_path = out_dir / f"merged_long_{suffix}.csv"
        wide_path = out_dir / f"merged_wide_{suffix}.csv"
        write_parsed_table(long_df, str(long_path), config.parsed_format)
        write_parsed_table(wide_df, str(wide_path), config.parsed_format)
    return long_df, wide_df, frames
