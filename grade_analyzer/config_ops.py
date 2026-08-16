"""CLI 配置修改操作。

exam add/update/remove/list：考试条目管理（写 config/exams/ 下的 yaml）；
config get/set：全局配置管理（白名单 + 类型/范围校验）。

安全机制：原子写入、修改后自动校验、冲突检测、不触碰原始成绩文件。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd
import yaml

from .config import AnalysisConfig, ExamConfig, load_config
from .detect import resolve_exam_name
from .storage import is_parsed_fresh, parsed_exam_dir

# 全局配置可修改键白名单：键 -> 值类型（number/text）
CONFIG_KEY_WHITELIST: dict[str, str] = {
    "pass_ratio": "number",
    "excellent_ratio": "number",
    "default_full_score": "number",
    "default_grade": "text",
    "current_semester": "text",
    "current_exam": "integer",
    "parsed_dir": "text",
    "parsed_format": "text",
}

# 数值型配置键的取值范围
CONFIG_KEY_RANGES: dict[str, tuple[float, float]] = {
    "pass_ratio": (0.0, 1.0),
    "excellent_ratio": (0.0, 1.0),
    "default_full_score": (1.0, 1000.0),
}

# 白名单键的默认值（config set 省略 value 时恢复为这些值）
CONFIG_KEY_DEFAULTS: dict[str, str] = {
    "pass_ratio": "0.6",
    "excellent_ratio": "0.85",
    "default_full_score": "100",
    "default_grade": "高一",
    "current_semester": "高一第二学期",
    "current_exam": "",
    "parsed_dir": "data/parsed",
    "parsed_format": "csv",
}

# 白名单键 -> 配置文件内的取值路径（逐层取）
_KEY_PATHS: dict[str, tuple[str, ...]] = {
    "pass_ratio": ("analysis", "pass_ratio"),
    "excellent_ratio": ("analysis", "excellent_ratio"),
    "default_full_score": ("default_full_score",),
    "default_grade": ("default_grade",),
    "current_semester": ("current_semester",),
    "current_exam": ("current_exam",),
    "parsed_dir": ("parsed_dir",),
    "parsed_format": ("parsed_format",),
}


def validate_config_value(key: str, value: str) -> str:
    """校验并归一化全局配置值，返回可直接写入 YAML 的值。

    白名单之外的键、类型不匹配、超出范围的值都会抛出 ValueError。
    """
    if key not in CONFIG_KEY_WHITELIST:
        raise ValueError(f"不允许修改的配置键: {key}")
    if CONFIG_KEY_WHITELIST[key] == "integer":
        stripped = value.strip()
        if stripped == "":
            return stripped  # 空值表示"处理全部"
        for part in stripped.split(","):
            part = part.strip()
            if part == "":
                continue
            try:
                int(part)
            except ValueError:
                raise ValueError(
                    f"{key} 应为整数列表（逗号分隔，可含 0 与负数），当前为 {value}"
                )
        return stripped
    if CONFIG_KEY_WHITELIST[key] == "number":
        num = float(value)
        if key in CONFIG_KEY_RANGES:
            lo, hi = CONFIG_KEY_RANGES[key]
            if not (lo <= num <= hi):
                raise ValueError(f"{key} 取值应在 {lo}~{hi} 之间，当前为 {value}")
        return value.strip()
    return value.strip()


def add_exam(
    config_path: str,
    folder: str | None = None,
    file: str | None = None,
    name: str | None = None,
    subject: str | None = None,
    semester: str | None = None,
    date: str | None = None,
    fmt: str | None = None,
    exam_type: str | None = None,
    importance: str | None = None,
    full_score: float | None = None,
    objective_full_score: float | None = None,
    subjective_full_score: float | None = None,
    default_grade: str | None = None,
    sheet: str | None = None,
) -> None:
    """新增考试条目，写入 config/exams/<学期>/<考试名称>.yaml。

    参数式：传入 folder/file 等参数直接生成条目；
    交互式：file 为空时逐个问答必填项与建议默认值。

    TODO:
    1. 识别/确认：考试名称、科目、格式（可复用 detect 模块）；
    2. 冲突检测：同名考试已存在则报错；
    3. 原子写入条目文件；semester 决定子目录；
    4. 写入后重新加载配置并输出校验结果。
    """
    raise NotImplementedError("exam add 将在后续实现")


def update_exam(
    config_path: str,
    name: str,
    folder: str | None = None,
    file: str | None = None,
    subject: str | None = None,
    semester: str | None = None,
    date: str | None = None,
    fmt: str | None = None,
    exam_type: str | None = None,
    importance: str | None = None,
    full_score: float | None = None,
    objective_full_score: float | None = None,
    subjective_full_score: float | None = None,
    default_grade: str | None = None,
    sheet: str | None = None,
) -> None:
    """修改考试条目字段；semester 变更时自动移动文件到新学期目录。

    TODO: 定位条目文件、合并修改、原子写入、修改后校验。
    """
    raise NotImplementedError("exam update 将在后续实现")


def remove_exam(config_path: str, name: str) -> None:
    """删除考试条目文件。

    保留规范表缓存，并在缓存目录写入删除标记（storage.mark_exam_deleted）。

    TODO: 定位条目文件删除；标记缓存；修改后校验。
    """
    raise NotImplementedError("exam remove 将在后续实现")


def _parsed_status(config: AnalysisConfig, exam: ExamConfig) -> str:
    """返回成绩单可用状态：已解析 / 已过期 / 未解析。"""
    if not exam.name:
        return "未解析"
    fmt = config.parsed_format
    exam_dir = parsed_exam_dir(config.parsed_dir, exam)
    score_file = exam_dir / f"score_summary.{fmt}"
    question_file = exam_dir / f"question_detail.{fmt}"
    if not score_file.is_file() and not question_file.is_file():
        return "未解析"
    if is_parsed_fresh(config.parsed_dir, exam, fmt):
        return "已解析"
    return "已过期"


def list_exams(
    config_path: str,
    semester: str | None = None,
    checkable: bool = False,
    results_ready: bool = False,
) -> pd.DataFrame:
    """列出考试条目及 check/results 可用性状态。

    - 检查列：原始成绩文件是否存在（可执行 check 的前提）；
    - 成绩单列：规范表是否已生成且有效（可执行 results 的前提）；
    - checkable=True 时只保留原始文件存在的场次；
    - results_ready=True 时只保留规范表有效的场次。

    返回 DataFrame，由调用方打印。
    """
    config = load_config(config_path)
    rows = []
    for exam in config.exams:
        if semester and exam.semester != semester:
            continue
        if exam.name is None:
            exam.name = resolve_exam_name(exam, config.subjects, config.subject_aliases)
        raw_exists = Path(exam.full_path).is_file()
        status = _parsed_status(config, exam)
        if checkable and not raw_exists:
            continue
        if results_ready and status != "已解析":
            continue
        defaults = config.defaults_for(exam.subject) if exam.subject else None
        full_score = exam.full_score or (defaults.full_score if defaults else None)
        rows.append(
            {
                "考试名称": exam.name or "",
                "学期": exam.semester or "",
                "考试类型": exam.type,
                "格式": exam.format or "",
                "科目": exam.subject or "",
                "日期": exam.date or "",
                "满分": "" if full_score is None else f"{full_score:g}",
                "检查": "可检查" if raw_exists else "文件缺失",
                "成绩单": status,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "考试名称", "学期", "考试类型", "格式", "科目", "日期",
            "满分", "检查", "成绩单",
        ],
    )


def get_config_value(config_path: str, key: str | None = None) -> None:
    """读取全局配置项并打印；key 省略时列出全部白名单键及值。"""
    cfg_path = Path(config_path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"配置文件不存在: {cfg_path}")
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    def _print_value(k: str) -> None:
        value = raw
        for part in _KEY_PATHS[k]:
            value = value.get(part) if isinstance(value, dict) else None
        print(f"{k}: {value}")

    if key is None:
        for k in sorted(CONFIG_KEY_WHITELIST):
            _print_value(k)
        return
    if key not in CONFIG_KEY_WHITELIST:
        raise ValueError(
            f"不支持的配置键: {key}（可用: {', '.join(sorted(CONFIG_KEY_WHITELIST))}）"
        )
    _print_value(key)


def set_config_value(config_path: str, key: str, value: str | None = None) -> None:
    """修改全局配置项。

    validate_config_value 校验 -> 文本级行替换（保留注释）
    -> 临时文件整体校验 -> 原子替换原文件。
    value 省略（None）时恢复该键的默认值。
    """
    if key not in CONFIG_KEY_WHITELIST:
        raise ValueError(
            f"不支持的配置键: {key}（可用: {', '.join(sorted(CONFIG_KEY_WHITELIST))}）"
        )
    if value is None:
        value = CONFIG_KEY_DEFAULTS[key]
    cfg_path = Path(config_path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"配置文件不存在: {cfg_path}")

    new_value = validate_config_value(key, value)
    text = cfg_path.read_text(encoding="utf-8")
    new_text = _replace_key_line(text, key, _format_value(key, new_value))

    tmp_path = cfg_path.with_name(cfg_path.name + ".tmp")
    tmp_path.write_text(new_text, encoding="utf-8")
    try:
        load_config(str(tmp_path))  # 整体校验（含组合合法性）
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    os.replace(tmp_path, cfg_path)
    print(f"{key}: {new_value} 已写入 {cfg_path}")


def _format_value(key: str, value: str) -> str:
    """把校验后的值格式化为 YAML 标量文本。"""
    if CONFIG_KEY_WHITELIST[key] in ("number", "integer"):
        if value == "":
            return "''"  # 空值写为空字符串（表示处理全部）
        return value  # 数字原样写入（如 0.65）
    scalar = yaml.safe_dump(value, allow_unicode=True).strip()
    if scalar.endswith("..."):  # 去掉 PyYAML 对单值文档追加的结束标记
        scalar = scalar[:-3].strip()
    return scalar


def _replace_key_line(text: str, key: str, formatted: str) -> str:
    """按行匹配 `键名:` 并只替换值部分，保留注释与其余格式。"""
    pattern = re.compile(rf"^(\s*{re.escape(key)}:).*$", re.MULTILINE)
    new_text, count = pattern.subn(
        lambda m: f"{m.group(1)} {formatted}", text, count=1
    )
    if count == 0:
        raise ValueError(f"配置文件中未找到键: {key}")
    return new_text
