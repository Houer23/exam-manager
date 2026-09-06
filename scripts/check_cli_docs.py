"""校验 docs/CLI命令参考.md 与 grade_analyzer/cli.py 的 argparse 定义一致。

用法：
    python scripts/check_cli_docs.py [--doc docs/CLI命令参考.md]

检查方向：
1. 文档必须包含 build_parser() 中注册的每一个命令/子命令；
2. 文档必须包含每个子命令下的每一个命令行选项（--xxx）；
3. 文档必须包含位置参数（name/key/value 等）。

缺失即打印并返回退出码 1，防止文档与代码漂移。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _collect(parser: argparse.ArgumentParser, prefix: str = "") -> tuple[list[str], set[str]]:
    """递归收集 (命令列表, 选项集合)。"""
    commands: list[str] = []
    options: set[str] = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                full = f"{prefix} {name}".strip()
                commands.append(full)
                sub_commands, sub_options = _collect(sub, full)
                commands.extend(sub_commands)
                options |= sub_options
        else:
            if action.option_strings:
                options.update(action.option_strings)
            elif action.dest and action.dest not in {"help"}:
                # 位置参数（name/key/value 等）也必须出现在文档中
                options.add(f"<{action.dest}>")
    return commands, options


def main() -> int:
    ap = argparse.ArgumentParser(description="校验 CLI 文档与 argparse 定义一致")
    ap.add_argument(
        "--doc",
        default=str(Path(__file__).resolve().parent.parent / "docs" / "CLI命令参考.md"),
        help="CLI 参考文档路径",
    )
    args = ap.parse_args()

    doc_path = Path(args.doc)
    if not doc_path.is_file():
        print(f"[FAIL] 文档不存在: {doc_path}")
        return 1
    text = doc_path.read_text(encoding="utf-8")

    sys.path.insert(0, str(doc_path.parent.parent))
    from grade_analyzer.cli import build_parser

    commands, options = _collect(build_parser())
    missing: list[str] = []

    for cmd in sorted(commands):
        # 子命令行如 "exam add"：要求文档中同时出现 "exam add" 字样
        if cmd not in text:
            missing.append(f"命令/子命令缺失: {cmd}")

    for opt in sorted(options):
        token = opt[1:-1] if opt.startswith("<") and opt.endswith(">") else opt
        if token not in text:
            missing.append(f"参数缺失: {opt}")

    if missing:
        print(f"[FAIL] 发现 {len(missing)} 项缺失：")
        for line in missing:
            print(f"  - {line}")
        return 1

    print(f"[OK] 文档覆盖 {len(commands)} 个命令/子命令、{len(options)} 个参数，无缺失。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
