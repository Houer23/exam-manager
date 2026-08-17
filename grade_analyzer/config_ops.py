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

from .adapters.registry import known_format_hint
from .config import (
    AnalysisConfig,
    ExamConfig,
    _load_exam_file,
    discover_exam_files,
    load_config,
    normalize_exam_name,
    semester_abbr,
)
from .detect import (
    detect_subject_from_filename,
    extract_exam_name_from_filename,
    resolve_exam_name,
)
from .storage import is_exam_deleted, is_parsed_fresh, mark_exam_deleted, parsed_exam_dir

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
    short_name: str | None = None,
    question_display: str | None = None,
    show_big_questions: bool | None = None,
    filter_by_selection: bool | None = None,
) -> None:
    """新增考试条目，写入 config/exams/<学期>/<文件名>.yaml。

    参数式：传入 folder/file 等参数直接生成条目；
    交互式：file 为空时对模板全部配置项逐一问答，必填项（file/semester/subject/name）优先。
    文件名用不带学期的规范名称（学科+考试名）。
    """
    config = load_config(config_path)
    interactive = file is None
    if interactive:
        # 必填项优先
        file = _ask("成绩文件名（必填）", None, required=True)
        semester = _ask(
            "学期全称（必填）", None,
            default=config.current_semester, required=True,
        )
        subject = _ask(
            "科目（必填）", None,
            default=detect_subject_from_filename(
                file, config.subjects, config.subject_aliases
            ),
            required=True,
        )
        defaults = config.defaults_for(subject) if subject else None
        name = _ask(
            "考试名称（必填）", None,
            default=extract_exam_name_from_filename(file), required=True,
        )
        # 其余配置项按模板顺序逐一输入（回车用默认值）
        date = _ask("考试日期（YYYY-MM-DD）", None, default=date)
        folder = _ask("成绩文件所在文件夹", None, default=config.input_dir)
        short_name = _ask("考试简称（留空=用考试全称）", None)
        question_display = _ask(
            "小题呈现（split/merged）", None, default="split"
        )
        show_big_questions = _ask(
            "是否显示主观大题汇总（true/false）", None, default="false"
        )
        fmt = _ask(
            f"格式（{known_format_hint()}，留空=自动识别）", None
        )
        exam_type = _ask("考试类型", None, default="默认")
        importance = _ask("重要度（平时/联考，留空=由格式推导）", None)
        full_score = _ask(
            "总分满分（留空=科目默认）", None,
            default=_fmt_default(defaults.full_score) if defaults else None,
        )
        objective_full_score = _ask(
            "客观题满分（留空=科目默认）", None,
            default=_fmt_default(defaults.objective_full_score) if defaults else None,
        )
        subjective_full_score = _ask(
            "主观题满分（留空=科目默认）", None,
            default=_fmt_default(defaults.subjective_full_score) if defaults else None,
        )
        default_grade = _ask("默认年级", None, default=config.default_grade)
        sheet = _ask("Sheet 名（留空=自动选择）", None)
        filter_by_selection = _ask(
            "名单核对按七选三过滤（true/false）", None, default="true"
        )
    else:
        if not semester:
            raise ValueError("semester 必填（参数或交互输入）")
        if subject is None:
            subject = detect_subject_from_filename(
                file, config.subjects, config.subject_aliases
            )

    raw_name = name
    if not raw_name:
        raw_name = extract_exam_name_from_filename(file)
    full_name = normalize_exam_name(
        raw_name, semester, subject, config.subject_aliases
    )
    if not full_name:
        full_name = _ask("考试名称（必填）", None, required=True)
        full_name = normalize_exam_name(
            full_name, semester, subject, config.subject_aliases
        )

    if not subject:
        raise ValueError("科目（subject）必填")
    if not full_name:
        raise ValueError("考试名称（name）必填")

    existing = _exam_file_map(config)
    if full_name in existing:
        raise ValueError(f"考试名称重复: {full_name}")

    folder = folder or config.input_dir
    abbr = semester_abbr(semester)
    stem = full_name[len(abbr):] if abbr and full_name.startswith(abbr) else full_name
    exam_dir = Path(config.exams_dir) / semester
    exam_dir.mkdir(parents=True, exist_ok=True)
    target = exam_dir / f"{stem}.yaml"
    if target.exists():
        raise ValueError(f"条目文件已存在: {target}")

    def _to_float(v):
        if v in (None, ""):
            return None
        return float(v)

    def _to_bool(v):
        if v in (None, ""):
            return None
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in ("true", "1", "yes", "是")

    fields = [
        ("subject", subject),
        ("semester", semester),
        ("date", date),
        ("folder", folder),
        ("file", file),
        ("name", full_name),
        ("short_name", short_name),
        ("question_display", question_display),
        ("show_big_questions", _to_bool(show_big_questions)),
        ("format", fmt),
        ("type", exam_type or "默认"),
        ("importance", importance),
        ("full_score", _to_float(full_score)),
        ("objective_full_score", _to_float(objective_full_score)),
        ("subjective_full_score", _to_float(subjective_full_score)),
        ("default_grade", default_grade),
        ("sheet", sheet),
        ("filter_by_selection", _to_bool(filter_by_selection)),
    ]
    data = {k: v for k, v in fields if v not in (None, "")}
    _write_exam_entry(target, data, config, semester)
    try:
        load_config(config_path)  # 全量校验
    except Exception:
        target.unlink(missing_ok=True)
        raise
    print(f"[完成] 已新增考试条目: {full_name} -> {target}")


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
    """修改考试条目字段；semester 变更时自动移动文件到新学期目录。"""
    config = load_config(config_path)
    existing = _exam_file_map(config)
    if name not in existing:
        raise ValueError(f"考试条目不存在: {name}")
    exam, path = existing[name]

    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    updates = {
        "folder": folder, "file": file, "subject": subject, "date": date,
        "format": fmt, "type": exam_type, "importance": importance,
        "full_score": full_score,
        "objective_full_score": objective_full_score,
        "subjective_full_score": subjective_full_score,
        "default_grade": default_grade, "sheet": sheet,
    }
    for k, v in updates.items():
        if v is not None:
            raw[k] = v

    new_semester = semester or exam.semester
    target = path
    if new_semester != exam.semester:
        raw["semester"] = new_semester
        old_abbr = semester_abbr(exam.semester)
        base = raw.get("name") or exam.name or ""
        if old_abbr and base.startswith(old_abbr):
            base = base[len(old_abbr):]
        raw["name"] = normalize_exam_name(
            base,
            new_semester,
            raw.get("subject") or exam.subject,
            config.subject_aliases,
        )
        new_dir = Path(config.exams_dir) / new_semester
        new_dir.mkdir(parents=True, exist_ok=True)
        target = new_dir / path.name
        if target.exists():
            raise ValueError(f"目标文件已存在: {target}")

    backup = path.read_text(encoding="utf-8")
    _write_exam_entry(target, raw, config, new_semester)
    if target != path and path.exists():
        path.unlink()
    try:
        load_config(config_path)
    except Exception:
        path.write_text(backup, encoding="utf-8")  # 回滚
        if target != path and target.exists():
            target.unlink()
        raise
    print(f"[完成] 已更新考试条目: {name}")


