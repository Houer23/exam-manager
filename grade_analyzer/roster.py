"""名单核对。

名单文件：data/roster/<学期>.xlsx（单 sheet 长表：姓名/考号/性别/七选三/班级）
规范化文件：<学期>_normalized.xlsx；原始文件更新（mtime 更新）后自动重新生成。
核对：名单（全班学生）vs 该场考试有成绩学生 → 缺考/名单外/姓名不符。
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .cleaning import normalize_class_name
from .config import AnalysisConfig, ExamConfig
from .detect import resolve_exam_name
from .io_utils import write_excel_report
from .outputs import type_dir
from .storage import read_score_summary

NORMALIZED_SUFFIX = "_normalized"

# 选考科目简称（历史可用 史 或 历）
SUBJECT_ABBR = {
    "物理": {"物"},
    "化学": {"化"},
    "生物": {"生"},
    "历史": {"史", "历"},
    "政治": {"政"},
    "地理": {"地"},
    "技术": {"技"},
}


def _selects_subject(selection: str, subject: str | None) -> bool:
    """判断七选三是否包含某科目；非选考科目（如语数外）不过滤。"""
    if not subject:
        return True
    abbrs = SUBJECT_ABBR.get(subject)
    if not abbrs:
        return True
    return any(a in selection for a in abbrs)


def _roster_paths(roster_dir: str, semester: str) -> tuple[Path, Path]:
    raw = Path(roster_dir) / f"{semester}.xlsx"
    normalized = Path(roster_dir) / f"{semester}{NORMALIZED_SUFFIX}.xlsx"
    return raw, normalized


def _is_normalized_fresh(raw: Path, normalized: Path) -> bool:
    """规范化文件存在且不比原始文件旧（mtime）则视为可用。"""
    return (
        raw.is_file()
        and normalized.is_file()
        and normalized.stat().st_mtime >= raw.stat().st_mtime
    )


def clean_roster(
    raw_df: pd.DataFrame, config: AnalysisConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """清洗名单：考号/班级校验、班级规范化；异常行剔除并返回 (规范名单, 异常清单)。"""
    df = raw_df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    required = ["姓名", "考号", "性别", "七选三", "班级"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"名单缺少列: {missing}")

    def _text(v: object) -> str:
        if pd.isna(v):
            return ""
        if isinstance(v, (int, float)):
            return str(int(v)) if float(v).is_integer() else str(v)
        return str(v).strip()

    issues: list[tuple[str, str, str, str]] = []
    valid: list[dict] = []
    seen: set[str] = set()
    for _, row in df.iterrows():
        sid = _text(row["考号"])
        name = _text(row["姓名"])
        if sid in ("", "nan", "None") or not re.fullmatch(r"\d{12}", sid):
            issues.append((name, sid, "考号异常", f"考号={sid!r}"))
            continue
        if sid in seen:
            issues.append((name, sid, "考号重复", ""))
            continue
        seen.add(sid)
        cls = _text(row["班级"])
        if not cls:
            issues.append((name, sid, "班级缺失", ""))
            continue
        norm_cls, grade = normalize_class_name(cls, config.default_grade)
        if grade is None:
            issues.append((name, sid, "班级无法规范化", cls))
            continue
        valid.append(
            {
                "姓名": name,
                "考号": sid,
                "性别": _text(row["性别"]),
                "七选三": _text(row["七选三"]),
                "班级": norm_cls,
            }
        )
    roster_df = pd.DataFrame(valid, columns=["姓名", "考号", "性别", "七选三", "班级"])
    issues_df = pd.DataFrame(issues, columns=["姓名", "考号", "问题类型", "说明"])
    return roster_df, issues_df


def normalize_roster(
    config: AnalysisConfig, semester: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """读取原始名单清洗并保存规范化文件，返回 (规范名单, 异常清单)。"""
    raw_path, norm_path = _roster_paths(config.roster_dir, semester)
    if not raw_path.is_file():
        raise FileNotFoundError(f"名单文件不存在: {raw_path}")
    raw_df = pd.read_excel(raw_path)
    roster_df, issues_df = clean_roster(raw_df, config)

    norm_path.parent.mkdir(parents=True, exist_ok=True)
    write_excel_report(
        {"名单": roster_df, "异常": issues_df},
        str(norm_path),
    )
    return roster_df, issues_df


def load_roster(
    config: AnalysisConfig, semester: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """加载名单：优先规范化文件；缺失或过期则重新清洗生成。"""
    raw_path, norm_path = _roster_paths(config.roster_dir, semester)
    if not raw_path.is_file():
        return pd.DataFrame(), pd.DataFrame()
    if _is_normalized_fresh(raw_path, norm_path):
        return pd.read_excel(norm_path, sheet_name="名单"), pd.DataFrame()
    return normalize_roster(config, semester)


def verify_exam(
    exam: ExamConfig, score: pd.DataFrame, config: AnalysisConfig
) -> pd.DataFrame:
    """核对一场考试：名单（全班学生）vs 有成绩学生。返回差异清单并落盘。"""
    roster_df, _ = load_roster(config, exam.semester)
    if roster_df.empty:
        print(f"[名单核对] {exam.name}: 未找到名单或名单为空，跳过")
        return pd.DataFrame(columns=["班级", "考号", "姓名", "状态"])

    # 按七选三过滤：只核对选择了该科目的学生/班级
    if exam.filter_by_selection and exam.subject:
        roster_df = roster_df[
            roster_df["七选三"].map(lambda s: _selects_subject(s, exam.subject))
        ]
        if roster_df.empty:
            print(f"[名单核对] {exam.name}: 名单中无选择 {exam.subject} 的学生，跳过")
            return pd.DataFrame(columns=["班级", "考号", "姓名", "状态"])

    valid = score[score["total_score"].notna()]
    name_by = {}
    for _, r in roster_df.iterrows():
        name_by[(r["班级"], str(r["考号"]))] = r["姓名"]

    rows: list[tuple[str, str, str, str]] = []
    # 只核对名单中存在的班级；名单缺失的班级（如 16 班）直接跳过
    classes = sorted(set(roster_df["班级"]))
    for cls in classes:
        roster_ids = set(
            roster_df.loc[roster_df["班级"] == cls, "考号"].astype(str)
        )
        data = valid[valid["class_name"] == cls]
        data_ids = set(data["student_id"].astype(str))
        missing = sorted(roster_ids - data_ids)
        extra = sorted(data_ids - roster_ids)
        for sid in missing:
            rows.append((cls, sid, name_by.get((cls, sid), ""), "缺考/未参加"))
        for sid in extra:
            rows.append((cls, sid, "", "名单外"))
        for sid in sorted(roster_ids & data_ids):
            rname = name_by.get((cls, sid), "")
            match = data[data["student_id"].astype(str) == sid]
            dname = ""
            if len(match) and not pd.isna(match["name"].iloc[0]):
                dname = str(match["name"].iloc[0]).strip()
            if rname and dname and rname != dname:
                rows.append((cls, sid, rname, "姓名不符"))
        print(
            f"[名单核对] {exam.name} {cls}: 应考 {len(roster_ids)} "
            f"实考 {len(data_ids)} 缺考 {len(missing)} 名单外 {len(extra)}"
        )

    issues_df = pd.DataFrame(rows, columns=["班级", "考号", "姓名", "状态"])
    quality_dir = type_dir(config.output, "quality")
    quality_dir.mkdir(parents=True, exist_ok=True)
    out = quality_dir / f"名单核对_{exam.name}.csv"
    issues_df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[名单核对] {exam.name}: 差异清单已保存 {out}")
    return issues_df


def run_roster_check(
    config: AnalysisConfig,
    semester: str | None = None,
    exam_name: str | None = None,
) -> None:
    """roster check 命令：核对指定学期（默认当前学期）与考试。"""
    semester = semester or config.current_semester
    exams = list(config.exams)
    if semester:
        exams = [e for e in exams if e.semester == semester]
    if exam_name:
        exams = [e for e in exams if e.name == exam_name]
    if not exams:
        raise ValueError("筛选后无考试可核对")
    for exam in exams:
        if exam.name is None:
            exam.name = resolve_exam_name(exam)
        if not exam.name:
            continue
        try:
            score = read_score_summary(config.parsed_dir, exam, config.parsed_format)
        except FileNotFoundError as exc:
            print(f"[名单核对] 跳过 {exam.name}: {exc}")
            continue
        verify_exam(exam, score, config)
