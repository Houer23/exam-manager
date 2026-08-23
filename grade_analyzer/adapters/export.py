"""平台成绩导出格式适配器（export）。

特征：单 sheet、第 0 行为表头；基础列含 学校/考生号/任课教师/班级(数字码)/
总分/客观分/主观分；客观题列为 选择题_N（得分列 + 选择项列两列一组）；
主观小题列为 第X（Y）题（全角/半角括号）。

规范表输出：
- class_name/class_raw 均为班级码映射后的 高一XX班（2501-2516 -> 高一01-16班）；
- 任课教师/层次由清洗阶段按配置（class_name）填充，不使用文件内 任课教师 列；
- 选择题选择项列与知识点得分列不进入小题明细。
"""

from __future__ import annotations

import re

import pandas as pd

from ..config import ExamConfig
from ..io_utils import read_raw_sheet
from .base import BaseAdapter

_HEADER_COLS = {"考生号", "姓名", "班级", "总分", "客观分", "主观分"}
_OBJ_RE = re.compile(r"^选择题_(\d+)$")
_SUBJ_RE = re.compile(
    r"^第(\d+)（(\d+)）题$|^第(\d+)\((\d+)\)题$"
)
_CLASS_CODE_RE = re.compile(r"^25(\d{2})$")


def _class_code_to_name(value) -> str:
    """班级数字码 2501-2516 -> 高一01-16班（"25" 前缀 + 末两位班号）。"""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    m = _CLASS_CODE_RE.fullmatch(text)
    if m:
        return f"高一{int(m.group(1)):02d}班"
    return text


def _parse_export_frame(raw: pd.DataFrame, exam: ExamConfig):
    """解析平台导出帧（第 0 行为表头），返回 (科目总分表, 小题明细表)。"""
    header = raw.iloc[0]
    col = {str(v).strip(): j for j, v in enumerate(header.tolist())}
    missing = [c for c in _HEADER_COLS if c not in col]
    if missing:
        raise ValueError(f"{exam.full_path}: 表头缺少列 {missing}（格式 export）")

    id_col = col["考生号"]
    name_col = col["姓名"]
    class_col = col["班级"]
    total_col = col["总分"]
    obj_col = col["客观分"]
    subj_col = col["主观分"]
    school_col = col.get("学校")

    data = raw.iloc[1:].copy()
    id_series = data.iloc[:, id_col].map(lambda v: str(v).strip())
    valid = id_series.str.fullmatch(r"\d{12}")
    data = data[valid].reset_index(drop=True)
    if data.empty:
        raise ValueError(f"{exam.full_path}: 未找到有效的 12 位考号数据行")
    id_series = data.iloc[:, id_col].map(lambda v: str(v).strip())

    def to_num(series: pd.Series) -> pd.Series:
        return pd.to_numeric(series, errors="coerce")

    class_names = data.iloc[:, class_col].map(_class_code_to_name)
    fs = exam.full_score
    ofs = exam.objective_full_score
    sfs = exam.subjective_full_score
    score_df = pd.DataFrame(
        {
            "exam_name": exam.name,
            "exam_type": exam.type,
            "exam_date": exam.date,
            "student_id": id_series,
            "name": data.iloc[:, name_col].map(
                lambda v: "" if pd.isna(v) else str(v).strip()
            ),
            "class_name": class_names,
            "class_raw": class_names,
            "grade": None,
            "school": (
                data.iloc[:, school_col].map(
                    lambda v: "" if pd.isna(v) else str(v).strip()
                )
                if school_col is not None
                else None
            ),
            "subject": exam.subject,
            "total_score": to_num(data.iloc[:, total_col]),
            "objective_score": to_num(data.iloc[:, obj_col]),
            "subjective_score": to_num(data.iloc[:, subj_col]),
            "full_score": fs,
            "objective_full_score": ofs,
            "subjective_full_score": sfs,
        }
    )
    score_df["total_ratio"] = (
        (score_df["total_score"] / fs).round(5) if fs else float("nan")
    )
    score_df["objective_ratio"] = (
        (score_df["objective_score"] / ofs).round(5) if ofs else float("nan")
    )
    score_df["subjective_ratio"] = (
        (score_df["subjective_score"] / sfs).round(5) if sfs else float("nan")
    )

    frames: list[pd.DataFrame] = []
    for h, j in col.items():
        m_obj = _OBJ_RE.fullmatch(h)
        if m_obj:
            qid = str(int(m_obj.group(1)))
            frames.append(
                pd.DataFrame(
                    {
                        "exam_name": exam.name,
                        "student_id": id_series,
                        "question_id": qid,
                        "question_type": "客观",
                        "score": to_num(data.iloc[:, j]),
                        "full_score": None,
                    }
                )
            )
            continue
        m_sub = _SUBJ_RE.match(h)
        if m_sub:
            g = m_sub.groups()
            base, sub = (g[0], g[1]) if g[0] else (g[2], g[3])
            qid = f"{base}-{sub}"
            frames.append(
                pd.DataFrame(
                    {
                        "exam_name": exam.name,
                        "student_id": id_series,
                        "question_id": qid,
                        "question_type": "主观",
                        "score": to_num(data.iloc[:, j]),
                        "full_score": None,
                    }
                )
            )
    if frames:
        question_df = pd.concat(frames, ignore_index=True)
    else:
        question_df = pd.DataFrame(
            columns=[
                "exam_name", "student_id", "question_id",
                "question_type", "score", "full_score",
            ]
        )
    return score_df, question_df


class ExportAdapter(BaseAdapter):
    """平台成绩导出格式适配器（export）。"""

    format_name = "export"

    @classmethod
    def detect(cls, df: pd.DataFrame) -> bool:
        """特征：第 0 行表头同时含 考生号/任课教师/选择题_1。"""
        header = {str(v).strip() for v in df.iloc[0].tolist()}
        return {"考生号", "任课教师", "选择题_1"} <= header

    def parse(self, exam: ExamConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
        """解析一场 export 格式考试。"""
        if not exam.name:
            raise ValueError(f"{exam.full_path}: 考试名称未解析（请先运行 check）")
        if not exam.subject:
            raise ValueError(f"{exam.full_path}: 科目未解析（请先运行 check）")
        raw = read_raw_sheet(exam.full_path, sheet=exam.sheet)
        return _parse_export_frame(raw, exam)
