"""流程编排：串联 逐场解析 -> 合并 -> 分析 -> 报告。"""

from __future__ import annotations

import re
import time

from .adapters.registry import auto_detect_format, get_adapter
from .chart_config import load_charts_config
from .cleaning import (
    add_question_type_scores,
    clean_score_table,
    classify_objective_types,
    collect_quality_issues,
    filter_default_school,
)
from .consolidate import (
    describe_exam_list,
    merge_to_output,
    resolve_exam_by_index,
    sort_exams_by_date,
)
from .config import AnalysisConfig, ExamConfig, load_config
from .detect import detect_subject_from_filename, resolve_exam_name
from .dist_charts import build_all_charts
from .io_utils import read_raw_sheet
from .storage import is_parsed_fresh, write_parsed_tables
from .report import build_class_summaries, build_exam_statistics, build_report
from .personal_strip import build_merged_personal_strips, build_personal_strips
from .quality import write_quality_excel
from .result_config import load_results_config
from .run_info import write_run_info
from .storage import read_question_detail, read_score_summary


def _parse_number_list(value: str) -> list[int] | None:
    """值全部由数字/逗号组成时返回序号列表，否则 None（视为考试名称）。"""
    stripped = value.strip()
    if not stripped:
        return None
    if not re.fullmatch(r"[-0-9,\s]+", stripped):
        return None
    parts = [p for p in stripped.replace(" ", "").split(",") if p != ""]
    return [int(p) for p in parts] if parts else None


def _resolve_exam_selection(
    config: AnalysisConfig,
    exam_arg: str | None,
    semester: str | None,
) -> tuple[list[ExamConfig], list[str] | None, str | None]:
    """确定本次处理的考试列表、parse 名称列表（None=全部）与合并用学期。

    - exam_arg（--exam）：纯数字/逗号数字按序号列表解析；否则按考试名称（单场）；
    - 无 --exam 时按全局 current_exam（序号列表）选择，为空处理全部；
    - 未传 --exam 时打印带序号的考试列表。
    """
    for e in config.exams:
        if e.name is None:
            e.name = resolve_exam_name(e, config.subjects, config.subject_aliases)

    nums = _parse_number_list(exam_arg) if exam_arg else None
    if exam_arg and nums is None:
        matched = [e for e in config.exams if e.name == exam_arg]
        if not matched:
            raise ValueError(f"未找到指定考试: {exam_arg}")
        return [matched[0]], [matched[0].name], None

    scope_semester = semester or config.current_semester
    scope = (
        [e for e in config.exams if e.semester == scope_semester]
        if scope_semester
        else list(config.exams)
    )
    lines = describe_exam_list(scope)
    print(f"[考试列表] 共 {len(lines)} 场（序号按日期升序）")
    for line in lines:
        print(f"  {line}")

    indices = nums if nums is not None else config.current_exam
    if indices:
        selected: list[ExamConfig] = []
        seen: set[str] = set()
        for i in indices:
            exam = resolve_exam_by_index(scope, i)
            if exam.name not in seen:
                selected.append(exam)
                seen.add(exam.name)
        selected = sort_exams_by_date(selected)
        return selected, [e.name for e in selected], scope_semester
    return scope, None, scope_semester


