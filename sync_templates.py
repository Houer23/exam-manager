"""同步实际配置文件到对应模板文件。

用法：
    python sync_templates.py

将以下 实际配置 -> 模板 同步（模板内容 = 实际配置内容）：
    config/charts/config.yaml  -> config/charts/_template.yaml
    config/results/config.yaml -> config/results/_template.yaml

说明：考试/班级/学科模板为说明性示例（含注释），不与实际配置一一对应，
不参与同步。
"""

from __future__ import annotations

import shutil
from pathlib import Path

PAIRS = [
    ("config/charts/config.yaml", "config/charts/_template.yaml"),
    ("config/results/config.yaml", "config/results/_template.yaml"),
]


def sync_pairs(pairs: list[tuple[str, str]], root: Path = Path(".")) -> list[str]:
    """按 (实际配置, 模板) 列表同步，返回成功列表。"""
    done = []
    for src, dst in pairs:
        s = root / src
        if not s.is_file():
            print(f"[跳过] 不存在: {src}")
            continue
        shutil.copyfile(s, root / dst)
        print(f"[完成] {src} -> {dst}")
        done.append(dst)
    return done


def main() -> None:
    sync_pairs(PAIRS)


if __name__ == "__main__":
    main()
