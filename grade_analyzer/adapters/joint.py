"""格式 B 适配器：联考（原始数据）。

特征：表头为 姓名/考号/学校/班级 + 答案区（题 1~N）+
得分区（客观题得分列 + 主观小题列 N-M）；
无总分/客观分/主观分列，全部由得分列求和得到。
题型分类（地理）：纯数字题号 = 客观题；"N-M" 题号 = 主观题。
题量动态识别，不写死。答案列不进入规范表。
"""

from __future__ import annotations

import re

import pandas as pd

from ..config import ExamConfig
from ..io_utils import read_raw_sheet
from ..question_types import resolve_question_types
from .base import BaseAdapter, classify_question_header, classify_question_type


class JointAdapter(BaseAdapter):
    """联考 适配器。"""

    format_name = "joint"

    @classmethod
    def detect(cls, df: pd.DataFrame) -> bool:
        """格式 B 特征：表头行含 考号/学校/班级，且其后存在字母答案列。"""
        header_idx = None
        for i, row in df.iterrows():
            cells = {str(v) for v in row.astype(str).tolist()}
            if {"考号", "学校", "班级"} <= cells:
                header_idx = i
                break
        if header_idx is None:
            return False
        letters = {"A", "B", "C", "D"}
        tail = df.iloc[header_idx + 1 : header_idx + 6]
        for _, row in tail.iterrows():
            for v in row.tolist():
                s = str(v).strip()
                if s and set(s) <= letters:
                    return True
        return False

    def parse(self, exam: ExamConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
        """解析格式 B，返回 (科目总分表, 小题明细表)。"""
        if not exam.name:
            raise ValueError(f"{exam.full_path}: 考试名称未解析（请先运行 check）")
        if not exam.subject:
            raise ValueError(f"{exam.full_path}: 科目未解析（请先运行 check）")

        raw = read_raw_sheet(exam.full_path, sheet=exam.sheet)
        plan = resolve_question_types(
            exam.question_types, exam.binary_split, exam.objective_question_count
        )

        def obj_subj_type(h: str) -> str | None:
            """返回题号所属 客观/主观 顶层（用于 客观分/主观分 聚合）。"""
            parsed = classify_question_header(h)
            if not parsed:
                return None
            qid, _ = parsed
            base = int(qid.split("-")[0])
            if plan is not None:
                top = plan.top_of(base)
                return top if top in ("客观", "主观") else None
            return classify_question_type(
                h, objective_count=exam.objective_question_count
            )[1]
        header_idx = self._find_header(raw)
        if header_idx is None:
            raise ValueError(f"{exam.full_path}: 未找到表头行（缺少 考号/学校/班级）")

        header = raw.iloc[header_idx]
        col = {str(v).strip(): j for j, v in enumerate(header.tolist())}

        def col_idx(name: str) -> int:
            if name not in col:
                raise ValueError(f"{exam.full_path}: 表头缺少 {name}")
            return col[name]

        id_col = col_idx("考号")
        name_col = col_idx("姓名")
        school_col = col_idx("学校")
        class_col = col_idx("班级")

        data = raw.iloc[header_idx + 1 :].copy()
        id_series = data.iloc[:, id_col].map(lambda v: str(v).strip())
        valid = id_series.str.fullmatch(r"\d{12}")
        data = data[valid].reset_index(drop=True)
        if data.empty:
            raise ValueError(f"{exam.full_path}: 未找到有效的 12 位考号数据行")
        id_series = data.iloc[:, id_col].map(lambda v: str(v).strip())

        # 候选题列：整数题号（答案区/客观得分区）与 主观小题题号
        # （全角/半角括号、短横线三种形式，统一归一化）
        q_cols: list[tuple[int, str]] = []
        for j, v in enumerate(header.tolist()):
            h = str(v).strip()
            if h in {"姓名", "考号", "学校", "班级"}:
                continue
            # 数值表头 1.0 -> 1（客观题得分区）
            h_norm = re.sub(r"\.0$", "", h) if re.fullmatch(r"\d+\.0", h) else h
            if classify_question_header(h_norm):
                q_cols.append((j, h_norm))

        def is_numeric_col(j: int) -> bool:
            return pd.to_numeric(data.iloc[:, j], errors="coerce").notna().any()

        # 答案列（字母）不是数值列，自动丢弃
        score_cols = [(j, h) for j, h in q_cols if is_numeric_col(j)]
        obj_cols = [
            (j, h)
            for j, h in score_cols
            if obj_subj_type(h) == "客观"
        ]
        subj_cols = [
            (j, h)
            for j, h in score_cols
            if obj_subj_type(h) == "主观"
        ]
        if not score_cols:
            raise ValueError(f"{exam.full_path}: 未找到得分列")

        def to_num(series: pd.Series) -> pd.Series:
            return pd.to_numeric(series, errors="coerce")

        objective = (
            sum(to_num(data.iloc[:, j]) for j, _ in obj_cols)
            if obj_cols
            else pd.Series(float("nan"), index=data.index)
        )
        subjective = (
            sum(to_num(data.iloc[:, j]) for j, _ in subj_cols)
            if subj_cols
            else pd.Series(float("nan"), index=data.index)
        )
        total = objective + subjective

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
                "school": data.iloc[:, school_col].map(
                    lambda v: "" if pd.isna(v) else str(v).strip()
                ),
                "subject": exam.subject,
                "total_score": total,
                "objective_score": objective,
                "subjective_score": subjective,
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
        for j, h in obj_cols:
            qid, qtype = classify_question_type(
                h, plan=plan, objective_count=exam.objective_question_count
            )
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
        for j, h in subj_cols:
            qid, qtype = classify_question_type(
                h, plan=plan, objective_count=exam.objective_question_count
            )
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
        """定位格式 B 表头行（同时含 考号/学校/班级）。"""
        for i, row in raw.iterrows():
            cells = {str(v).strip() for v in row.tolist()}
            if {"考号", "学校", "班级"} <= cells:
                return i
        return None
