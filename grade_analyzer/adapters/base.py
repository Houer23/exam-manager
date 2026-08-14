"""适配器接口定义。

分析层只依赖规范表，不接触原始格式；
新增一种成绩单格式时，实现一个 BaseAdapter 子类并注册即可。
"""

from __future__ import annotations

import abc
import re

import pandas as pd

from ..config import ExamConfig


_QUESTION_HEADER_PATTERNS = [
    re.compile(r"^(\d+)$"),               # 客观题：1
    re.compile(r"^(\d+)[（(](\d+)[)）]$"),  # 主观小题：26(1) / 26（1）
    re.compile(r"^(\d+)-(\d+)$"),         # 主观小题：26-1
]


def classify_question_header(header: str) -> tuple[str, str] | None:
    """识别题号表头，返回 (规范题号, 题型)；无法识别返回 None。

    规范题号：客观题 "N"；主观小题 "N-M"（全角/半角括号、短横线统一为短横线）。
    """
    for pattern in _QUESTION_HEADER_PATTERNS:
        match = pattern.fullmatch(header)
        if not match:
            continue
        if len(match.groups()) == 1:
            return match.group(1), "客观"
        return f"{match.group(1)}-{match.group(2)}", "主观"
    return None


class BaseAdapter(abc.ABC):
    """格式适配器基类。"""

    #: 格式标识，用于 registry 映射（如 weekly / joint）
    format_name: str = ""

    @classmethod
    @abc.abstractmethod
    def detect(cls, df: pd.DataFrame) -> bool:
        """判断表头特征是否匹配本格式（用于自动识别考试类型）。

        TODO: 各适配器实现特征列检查，如 weekly 含"自定义考号/总分"，
        joint 含"考号/学校"及答案区。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def parse(self, exam: ExamConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
        """解析一场考试，返回 (科目总分表, 小题明细表)。

        科目总分表字段：
            exam_name, exam_type, exam_date, student_id, name, class_name, class_raw, grade,
            school, subject, total_score, objective_score, subjective_score,
            full_score, objective_full_score, subjective_full_score,
            total_ratio, objective_ratio, subjective_ratio,
            单选分, 多选分, 单选满分, 多选满分, 班次, 校次,
            class_level, course, teacher

        小题明细表字段：
            exam_name, student_id, question_id, question_type, score, full_score
            （question_type: 单选/多选/主观，由清洗阶段按实际最高得分区分）
        """
        raise NotImplementedError
