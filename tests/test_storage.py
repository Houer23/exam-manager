"""规范表存储与复用的单元测试。"""

import os
import time
from pathlib import Path

import pandas as pd
import pytest

from grade_analyzer.config import ExamConfig
from grade_analyzer.storage import (
    is_parsed_fresh,
    parsed_exam_dir,
    read_score_summary,
    write_parsed_tables,
)


def _exam(folder: str | None = None, file: str = "地理原始数据.xlsx") -> ExamConfig:
    return ExamConfig(
        name="高一下联考",
        semester="高一第二学期",
        folder=folder,
        file=file,
    )


def test_parsed_exam_dir():
    p = parsed_exam_dir("data/parsed", _exam())
    assert p == Path("data/parsed") / "高一第二学期" / "高一下联考"


def test_parsed_exam_dir_requires_name():
    with pytest.raises(ValueError, match="名称"):
        parsed_exam_dir("data/parsed", ExamConfig(semester="高一第二学期"))


def test_write_read_roundtrip(tmp_path):
    exam = _exam()
    score = pd.DataFrame(
        {
            "exam_name": ["高一下联考"],
            "student_id": ["250902010001"],
            "total_score": [70.0],
        }
    )
    questions = pd.DataFrame(
        {
            "exam_name": ["高一下联考"],
            "student_id": ["250902010001"],
            "question_id": ["1"],
            "question_type": ["客观"],
            "score": [2.0],
            "full_score": [None],
        }
    )
    write_parsed_tables(str(tmp_path), exam, score, questions)
    loaded = read_score_summary(str(tmp_path), exam)
    assert loaded["total_score"].iloc[0] == 70.0
    assert (
        tmp_path / "高一第二学期" / "高一下联考" / "score_summary.csv"
    ).is_file()
    assert (
        tmp_path / "高一第二学期" / "高一下联考" / "question_detail.csv"
    ).is_file()


def test_is_parsed_fresh_follows_raw_mtime(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw = raw_dir / "地理原始数据.xlsx"
    pd.DataFrame([[1, 2]]).to_excel(raw, index=False, header=False)
    exam = _exam(folder=str(raw_dir))

    assert is_parsed_fresh(str(tmp_path), exam) is False  # 尚无规范表

    write_parsed_tables(
        str(tmp_path), exam, pd.DataFrame({"a": [1]}), pd.DataFrame({"a": [1]})
    )
    time.sleep(0.05)
    assert is_parsed_fresh(str(tmp_path), exam) is True

    future = time.time() + 10
    os.utime(raw, (future, future))
    assert is_parsed_fresh(str(tmp_path), exam) is False  # 原始文件变新


def test_is_parsed_fresh_config_change_invalidates(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw = raw_dir / "地理原始数据.xlsx"
    raw.write_text("x", encoding="utf-8")
    exam_yaml = tmp_path / "考试.yaml"
    exam_yaml.write_text("name: 高一下联考\nobjective_question_count: 20\n", encoding="utf-8")
    exam = _exam(folder=str(raw_dir))
    exam.config_path = str(exam_yaml)

    write_parsed_tables(
        str(tmp_path), exam, pd.DataFrame({"a": [1]}), pd.DataFrame({"a": [1]})
    )
    assert is_parsed_fresh(str(tmp_path), exam) is True  # 规范表比配置新

    # 仅改 mtime 不改内容：签名相同，缓存仍有效
    later = time.time() + 10
    os.utime(exam_yaml, (later, later))
    assert is_parsed_fresh(str(tmp_path), exam) is True
    # 修改配置内容（客观题数变化）-> 签名变化 -> 缓存失效
    exam_yaml.write_text(
        "name: 高一下联考\nobjective_question_count: 21\n", encoding="utf-8"
    )
    assert is_parsed_fresh(str(tmp_path), exam) is False


def test_is_parsed_fresh_meta_config_invalidates(tmp_path):
    """学科配置（teacher 列来源）变化应使解析缓存失效。"""
    from grade_analyzer.config import AnalysisConfig

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw = raw_dir / "外语数据.xlsx"
    raw.write_text("x", encoding="utf-8")
    exam = ExamConfig(
        name="高一下外语限时练",
        semester="高一第二学期",
        subject="外语",
        folder=str(raw_dir),
        file="外语数据.xlsx",
    )
    subjects_dir = tmp_path / "subjects"
    classes_dir = tmp_path / "classes"
    subjects_dir.mkdir()
    classes_dir.mkdir()
    cfg = AnalysisConfig(
        subjects_dir=str(subjects_dir), classes_dir=str(classes_dir)
    )
    subject_file = subjects_dir / "高一第二学期_外语.yaml"
    subject_file.write_text(
        "subject: 外语\n"
        "teacher_count: 1\n"
        "teacher_names:\n"
        "  A: Q\n"
        "class_teachers:\n"
        "  高一01班: A\n",
        encoding="utf-8",
    )
    score = pd.DataFrame(
        {"exam_name": ["高一下外语限时练"], "student_id": ["1"], "total_score": [70.0]}
    )
    questions = pd.DataFrame(
        columns=["exam_name", "student_id", "question_id", "question_type", "score", "full_score"]
    )
    write_parsed_tables(str(tmp_path), exam, score, questions, config=cfg)
    time.sleep(0.05)
    assert is_parsed_fresh(str(tmp_path), exam, config=cfg) is True
    # 修改学科配置（增加教师）→ 缓存失效
    subject_file.write_text(
        "subject: 外语\n"
        "teacher_count: 2\n"
        "teacher_names:\n"
        "  A: Q\n"
        "  B: W\n"
        "class_teachers:\n"
        "  高一01班: A\n"
        "  高一02班: B\n",
        encoding="utf-8",
    )
    assert is_parsed_fresh(str(tmp_path), exam, config=cfg) is False
