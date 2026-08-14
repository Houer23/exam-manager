"""流程编排：串联 逐场解析 -> 合并 -> 分析 -> 报告。"""

from __future__ import annotations

from .adapters.registry import auto_detect_format, get_adapter
from .cleaning import (
    add_question_type_scores,
    clean_score_table,
    classify_objective_types,
    filter_default_school,
)
from .consolidate import merge_to_output
from .config import load_config
from .detect import detect_subject_from_filename, resolve_exam_name
from .io_utils import read_raw_sheet
from .storage import is_parsed_fresh, write_parsed_tables
from .report import build_class_summaries, build_exam_statistics, build_report
from .storage import read_question_detail


def parse_exams(
    config_path: str = "config/config.yaml", reparse: bool = False
) -> None:
    """解析全部考试原始文件 -> 规范表落盘。

    复用策略：规范表已存在且原始文件未变（mtime）时复用缓存；
    reparse=True 时忽略缓存强制重新解析。
    """
    config = load_config(config_path)
    for exam in config.exams:
        if exam.name is None:
            exam.name = resolve_exam_name(exam)
        if not exam.name:
            print(f"[失败] {exam.full_path}: 考试名称无法解析，请先运行 check")
            continue

        if exam.format is None:
            try:
                raw = read_raw_sheet(exam.full_path)
            except (FileNotFoundError, ValueError) as exc:
                print(f"[失败] {exam.name}: {exc}")
                continue
            exam.format = auto_detect_format(raw)
        if not exam.format:
            print(f"[失败] {exam.name}: 格式无法识别，请先运行 check")
            continue

        if exam.subject is None:
            exam.subject = detect_subject_from_filename(
                exam.full_path, config.subjects, config.subject_aliases
            )
        if not exam.subject:
            print(f"[失败] {exam.name}: 科目无法推测，请先运行 check")
            continue

        if not reparse and is_parsed_fresh(
            config.parsed_dir, exam, config.parsed_format
        ):
            print(f"[复用] {exam.name}: 规范表缓存有效，跳过解析")
            continue

        try:
            adapter = get_adapter(exam.format)
            score, questions = adapter.parse(exam)
        except (ValueError, FileNotFoundError) as exc:
            print(f"[失败] {exam.name}: {exc}")
            continue

        # 无学校列（或部分缺失）时，用全局默认学校填充
        if config.default_school:
            score["school"] = score["school"].replace("", None).fillna(
                config.default_school
            )
        # 单学校模型：只保留默认学校
        score, questions = filter_default_school(
            score, questions, config.default_school
        )
        # 清洗：考号/总分校验（失败终止）+ 班级归一化 + 质量清单
        score, issues = clean_score_table(score, exam, config)
        questions = classify_objective_types(questions)
        score, questions = add_question_type_scores(score, questions)
        if len(issues):
            print(f"[质量] {exam.name}: {len(issues)} 条问题")
        write_parsed_tables(
            config.parsed_dir, exam, score, questions, config.parsed_format
        )
        print(f"[完成] {exam.name}: {len(score)} 名学生已落盘")


def run_pipeline(
    config_path: str = "config/config.yaml",
    semester: str | None = None,
    types: str | None = None,
    baseline_exams: str | None = None,
    exam: str | None = None,
    reparse: bool = False,
) -> None:
    """执行完整分析流程。

    - semester：限定学期，缺省用全局 current_semester（当前学期）；
    - types：考试类型筛选（逗号分隔，如 默认,模考）；
    - baseline_exams：额外加入的历史场次名称（比较基准），逗号分隔；
    - exam：显式指定当前场次（优先级高于全局 current_exam 与日期判断）；
    - reparse：强制重新解析原始文件。

    后续实现步骤：
    1. parse_exams（按需复用缓存）；
    2. 合并规范表 -> 长表/宽表；
    3. 每场统计工作簿 + 跨场 Excel 汇总报告。
    """
    config = load_config(config_path)
    parse_exams(config_path, reparse=reparse)
    long_df, _wide_df, frames = merge_to_output(
        config,
        semester=semester,
        types=types,
        baseline_exams=baseline_exams,
    )
    for exam, score in frames:
        path = build_exam_statistics(exam, score, config)
        print(f"[统计] {exam.name}: {path}")
        questions = read_question_detail(
            config.parsed_dir, exam, config.parsed_format
        )
        for summary_path in build_class_summaries(exam, score, questions, config):
            print(f"[班级汇总] {summary_path}")
    report_path = build_report(config, long_df, frames)
    print(f"[报告] {report_path}")