def parse_exams(
    config_path: str = "config/config.yaml",
    reparse: bool = False,
    exam_names: list[str] | None = None,
) -> None:
    """解析全部考试原始文件 -> 规范表落盘。

    复用策略：规范表已存在且原始文件未变（mtime）时复用缓存；
    reparse=True 时忽略缓存强制重新解析；
    exam_names 指定时只解析其中考试（名称需与配置解析后一致）。
    """
    config = load_config(config_path)
    exams = list(config.exams)
    # 先解析考试名称（weekly 名称从文件名提取），否则 exam_names 无法命中
    for exam in exams:
        if exam.name is None:
            exam.name = resolve_exam_name(exam, config.subjects, config.subject_aliases)
    if exam_names:
        exams = [e for e in exams if e.name in exam_names]
        if not exams:
            raise ValueError(f"未找到指定考试: {exam_names}")
    for exam in exams:
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
    verify_roster: bool = False,
) -> None:
    """执行完整分析流程。

    - semester：限定学期，缺省用全局 current_semester（当前学期）；
    - types：考试类型筛选（逗号分隔，如 默认,模考）；
    - baseline_exams：额外加入的历史场次名称（比较基准），逗号分隔；
    - exam：指定考试名称或序号列表（优先级最高，名称/序号见 --exam 帮助）；
      不传时默认列出考试列表，并按全局 current_exam（序号列表）选择，为空处理全部；
    - reparse：强制重新解析原始文件。

    后续实现步骤：
    1. parse_exams（按需复用缓存）；
    2. 合并规范表 -> 长表/宽表；
    3. 每场统计工作簿 + 跨场 Excel 汇总报告。
    """
    config = load_config(config_path)
    start = time.time()
    events: list[tuple[str, str, str]] = []
    charts_cfg = load_charts_config(config.charts_dir)
    results_cfg = load_results_config(config.results_config_dir)

    selected, parse_names, merge_semester = _resolve_exam_selection(
        config, exam, semester
    )
    config.exams = selected

    def event(stage: str, msg: str) -> None:
        events.append((time.strftime("%H:%M:%S"), stage, msg))

    event("启动", f"run 开始（配置 {config_path}）")
    parse_exams(config_path, reparse=reparse, exam_names=parse_names)
    event("解析", "规范表解析/复用完成")
    long_df, wide_df, frames = merge_to_output(
        config,
        semester=merge_semester,
        types=types,
        baseline_exams=baseline_exams,
    )
    event("合并", f"合并 {len(frames)} 场考试，{len(wide_df)} 名学生")
    strip_inputs: list[tuple[ExamConfig, pd.DataFrame, pd.DataFrame]] = []
    for exam, score in frames:
        path = build_exam_statistics(exam, score, config)
        event("统计", f"{exam.name}: {path}")
        print(f"[统计] {exam.name}: {path}")
        questions = read_question_detail(
            config.parsed_dir, exam, config.parsed_format
        )
        strip_inputs.append((exam, score, questions))
        summary_paths = build_class_summaries(
            exam, score, questions, config, results_cfg,
            verify_roster=verify_roster,
        )
        for summary_path in summary_paths:
            print(f"[班级汇总] {summary_path}")
        event(
            "班级汇总",
            f"{exam.name}: {len(summary_paths)} 个教师汇总文件",
        )
        if verify_roster:
            event("名单核对", f"{exam.name}: 已核对")
        chart_paths = build_all_charts(exam, score, charts_cfg, config.output)
        for chart_path in chart_paths:
            print(f"[统计图] {chart_path}")
        if chart_paths:
            event("统计图", f"{exam.name}: {len(chart_paths)} 张组合图")
    # 个人成绩单：多场合并（每生一个表头，每场一行）；单场沿用原格式
    if len(strip_inputs) >= 2:
        strip_paths = build_merged_personal_strips(
            [e for e, _, _ in strip_inputs],
            [s for _, s, _ in strip_inputs],
            [q for _, _, q in strip_inputs],
            results_cfg,
            config,
        )
        for strip_path in strip_paths:
            print(f"[个人成绩单] {strip_path}")
        if strip_paths:
            event("个人成绩单", f"多场合并: {len(strip_paths)} 份")
    elif strip_inputs:
        exam, score, questions = strip_inputs[0]
        strip_paths = build_personal_strips(
            exam, score, questions, results_cfg, config
        )
        for strip_path in strip_paths:
            print(f"[个人成绩单] {strip_path}")
        if strip_paths:
            event("个人成绩单", f"{exam.name}: {len(strip_paths)} 份")
    report_path = build_report(config, long_df, frames)
    event("报告", report_path)
    print(f"[报告] {report_path}")
    quality_sheets = {
        exam.name: collect_quality_issues(score, exam, config)
        for exam, score in frames
    }
    quality_path = write_quality_excel(config, quality_sheets)
    if quality_path:
        event("质量", quality_path)
        print(f"[质量] {quality_path}")
    elapsed = time.time() - start
    event("完成", f"总耗时 {elapsed:.1f}s")
    run_dir = write_run_info(config, events)
    print(f"[run-info] {run_dir}")


def run_results(
    config_path: str = "config/config.yaml",
    semester: str | None = None,
    exam_name: str | None = None,
) -> None:
    """单独命令：生成指定学期/考试的班级汇总与个人成绩单。

    - exam_name：指定考试名称或序号列表（优先级最高，规则同 --exam）；
    - 未指定时默认列出考试列表，并按全局 current_exam（序号列表）选择，
      为空则处理学期内全部考试；多场时个人成绩单合并为一份。
    """
    config = load_config(config_path)
    results_cfg = load_results_config(config.results_config_dir)
    exams, _parse_names, _merge_semester = _resolve_exam_selection(
        config, exam_name, semester
    )
    if not exams:
        raise ValueError("筛选后无考试可生成成绩单")
    strip_inputs: list[tuple[ExamConfig, pd.DataFrame, pd.DataFrame]] = []
    for exam in exams:
        if not exam.name:
            continue
        score = read_score_summary(config.parsed_dir, exam, config.parsed_format)
        questions = read_question_detail(
            config.parsed_dir, exam, config.parsed_format
        )
        for p in build_class_summaries(
            exam, score, questions, config, results_cfg
        ):
            print(f"[班级汇总] {p}")
        strip_inputs.append((exam, score, questions))
    if len(strip_inputs) >= 2:
        strip_paths = build_merged_personal_strips(
            [e for e, _, _ in strip_inputs],
            [s for _, s, _ in strip_inputs],
            [q for _, _, q in strip_inputs],
            results_cfg,
            config,
        )
        for p in strip_paths:
            print(f"[个人成绩单] {p}")
    else:
        for exam, score, questions in strip_inputs:
            for p in build_personal_strips(
                exam, score, questions, results_cfg, config
            ):
                print(f"[个人成绩单] {p}")
