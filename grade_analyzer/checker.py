"""识别预览与校验清单（check 命令核心）。

对每个考试条目：
1. 读取原始文件，运行格式/名称/科目识别；
2. 生成识别预览（格式/名称/科目/班级样例/满分建议）；
3. 逐项校验（PASS / WARN / FAIL），FAIL 定位到字段并给出建议。

只读不写，不生成任何文件；返回有问题（FAIL）的场次数。
"""

from __future__ import annotations

import pandas as pd

from .adapters.registry import auto_detect_format
from .config import AnalysisConfig, ExamConfig, normalize_exam_name
from .detect import detect_subject_from_filename, extract_exam_name_from_filename
from .io_utils import read_raw_sheet
from .quality import write_check_reports
from .storage import read_score_summary


def _extract_class_samples(raw: pd.DataFrame, limit: int = 3) -> list[str]:
    """通用扫描：找含"班级"的表头行，取后续数据行的班级列去重样例。"""
    header_idx = None
    class_col = None
    for i, row in raw.iterrows():
        for j, v in enumerate(row.tolist()):
            if str(v).strip() == "班级":
                header_idx = i
                class_col = j
                break
        if header_idx is not None:
            break
    if header_idx is None or class_col is None:
        return []
    samples: list[str] = []
    seen: set[str] = set()
    for i in range(header_idx + 1, min(header_idx + 51, len(raw))):
        s = str(raw.iloc[i, class_col]).strip()
        if not s or s.lower() == "nan" or s in seen:
            continue
        seen.add(s)
        samples.append(s)
        if len(samples) >= limit:
            break
    return samples


def check_exam(exam: ExamConfig, config: AnalysisConfig) -> dict:
    """检查单场考试，返回识别预览与校验结果。"""
    result: dict = {"exam": exam, "checks": [], "preview": {}}

    def add_check(name: str, status: str, detail: str) -> None:
        result["checks"].append((name, status, detail))

    raw = None
    try:
        raw = read_raw_sheet(exam.full_path)
        add_check("文件", "PASS", f"{exam.full_path}（{raw.shape[0]} 行 × {raw.shape[1]} 列）")
    except (FileNotFoundError, ValueError) as exc:
        add_check("文件", "FAIL", str(exc))
        result["preview"] = {
            "格式": exam.format,
            "名称": exam.name,
            "科目": exam.subject,
        }
        return result

    fmt = exam.format or auto_detect_format(raw)
    if fmt:
        add_check("格式", "PASS", fmt)
    else:
        add_check("格式", "FAIL", "无法识别，请手动指定 format（weekly/joint）")
    result["preview"]["格式"] = fmt

    name = exam.name
    name_source = "配置"
    if name is None:
        extracted = extract_exam_name_from_filename(exam.full_path)
        name = normalize_exam_name(extracted, exam.semester) if extracted else None
        name_source = "文件名提取"
    if name:
        exam.name = name  # 供规范表路径解析使用
        add_check("名称", "PASS", f"{name}（来源：{name_source}）")
    else:
        add_check("名称", "WARN", "无法解析考试名称，请手动指定 name")
    result["preview"]["名称"] = name

    if exam.short_name:
        add_check("考试简称", "PASS", exam.short_name)
    else:
        add_check("考试简称", "FAIL", "short_name 必填（个人成绩单内使用）")

    subject = exam.subject
    subject_source = "配置"
    if subject is None:
        subject = detect_subject_from_filename(
            exam.full_path, config.subjects, config.subject_aliases
        )
        subject_source = "文件名推测"
    if subject:
        add_check("科目", "PASS", f"{subject}（来源：{subject_source}）")
    else:
        add_check("科目", "WARN", "无法推测科目，请手动指定 subject")
    result["preview"]["科目"] = subject

    samples = _extract_class_samples(raw)
    if samples:
        add_check("班级样例", "PASS", ", ".join(samples))
    else:
        add_check("班级样例", "WARN", "未找到班级列")
    result["preview"]["班级样例"] = samples

    defaults = config.defaults_for(subject) if subject else None
    full_score = exam.full_score or (defaults.full_score if defaults else None)
    objective = exam.objective_full_score or (
        defaults.objective_full_score if defaults else None
    )
    subjective = exam.subjective_full_score or (
        defaults.subjective_full_score if defaults else None
    )
    if full_score:
        add_check(
            "满分",
            "PASS",
            f"总分 {full_score:g}  客观 {objective if objective else '-'}  "
            f"主观 {subjective if subjective else '-'}",
        )
    else:
        add_check("满分", "WARN", "无满分来源（条目或科目默认）")
    result["preview"]["满分"] = (full_score, objective, subjective)

    # 元数据覆盖比对：有成绩的班级 vs 班级/学科配置（需要已解析的规范表）
    try:
        parsed = read_score_summary(config.parsed_dir, exam, config.parsed_format)
        for check_name, detail in _metadata_coverage_checks(parsed, exam, config):
            add_check(check_name, "WARN", detail)
    except (FileNotFoundError, ValueError) as exc:
        add_check("元数据覆盖", "WARN", f"跳过比对（{exc}）")
    return result


def _metadata_coverage_checks(
    score: pd.DataFrame, exam: ExamConfig, config: AnalysisConfig
) -> list[tuple[str, str]]:
    """返回有成绩班级与班级/学科配置的覆盖差异清单。"""
    checks: list[tuple[str, str]] = []
    valid = score[score["total_score"].notna()]
    if valid.empty:
        return checks
    data_classes = set(valid["class_name"])
    teacher_map = config.teacher_maps.get((exam.semester, exam.subject))
    config_classes = set(teacher_map.class_teachers) if teacher_map else set()

    missing = sorted(data_classes - config_classes)
    if missing:
        checks.append(("教师配置", f"有成绩但未配置教师的班级: {missing}"))
    extra = sorted(config_classes - data_classes)
    if extra:
        checks.append(("教师配置", f"学科配置中但本次数据未出现的班级: {extra}"))
    no_class_info = sorted(
        c for c in data_classes if config.class_info(exam.semester, c) is None
    )
    if no_class_info:
        checks.append(("班级配置", f"未配置 level/course 的班级: {no_class_info}"))
    return checks


def run_check(config: AnalysisConfig) -> int:
    """对所有考试条目执行 check，打印识别预览与校验清单，返回有 FAIL 的场次数。"""
    problems = 0
    checks_by_exam: dict[str, list[tuple[str, str, str]]] = {}
    for exam in config.exams:
        result = check_exam(exam, config)
        name = result["preview"].get("名称") or "（未命名）"
        print(f"=== 检查: {name} ===")
        for check_name, status, detail in result["checks"]:
            print(f"  {check_name}: {detail}  [{status}]")
        checks_by_exam[name] = result["checks"]
        if any(status == "FAIL" for _, status, _ in result["checks"]):
            problems += 1
    for path in write_check_reports(config, checks_by_exam):
        print(f"[质量] {path}")
    print(f"=== 汇总: {len(config.exams)} 场检查, {problems} 场有问题 ===")
    return problems
