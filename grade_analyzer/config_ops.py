"""CLI 配置修改操作。

exam add/update/remove/list：考试条目管理（写 config/exams/ 下的 yaml）；
config get/set：全局配置管理（白名单 + 类型/范围校验）。

安全机制：原子写入、修改后自动校验、冲突检测、不触碰原始成绩文件。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

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
    "current_exam": "text",
    "parsed_dir": "text",
    "parsed_format": "text",
}

# 数值型配置键的取值范围
CONFIG_KEY_RANGES: dict[str, tuple[float, float]] = {
    "pass_ratio": (0.0, 1.0),
    "excellent_ratio": (0.0, 1.0),
    "default_full_score": (1.0, 1000.0),
}


def validate_config_value(key: str, value: str) -> str:
    """校验并归一化全局配置值，返回可直接写入 YAML 的值。

    白名单之外的键、类型不匹配、超出范围的值都会抛出 ValueError。
    """
    if key not in CONFIG_KEY_WHITELIST:
        raise ValueError(f"不允许修改的配置键: {key}")
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


def get_config_value(config_path: str, key: str) -> None:
    """读取全局配置项并打印。"""
    raise NotImplementedError("config get 将在后续实现")


def set_config_value(config_path: str, key: str, value: str) -> None:
    """修改全局配置项。

    TODO: validate_config_value 校验 -> 原子写入 -> 重新加载校验。
    """
    raise NotImplementedError("config set 将在后续实现")