def remove_exam(config_path: str, name: str) -> None:
    """删除考试条目文件。

    保留规范表缓存，并在缓存目录写入删除标记（storage.mark_exam_deleted）。
    """
    config = load_config(config_path)
    existing = _exam_file_map(config)
    if name not in existing:
        raise ValueError(f"考试条目不存在: {name}")
    exam, path = existing[name]

    backup = path.read_text(encoding="utf-8")
    path.unlink()
    try:
        load_config(config_path)
    except Exception:
        path.write_text(backup, encoding="utf-8")  # 回滚
        raise
    mark_exam_deleted(config.parsed_dir, exam)
    print(f"[完成] 已删除考试条目: {name}（规范表缓存保留，已标记删除）")


def _exam_file_map(
    config: AnalysisConfig,
) -> dict[str, tuple[ExamConfig, Path]]:
    """返回 {规范考试名: (ExamConfig, 条目文件路径)}。"""
    result: dict[str, tuple[ExamConfig, Path]] = {}
    for path, folder_semester in discover_exam_files(config.exams_dir):
        exam = _load_exam_file(
            Path(path), folder_semester, config.subject_aliases, config.input_dir
        )
        if exam.name:
            result[exam.name] = (exam, Path(path))
    return result


def _write_exam_entry(
    target: Path, data: dict, config: AnalysisConfig, semester: str
) -> None:
    """写临时文件 -> 单文件校验 -> 原子替换。"""
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    try:
        _load_exam_file(tmp, semester, config.subject_aliases, config.input_dir)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, target)


def _ask(
    label: str, value: str | None, default: str | None = None, required: bool = False
) -> str | None:
    """交互式问答：value 有值时直接返回，否则读取用户输入。"""
    if value is not None:
        return value
    prompt = f"{label}"
    if default is not None:
        prompt += f"（默认: {default}）"
    prompt += ": "
    answer = input(prompt).strip()
    if not answer and default is not None:
        return default
    if not answer and required:
        raise ValueError(f"{label} 必填")
    return answer or None


def _fmt_default(value: float | None) -> str | None:
    """数值默认值格式化为提示文本。"""
    return f"{value:g}" if value is not None else None


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
                "删除": "已删除" if is_exam_deleted(config.parsed_dir, exam) else "",
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "考试名称", "学期", "考试类型", "格式", "科目", "日期",
            "满分", "检查", "成绩单", "删除",
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
