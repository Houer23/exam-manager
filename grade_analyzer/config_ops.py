"""CLI 配置修改操作。

exam add/update/remove/list：考试条目管理（写 config/exams/ 下的 yaml）；
config get/set：全局配置管理（白名单 + 类型/范围校验）。

安全机制：原子写入、修改后自动校验、冲突检测、不触碰原始成绩文件。
"""

from __future__ import annotations

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


def list_exams(config_path: str, semester: str | None = None) -> None:
    """列出考试条目（名称/学期/格式/类型/日期/满分）。"""
    raise NotImplementedError("exam list 将在后续实现")


def get_config_value(config_path: str, key: str) -> None:
    """读取全局配置项并打印。"""
    raise NotImplementedError("config get 将在后续实现")


def set_config_value(config_path: str, key: str, value: str) -> None:
    """修改全局配置项。

    TODO: validate_config_value 校验 -> 原子写入 -> 重新加载校验。
    """
    raise NotImplementedError("config set 将在后续实现")
