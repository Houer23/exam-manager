"""题号表头识别与归一化的单元测试。"""

from grade_analyzer.adapters.base import classify_question_header


def test_classify_objective():
    assert classify_question_header("1") == ("1", "客观")
    assert classify_question_header("25") == ("25", "客观")


def test_classify_halfwidth_parentheses():
    assert classify_question_header("26(1)") == ("26-1", "主观")
    assert classify_question_header("27(4)") == ("27-4", "主观")


def test_classify_fullwidth_parentheses():
    assert classify_question_header("26（1）") == ("26-1", "主观")
    assert classify_question_header("27（2）") == ("27-2", "主观")


def test_classify_dash():
    assert classify_question_header("28-1") == ("28-1", "主观")


def test_classify_unknown():
    assert classify_question_header("abc") is None
    assert classify_question_header("") is None
