"""规范表存储与复用。

规范表按学期落盘：<parsed_dir>/<学期>/<考试名称>/score_summary.<fmt>
复用策略：规范表存在且原始文件未变（mtime）时直接复用；
原始文件变更或 force_reparse 时重新解析。
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import ExamConfig
from .io_utils import read_parsed_table, write_parsed_table

DELETED_MARKER = ".deleted"
CONFIG_SIG = ".config_sig"


def parsed_exam_dir(parsed_dir: str, exam: ExamConfig) -> Path:
    """返回某场考试的规范表目录：<parsed_dir>/<学期>/<考试名称>/。"""
    if not exam.name:
        raise ValueError("考试名称未解析，无法确定规范表目录")
    if not exam.semester:
        raise ValueError("semester 缺失，无法确定规范表目录")
    return Path(parsed_dir) / exam.semester / exam.name


def is_parsed_fresh(
    parsed_dir: str, exam: ExamConfig, fmt: str = "csv"
) -> bool:
    """规范表两张表均存在且不比原始文件/考试条目配置旧（按 mtime）则视为可复用。"""
    raw_path = Path(exam.full_path)
    if not raw_path.is_file():
        return False
    exam_dir = parsed_exam_dir(parsed_dir, exam)
    files = [
        exam_dir / f"score_summary.{fmt}",
        exam_dir / f"question_detail.{fmt}",
    ]
    if any(not f.is_file() for f in files):
        return False
    raw_mtime = raw_path.stat().st_mtime
    if not all(f.stat().st_mtime >= raw_mtime for f in files):
        return False
    # 考试条目配置变更（如客观题数）也会使缓存失效
    if exam.config_path:
        cfg_path = Path(exam.config_path)
        if cfg_path.is_file():
            sig_path = exam_dir / CONFIG_SIG
            if sig_path.is_file():
                current = hashlib.sha256(cfg_path.read_bytes()).hexdigest()
                if sig_path.read_text(encoding="utf-8").strip() != current:
                    return False
            else:
                # 旧缓存无签名：回退到配置 mtime 比较
                cfg_mtime = cfg_path.stat().st_mtime
                if not all(f.stat().st_mtime >= cfg_mtime for f in files):
                    return False
    return True


def read_score_summary(
    parsed_dir: str, exam: ExamConfig, fmt: str = "csv"
) -> pd.DataFrame:
    """读取某场考试的科目总分表。"""
    path = parsed_exam_dir(parsed_dir, exam) / f"score_summary.{fmt}"
    if not path.is_file():
        raise FileNotFoundError(f"规范表不存在: {path}")
    return read_parsed_table(str(path), fmt)


def read_question_detail(
    parsed_dir: str, exam: ExamConfig, fmt: str = "csv"
) -> pd.DataFrame:
    """读取某场考试的小题明细表。"""
    path = parsed_exam_dir(parsed_dir, exam) / f"question_detail.{fmt}"
    if not path.is_file():
        raise FileNotFoundError(f"规范表不存在: {path}")
    return read_parsed_table(str(path), fmt)


def write_parsed_tables(
    parsed_dir: str,
    exam: ExamConfig,
    score: pd.DataFrame,
    questions: pd.DataFrame,
    fmt: str = "csv",
) -> None:
    """写入规范表（科目总分表 + 小题明细表）。"""
    exam_dir = parsed_exam_dir(parsed_dir, exam)
    exam_dir.mkdir(parents=True, exist_ok=True)
    write_parsed_table(score, str(exam_dir / f"score_summary.{fmt}"), fmt)
    write_parsed_table(questions, str(exam_dir / f"question_detail.{fmt}"), fmt)
    # 记录考试条目配置签名：配置内容变化时缓存失效
    if exam.config_path:
        cfg_path = Path(exam.config_path)
        if cfg_path.is_file():
            sig = hashlib.sha256(cfg_path.read_bytes()).hexdigest()
            (exam_dir / CONFIG_SIG).write_text(sig, encoding="utf-8")


def class_summary_path(parsed_dir: str, exam: ExamConfig) -> Path:
    """班级成绩汇总文件路径（保存在该场考试的规范表目录下）。

    具体要求待定；此处仅固定路径：<parsed_dir>/<学期>/<考试名称>/class_summary.csv。
    """
    return parsed_exam_dir(parsed_dir, exam) / "class_summary.csv"


def mark_exam_deleted(parsed_dir: str, exam: ExamConfig) -> None:
    """在规范表缓存目录写入删除标记（缓存文件本身保留）。"""
    exam_dir = parsed_exam_dir(parsed_dir, exam)
    if exam_dir.is_dir():
        (exam_dir / DELETED_MARKER).write_text(
            f"deleted: {datetime.now().isoformat(timespec='seconds')}\n"
            f"exam: {exam.name}\n",
            encoding="utf-8",
        )


def is_exam_deleted(parsed_dir: str, exam: ExamConfig) -> bool:
    """检查缓存目录是否存在删除标记。"""
    return (parsed_exam_dir(parsed_dir, exam) / DELETED_MARKER).is_file()
