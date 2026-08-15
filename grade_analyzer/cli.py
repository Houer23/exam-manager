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
        help="指定当前场次考试名称（优先级高于全局 current_exam 与日期判断）",
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
        "--folder", default=None, help="成绩文件所在文件夹（留空=data/input，缺省=交互式问答）"
    )
    add_p.add_argument("--file", default=None, help="成绩文件名（缺省=交互式问答）")
    add_p.add_argument("--name", default=None, help="考试名称（留空=自动提取）")
    add_p.add_argument("--format", default=None, choices=["weekly", "joint"])
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
    add_p.add_argument("--default-grade", dest="default_grade", default=None)
    add_p.add_argument("--sheet", default=None)

    update_p = exam_sub.add_parser("update", help="修改考试条目字段")
    update_p.add_argument("name", help="考试名称")
    add_config_arg(update_p)
    update_p.add_argument("--folder", default=None)
    update_p.add_argument("--file", default=None)
    update_p.add_argument("--format", default=None, choices=["weekly", "joint"])
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

    list_p = exam_sub.add_parser("list", help="列出考试条目")
    add_config_arg(list_p)
    list_p.add_argument("--semester", default=None, help="限定学期")

    # ---------- config：全局配置管理 ----------
    config_parser = subparsers.add_parser("config", help="全局配置管理")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)

    get_p = config_sub.add_parser("get", help="读取全局配置项")
    add_config_arg(get_p)
    get_p.add_argument("key", help="配置键（如 pass_ratio）")

    set_p = config_sub.add_parser("set", help="修改全局配置项（白名单+类型/范围校验）")
    add_config_arg(set_p)
    set_p.add_argument("key", help="配置键（如 pass_ratio）")
    set_p.add_argument("value", help="配置值")

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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "check":
        from .checker import run_check
        from .config import load_config

        return 1 if run_check(load_config(args.config)) else 0
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
                default_grade=args.default_grade,
                sheet=args.sheet,
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
            list_exams(args.config, semester=args.semester)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
