"""命令行入口。

用法：
    python -m grade_analyzer.cli check --config config/config.yaml
    python -m grade_analyzer.cli parse [--reparse]
    python -m grade_analyzer.cli merge [--semester ...] [--types ...] [--baseline-exams ...]
    python -m grade_analyzer.cli run --config config/config.yaml
    python -m grade_analyzer.cli exam add|update|remove|list ...
    python -m grade_analyzer.cli config get|set <key> [<value>]
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grade-analyzer",
        description="学生成绩单处理与分析工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_config_arg(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--config",
            default="config/config.yaml",
            help="配置文件路径（默认：config/config.yaml）",
        )

    check_parser = subparsers.add_parser(
        "check", help="识别并校验考试配置，不运行分析"
    )
    add_config_arg(check_parser)
    check_parser.add_argument(
        "--force",
        action="store_true",
        help="忽略已检查标记，强制重新检查所有考试",
    )
    check_parser.add_argument(
        "--exam",
        default=None,
        help="考试名称或序号列表（如 1,3；纯数字/逗号=按日期升序序号，否则按名称）；缺省=全部",
    )

    parse_parser = subparsers.add_parser(
        "parse", help="解析原始文件并落盘规范表（可复用缓存）"
    )
    add_config_arg(parse_parser)
    parse_parser.add_argument(
        "--reparse", action="store_true", help="忽略缓存强制重新解析"
    )

    merge_parser = subparsers.add_parser(
        "merge", help="读取规范表合并输出长表/宽表（可选）"
    )
    add_config_arg(merge_parser)
    merge_parser.add_argument(
        "--semester", default=None, help="限定学期（缺省=当前学期）"
    )
    merge_parser.add_argument(
        "--types", default=None, help="考试类型，逗号分隔，如 默认,模考"
    )
    merge_parser.add_argument("--subject", default=None, help="限定科目")
    merge_parser.add_argument(
        "--baseline-exams",
        default=None,
        help="额外加入的历史场次名称（比较基准），逗号分隔",
    )

    run_parser = subparsers.add_parser("run", help="运行完整分析流程")
    add_config_arg(run_parser)
    run_parser.add_argument(
        "--semester", default=None, help="限定学期（缺省=当前学期）"
    )
    run_parser.add_argument(
        "--types", default=None, help="考试类型，逗号分隔，如 默认,模考"
    )
    run_parser.add_argument(
        "--baseline-exams",
        default=None,
        help="额外加入的历史场次名称（比较基准），逗号分隔",
    )
    run_parser.add_argument(
        "--exam",
        default=None,
        help="考试名称或序号列表（如 1,3；纯数字/逗号=按日期升序序号，否则按名称）；"
             "不传时列出考试列表并按 current_exam 或全部处理",
    )
    run_parser.add_argument(
        "--reparse", action="store_true", help="忽略缓存强制重新解析"
    )
    run_parser.add_argument(
        "--verify-roster",
        action="store_true",
        help="生成班级汇总时核对学生名单",
    )

    # ---------- exam：考试条目管理 ----------
    exam_parser = subparsers.add_parser("exam", help="考试条目管理")
    exam_sub = exam_parser.add_subparsers(dest="exam_command", required=True)

    add_p = exam_sub.add_parser(
        "add", help="新增考试条目（参数式或交互式问答）"
    )
    add_config_arg(add_p)
    add_p.add_argument(
        "--folder",
        default=None,
        help="成绩文件所在文件夹（留空=取全局 input_dir；缺省=交互式问答）",
    )
    add_p.add_argument("--file", default=None, help="成绩文件名（缺省=交互式问答）")
    add_p.add_argument("--name", default=None, help="考试名称（留空=自动提取）")
    add_p.add_argument("--format", default=None)
    add_p.add_argument("--type", default=None, help="考试类型：默认/学考/模考...")
    add_p.add_argument("--importance", default=None, choices=["平时", "联考"])
    add_p.add_argument("--semester", default=None, help="学期全称（缺省=交互式问答）")
    add_p.add_argument("--date", default=None, help="考试日期 YYYY-MM-DD（留空=运行当日）")
    add_p.add_argument("--subject", default=None, help="科目（留空=从文件名推测）")
    add_p.add_argument("--full-score", dest="full_score", type=float, default=None)
    add_p.add_argument(
        "--objective-full-score", dest="objective_full_score", type=float, default=None
    )
    add_p.add_argument(
        "--subjective-full-score", dest="subjective_full_score", type=float, default=None
    )
    add_p.add_argument(
        "--objective-question-count",
        dest="objective_question_count",
        type=int,
        default=None,
        help="客观题数（题号大于该数均为主观题；留空=按题号格式自动判定）",
    )
    add_p.add_argument("--default-grade", dest="default_grade", default=None)
    add_p.add_argument("--sheet", default=None)
    add_p.add_argument("--short-name", dest="short_name", default=None)
    add_p.add_argument(
        "--question-display",
        dest="question_display",
        default=None,
        choices=["split", "merged"],
    )
    add_p.add_argument("--show-big-questions", dest="show_big_questions", action="store_true")
    add_p.add_argument("--filter-by-selection", dest="filter_by_selection", action="store_true")

    update_p = exam_sub.add_parser("update", help="修改考试条目字段")
    update_p.add_argument("name", help="考试名称")
    add_config_arg(update_p)
    update_p.add_argument("--folder", default=None)
    update_p.add_argument("--file", default=None)
    update_p.add_argument("--format", default=None)
    update_p.add_argument("--type", default=None)
    update_p.add_argument("--importance", default=None, choices=["平时", "联考"])
    update_p.add_argument("--semester", default=None, help="变更时自动移动条目文件到新学期目录")
    update_p.add_argument("--date", default=None)
    update_p.add_argument("--subject", default=None)
    update_p.add_argument("--full-score", dest="full_score", type=float, default=None)
    update_p.add_argument(
        "--objective-full-score", dest="objective_full_score", type=float, default=None
    )
    update_p.add_argument(
        "--subjective-full-score", dest="subjective_full_score", type=float, default=None
    )
    update_p.add_argument("--default-grade", dest="default_grade", default=None)
    update_p.add_argument("--sheet", default=None)

    remove_p = exam_sub.add_parser(
        "remove", help="删除考试条目（保留规范表缓存，仅做删除标记）"
    )
    remove_p.add_argument("name", help="考试名称")
    add_config_arg(remove_p)

    list_p = exam_sub.add_parser("list", help="列出考试条目及 check/results 可用性")
    add_config_arg(list_p)
    list_p.add_argument("--semester", default=None, help="限定学期")
    list_p.add_argument(
        "--checkable", action="store_true", help="只列出可执行 check 的场次（原始文件存在）"
    )
    list_p.add_argument(
        "--results-ready",
        action="store_true",
        help="只列出可生成成绩单的场次（规范表有效）",
    )

    # ---------- config：全局配置管理 ----------
    config_parser = subparsers.add_parser("config", help="全局配置管理")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)

    get_p = config_sub.add_parser("get", help="读取全局配置项")
    add_config_arg(get_p)
    get_p.add_argument(
        "key",
        nargs="?",
        default=None,
        help="配置键（如 pass_ratio）；省略时列出全部可 get 的键及值",
    )

    set_p = config_sub.add_parser("set", help="修改全局配置项（白名单+类型/范围校验）")
    add_config_arg(set_p)
    set_p.add_argument("key", help="配置键（如 pass_ratio）")
    set_p.add_argument(
        "value",
        nargs="?",
        default=None,
        help="配置值；省略时恢复该键默认值",
    )

    # ---------- roster：名单清洗与核对 ----------
    roster_parser = subparsers.add_parser("roster", help="名单清洗与核对")
    roster_sub = roster_parser.add_subparsers(dest="roster_command", required=True)

    norm_p = roster_sub.add_parser("normalize", help="清洗名单并生成规范化文件")
    add_config_arg(norm_p)
    norm_p.add_argument("--semester", default=None, help="学期（缺省=当前学期）")

    check_p = roster_sub.add_parser("check", help="核对指定学期/考试")
    add_config_arg(check_p)
    check_p.add_argument("--semester", default=None, help="学期（缺省=当前学期）")
    check_p.add_argument("--exam", default=None, help="考试名称（缺省=全部）")

    # ---------- results：成绩单生成 ----------
    results_parser = subparsers.add_parser(
        "results", help="生成班级成绩汇总与个人成绩单"
    )
    add_config_arg(results_parser)
    results_parser.add_argument("--semester", default=None, help="学期（缺省=当前学期）")
    results_parser.add_argument(
        "--exam",
        default=None,
        help="考试名称或序号列表（如 1,3；纯数字/逗号=按日期升序序号，否则按名称）；"
             "缺省时列出考试列表并按 current_exam 或全部处理",
    )
    results_parser.add_argument(
        "--no-merge-strips",
        action="store_true",
        help="多场考试时个人成绩单不合并，每场单独生成（缺省=合并）",
    )
    results_only_group = results_parser.add_mutually_exclusive_group()
    results_only_group.add_argument(
        "--summary-only",
        action="store_true",
        help="只生成班级成绩汇总，不生成个人成绩单",
    )
    results_only_group.add_argument(
        "--strips-only",
        action="store_true",
        help="只生成个人成绩单，不生成班级成绩汇总",
    )

    charts_parser = subparsers.add_parser("charts", help="生成统计图（需先 parse）")
    add_config_arg(charts_parser)
    charts_parser.add_argument("--semester", default=None, help="学期（缺省=当前学期）")
    charts_parser.add_argument(
        "--exam",
        default=None,
        help="考试名称或序号列表（如 1,3；纯数字/逗号=按日期升序序号，否则按名称）；"
             "缺省时列出考试列表并按 current_exam 或全部处理",
    )
    charts_parser.add_argument(
        "--class",
        dest="class_list",
        default=None,
        help="指定班级数字列表（如 10,11，年级取默认年级），按 班级×考试 绘制；"
             "缺省按配置分组（层次/教师）绘制",
    )
    charts_parser.add_argument(
        "--per-class",
        action="store_true",
        help="--class 给出多个班级时，每个班级单独生成一张图",
    )

    # ---------- task：运行插件任务 ----------
    task_parser = subparsers.add_parser(
        "task", help="运行插件注册的批处理任务（如 objective_analyze）"
    )
    add_config_arg(task_parser)
    task_parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help="任务名称；省略或使用 --list 时列出已注册任务",
    )
    task_parser.add_argument(
        "--list",
        action="store_true",
        help="列出已注册的任务名称与描述",
    )
    task_parser.add_argument(
        "--plugin-config",
        default=None,
        help="插件配置文件路径（由任务自行解析，如 objective_analyze 的 config.yaml）",
    )
    task_parser.add_argument(
        "--input-dir",
        default=None,
        help="任务输入目录（如客观题得分明细文件夹；优先于插件配置）",
    )
    task_parser.add_argument(
        "--output-dir",
        default=None,
        help="任务输出目录（覆盖插件配置的默认输出位置）",
    )
    task_parser.add_argument(
        "--baseline",
        "--bl",
        dest="baseline",
        default=None,
        help="基线（全部班级 或 分组名；留空 = 全部班级），别名 --bl",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from .plugins.loader import load_plugins

    # 启动时加载插件（幂等）：注册格式适配器与生命周期钩子
    load_plugins(args.config)

    if args.command == "check":
        from .checker import run_check
        from .config import load_config

        config = load_config(args.config)
        if args.exam:
            from .pipeline import _resolve_exam_selection

            selected, _, _ = _resolve_exam_selection(config, args.exam, None)
            return 1 if run_check(config, exams=selected, force=args.force) else 0
        return 1 if run_check(config, force=args.force) else 0
    elif args.command == "parse":
        from .pipeline import parse_exams

        parse_exams(args.config, reparse=args.reparse)
    elif args.command == "merge":
        from .consolidate import run_merge

        run_merge(
            args.config,
            semester=args.semester,
            types=args.types,
            subject=args.subject,
            baseline_exams=args.baseline_exams,
        )
    elif args.command == "run":
        from .pipeline import run_pipeline

        run_pipeline(
            args.config,
            semester=args.semester,
            types=args.types,
            baseline_exams=args.baseline_exams,
            exam=args.exam,
            reparse=args.reparse,
            verify_roster=args.verify_roster,
        )
    elif args.command == "exam":
        from .config_ops import add_exam, list_exams, remove_exam, update_exam

        if args.exam_command == "add":
            add_exam(
                config_path=args.config,
                folder=args.folder,
                file=args.file,
                name=args.name,
                subject=args.subject,
                semester=args.semester,
                date=args.date,
                fmt=args.format,
                exam_type=args.type,
                importance=args.importance,
                full_score=args.full_score,
                objective_full_score=args.objective_full_score,
                subjective_full_score=args.subjective_full_score,
                objective_question_count=args.objective_question_count,
                default_grade=args.default_grade,
                sheet=args.sheet,
                short_name=args.short_name,
                question_display=args.question_display,
                show_big_questions=args.show_big_questions,
                filter_by_selection=args.filter_by_selection,
            )
        elif args.exam_command == "update":
            update_exam(
                config_path=args.config,
                name=args.name,
                folder=args.folder,
                file=args.file,
                subject=args.subject,
                semester=args.semester,
                date=args.date,
                fmt=args.format,
                exam_type=args.type,
                importance=args.importance,
                full_score=args.full_score,
                objective_full_score=args.objective_full_score,
                subjective_full_score=args.subjective_full_score,
                default_grade=args.default_grade,
                sheet=args.sheet,
            )
        elif args.exam_command == "remove":
            remove_exam(args.config, name=args.name)
        elif args.exam_command == "list":
            df = list_exams(
                args.config,
                semester=args.semester,
                checkable=args.checkable,
                results_ready=args.results_ready,
            )
            if df.empty:
                print("（无符合条件的考试）")
            else:
                print(df.to_string(index=False))
    elif args.command == "config":
        from .config_ops import get_config_value, set_config_value

        if args.config_command == "get":
            get_config_value(args.config, key=args.key)
        else:
            set_config_value(args.config, key=args.key, value=args.value)
    elif args.command == "roster":
        from .config import load_config
        from .roster import normalize_roster, run_roster_check

        cfg = load_config(args.config)
        if args.roster_command == "normalize":
            semester = args.semester or cfg.current_semester
            if not semester:
                raise ValueError("未指定学期（--semester 或配置 current_semester）")
            roster_df, issues_df = normalize_roster(cfg, semester)
            print(
                f"[名单] {semester}: 规范化 {len(roster_df)} 名学生，"
                f"异常 {len(issues_df)} 条"
            )
        else:
            run_roster_check(cfg, semester=args.semester, exam_name=args.exam)
    elif args.command == "results":
        from .pipeline import run_results

        run_results(
            args.config,
            semester=args.semester,
            exam_name=args.exam,
            merge_strips=not args.no_merge_strips,
            generate_summary=not args.strips_only,
            generate_strips=not args.summary_only,
        )
    elif args.command == "charts":
        from .pipeline import run_charts

        run_charts(
            args.config,
            semester=args.semester,
            exam_name=args.exam,
            classes=args.class_list,
            per_class=args.per_class,
        )
    elif args.command == "task":
        from .plugins.loader import list_tasks, load_plugins, run_task

        load_plugins(args.config)
        if args.list or not args.name:
            for name, plugin, description in list_tasks():
                print(f"{name}\t{plugin}\t{description}")
            return 0
        return run_task(
            args.name,
            config_path=args.config,
            plugin_config=args.plugin_config,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            baseline=args.baseline,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
