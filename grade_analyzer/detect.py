"""文件名识别工具。

- 从文件名提取考试名称（weekly 用："--" 与 "】" 之间）；
- 从文件名推测科目（匹配 subjects 与 subject_aliases 词表）。
"""

from __future__ import annotations

import re
from pathlib import Path

from .config import normalize_exam_name


def extract_exam_name_from_filename(path: str) -> str | None:
    """从文件名 "--" 与 "】" 之间提取考试名称，未命中返回 None。"""
    filename = Path(path).name
    match = re.search(r"--(.*?)】", filename)
    if not match:
        return None
    return match.group(1).strip()


def detect_subject_from_filename(
    path: str,
    subjects: list[str],
    subject_aliases: dict[str, list[str]],
) -> str | None:
    """按词表匹配文件名，返回规范科目名（如 英语 -> 外语）。

    规范科目名与别名命中多个不同科目时返回 None，提示手动指定。
    """
    filename = Path(path).name
    hits: set[str] = set()
    for subject in subjects:
        if subject and subject in filename:
            hits.add(subject)
    for canonical, words in subject_aliases.items():
        for word in words:
            if word and word in filename:
                hits.add(canonical)
    if len(hits) == 1:
        return next(iter(hits))
    return None


def resolve_exam_name(
    exam,
    subjects: list[str] | None = None,
    subject_aliases: dict[str, list[str]] | None = None,
) -> str | None:
    """解析考试名称：配置显式 > 文件名提取 + 学期/科目规范化。

    科目优先用配置值；为空时可用 subjects/aliases 从文件名推测，
    仅用于拼接规范名（不修改 exam.subject，check 仍校验 subject 必填）。
    """
    if exam.name:
        return exam.name
    extracted = extract_exam_name_from_filename(exam.full_path)
    if not extracted:
        return None
    subject = exam.subject
    if not subject and subjects:
        subject = detect_subject_from_filename(
            exam.full_path, subjects, subject_aliases
        )
    return normalize_exam_name(
        extracted, exam.semester, subject, subject_aliases
    )
