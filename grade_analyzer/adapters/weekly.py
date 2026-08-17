"""格式 A 适配器：平时考试 / 周测（教学班报告）。

特征：表头含 序号/姓名/准考证号/自定义考号/班级/总分；
总分、客观分、主观分为权威列；另有 大题列（如 26）与 小题列（如 26(1)）。
考试名称从文件名提取（"--" 与 "】" 之间）。
"""

from __future__ import annotations

import re

import pandas as pd

from ..config import ExamConfig
from ..io_utils import read_raw_sheet
from .base import BaseAdapter, classify_question_header, classify_question_type


class WeeklyAdapter(BaseAdapter):
    """平时考试 / 周测 适配器。"""

    format_name = "weekly"

    @classmethod
    def detect(cls, df: pd.DataFrame) -> bool:
        """格式 A 特征：表头行同时含 自定义考号/总分/班级。"""
        for _, row in df.iterrows():
            cells = {str(v) for v in row.astype(str).tolist()}
            if {"自定义考号", "总分", "班级"} <= cells:
                return True
        return False

    def parse(self, exam: ExamConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
        """解析格式 A，返回 (科目总分表, 小题明细表)。"""
        if not exam.name:
            raise ValueError(f"{exam.full_path}: 考试名称未解析（请先运行 check）")
        if not exam.subject:
            raise ValueError(f"{exam.full_path}: 科目未解析（请先运行 check）")

        raw = read_raw_sheet(exam.full_path)
        header_idx = self._find_header(raw)
        if header_idx is None:
            raise ValueError(f"{exam.full_path}: 未找到表头行（缺少 自定义考号/总分/班级）")

        header = raw.iloc[header_idx]
        col = {str(v).strip(): j for j, v in enumerate(header.tolist())}

        def col_idx(name: str) -> int:
            if name not in col:
                raise ValueError(f"{exam.full_path}: 表头缺少 {name}")
            return col[name]

        id_col = col_idx("自定义考号")
        name_col = col_idx("姓名")
        class_col = col_idx("班级")
        total_col = col_idx("总分")
        obj_col = col_idx("客观分")
        subj_col = col_idx("主观分")
        essay_col = col_idx("解答题")

        data = raw.iloc[header_idx + 1 :].copy()
        id_series = data.iloc[:, id_col].map(lambda v: str(v).strip())
        valid = id_series.str.fullmatch(r"\d{12}")
        data = data[valid].reset_index(drop=True)
        if data.empty:
            raise ValueError(f"{exam.full_path}: 未找到有效的 12 位考号数据行")
        id_series = data.iloc[:, id_col].map(lambda v: str(v).strip())

        def to_num(series: pd.Series) -> pd.Series:
            return pd.to_numeric(series, errors="coerce")

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
                "class_name": None,
                "class_raw": data.iloc[:, class_col].map(
                    lambda v: "" if pd.isna(v) else str(v).strip()
                ),
                "grade": None,
                "school": None,
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

        # 小题列：解答题 之后的题号列（纯数字 / 括号 / 短横线三种形式）
        q_cols: list[tuple[int, str]] = []
        for j, v in enumerate(header.tolist()):
            h = str(v).strip()
            if j <= essay_col:
                continue
            # 数值表头 1.0 -> 1（Excel 可能把数字题号存成数值）
            h_norm = re.sub(r"\.0$", "", h) if re.fullmatch(r"\d+\.0", h) else h
            if classify_question_header(h_norm):
                q_cols.append((j, h_norm))

        # 跳过纯数字但存在子题的大题汇总列（如 26，其后有 26(1)/26-1/26（1））
        question_cols = [
            (j, h)
            for j, h in q_cols
            if not (
                re.fullmatch(r"\d+", h)
                and any(
                    h2.startswith(f"{h}-")
                    or h2.startswith(f"{h}(")
                    or h2.startswith(f"{h}（")
                    for _, h2 in q_cols
                )
            )
        ]

        frames: list[pd.DataFrame] = []
        for j, h in question_cols:
            qid, qtype = classify_question_type(h, exam.objective_question_count)
            frames.append(
                pd.DataFrame(
                    {
                        "exam_name": exam.name,
                        "student_id": id_series,
                        "question_id": qid,
                        "question_type": qtype,
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

    @staticmethod
    def _find_header(raw: pd.DataFrame) -> int | None:
        """定位格式 A 表头行（同时含 自定义考号/总分/班级）。"""
        for i, row in raw.iterrows():
            cells = {str(v).strip() for v in row.tolist()}
            if {"自定义考号", "总分", "班级"} <= cells:
                return i
        return None
