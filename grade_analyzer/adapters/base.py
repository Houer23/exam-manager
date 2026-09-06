"""适配器接口定义。

分析层只依赖规范表，不接触原始格式；
新增一种成绩单格式时，实现一个 BaseAdapter 子类并注册即可。
"""

from __future__ import annotations

import abc
import re

import pandas as pd

from ..config import ExamConfig
from ..question_types import QuestionTypePlan


_QUESTION_HEADER_PATTERNS = [
    re.compile(r"^(\d+)$"),               # 客观题：1
    re.compile(r"^(\d+)[（(](\d+)[)）]$"),  # 主观小题：26(1) / 26（1）
    re.compile(r"^(\d+)-(\d+)$"),         # 主观小题：26-1
]

# 主观分组题号（一列对应多个小题/圈码）：17(1)(2)、19(1)(2)(3)①、19(3)②(4)
_GROUPED_SUB_RE = re.compile(r"^(\d+)(?:[（(]\d+[）)]|[\u2460-\u2473])+$")
# 数字 + 汉字后缀（平台在题号后附题型名/说明）：23作文
_CHINESE_SUFFIX_RE = re.compile(r"^(\d+)[\u4e00-\u9fff]+$")
_FULL_TO_HALF_PAREN = str.maketrans({"（": "(", "）": ")"})


def classify_question_header(header: str) -> tuple[str, str] | None:
    """识别题号表头，返回 (规范题号, 题型)；无法识别返回 None。

    规范题号：
    - 客观题 "N"；
    - 主观小题（单个小题）"N-M"（全角/半角括号、短横线统一为短横线）；
    - 主观分组（一列含多个小题号/圈码）保留括号形式，如 "17(1)(2)"、"19(1)(2)(3)①"。
    - 数字 + 汉字后缀（如 "23作文"）按纯数字题号处理，默认归入主观题。
    """
    text = str(header).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+", text):
        return text, "客观"
    m = _CHINESE_SUFFIX_RE.fullmatch(text)
    if m:
        return m.group(1), "主观"
    m = _QUESTION_HEADER_PATTERNS[1].fullmatch(text)  # 单个小题 26(1) / 26（1）
    if m:
        return f"{m.group(1)}-{m.group(2)}", "主观"
    m = _QUESTION_HEADER_PATTERNS[2].fullmatch(text)  # 短横线 26-1
    if m:
        return f"{m.group(1)}-{m.group(2)}", "主观"
    if _GROUPED_SUB_RE.fullmatch(text):
        return text.translate(_FULL_TO_HALF_PAREN), "主观"
    return None


def classify_question_type(
    header: str,
    plan: QuestionTypePlan | None = None,
    objective_count: int | None = None,
) -> tuple[str, str] | None:
    """判定题型：题型配置优先；其次客观题数（题号大于该数为主观题）；最后按题号格式。

    配置模式（mode=config）下未覆盖题号返回题型 ""，由解析流程校验报错。
    """
    parsed = classify_question_header(header)
    if not parsed:
        return None
    qid, _ = parsed
    lead = re.match(r"\d+", qid)
    base = int(lead.group()) if lead else 0
    if plan is not None:
        qtype = plan.type_for(base)
        if qtype:
            return qid, qtype
        if plan.mode == "config":
            return qid, ""  # 未覆盖，由流程校验
    if objective_count is not None:
        return qid, "主观" if base > objective_count else "客观"
    return parsed


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
