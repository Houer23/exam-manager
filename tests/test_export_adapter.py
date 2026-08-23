"""平台成绩导出（export）适配器测试。"""

from __future__ import annotations

import pandas as pd

from grade_analyzer.adapters.export import (
    ExportAdapter,
    _class_code_to_name,
    _parse_export_frame,
)
from grade_analyzer.adapters.registry import known_formats
from grade_analyzer.config import ExamConfig

_HEADER = [
    "学校", "学校代码", "考生号", "学籍号", "姓名", "任课教师", "班级",
    "总分", "客观分", "主观分", "标准分", "赋分", "级名次", "校名次",
    "选择题_1", "选择项_1", "选择题_2", "选择项_2", "选择题_3", "选择项_3",
    "第26（1）题", "第26（2）题", "第28(4)题",
    "大气垂直分层及其特征",
]


def _exam() -> ExamConfig:
    return ExamConfig(
        name="高一下地理期末联考",
        subject="地理",
        semester="高一第二学期",
        full_score=100.0,
        objective_full_score=50.0,
        subjective_full_score=50.0,
        objective_question_count=25,
    )


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _HEADER,
            [
                "遂昌中学", "332590701", "250907010709", "331123201006142412", "鲍帅",
                "韩慧", 2501.0, 87.0, 44.0, 43.0, 98.63, 0.0, 8.0, 1.0,
                2.0, "C", 0.0, "A", 2.0, "B",
                3.0, 6.0, 6.0, 2.0,
            ],
            [
                "遂昌中学", "332590701", "250907010227", "331123201001160822", "项晨奕",
                "王亚玲", 2516.0, 79.0, 44.0, 35.0, 93.29, 0.0, 190.0, 5.0,
                2.0, "C", 2.0, "A", 0.0, "B",
                3.0, 4.0, 4.0, 2.0,
            ],
        ]
    )


def test_class_code_to_name():
    assert _class_code_to_name(2501.0) == "高一01班"
    assert _class_code_to_name("2516") == "高一16班"
    assert _class_code_to_name("高一01班") == "高一01班"


def test_detect():
    assert ExportAdapter.detect(_frame()) is True
    other = pd.DataFrame([["自定义考号", "总分", "班级"], ["1", "2", "3"]])
    assert ExportAdapter.detect(other) is False


def test_registered():
    assert "export" in known_formats()


def test_parse_export_frame():
    exam = _exam()
    score, questions = _parse_export_frame(_frame(), exam)
    assert len(score) == 2
    assert score["class_name"].tolist() == ["高一01班", "高一16班"]
    assert score["class_raw"].tolist() == ["高一01班", "高一16班"]
    assert score["total_score"].tolist() == [87.0, 79.0]
    assert score["objective_score"].tolist() == [44.0, 44.0]
    assert score["subjective_score"].tolist() == [43.0, 35.0]
    assert score["school"].tolist() == ["遂昌中学", "遂昌中学"]
    # 选择项/知识点列不入小题明细
    assert len(questions) == 2 * 6  # 选择题1-3 + 26-1/26-2/28-4
    qids = questions["question_id"].tolist()
    assert qids == [
        q for q in ["1", "2", "3", "26-1", "26-2", "28-4"] for _ in range(2)
    ]
    types = questions["question_type"].tolist()
    assert types == [
        t for t in ["客观", "客观", "客观", "主观", "主观", "主观"] for _ in range(2)
    ]
    # 得分正确
    s1 = questions[questions["student_id"] == "250907010709"]
    assert s1.set_index("question_id")["score"].to_dict() == {
        "1": 2.0, "2": 0.0, "3": 2.0, "26-1": 3.0, "26-2": 6.0, "28-4": 6.0,
    }


def test_parse_invalid_rows_filtered():
    frame = _frame()
    frame.loc[len(frame)] = [
        "遂昌中学", "332590701", "bad-id", "x", "无效", "韩慧", 2501.0,
        10.0, 5.0, 5.0, 0.0, 0.0, 1.0, 1.0,
        2.0, "C", 2.0, "A", 2.0, "B", 0.0, 0.0, 0.0, 0.0,
    ]
    score, _questions = _parse_export_frame(frame, _exam())
    assert len(score) == 2  # 非 12 位考号行被过滤
