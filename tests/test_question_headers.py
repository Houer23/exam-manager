"""题号表头识别与归一化的单元测试。"""

from grade_analyzer.adapters.base import classify_question_header, classify_question_type


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


def test_classify_chinese_suffix():
    # 数字 + 汉字后缀（如平台导出的 23作文）按纯数字题号处理，默认归入主观题
    assert classify_question_header("23作文") == ("23", "主观")
    assert classify_question_header("21写作") == ("21", "主观")
    assert classify_question_type("23作文") == ("23", "主观")


def test_classify_unknown():
    assert classify_question_header("abc") is None
    assert classify_question_header("") is None


def test_classify_type_with_count():
    # 客观题数 25：题号 <=25 客观，>25 主观（含小题取大题号）
    assert classify_question_type("10", objective_count=25) == ("10", "客观")
    assert classify_question_type("25", objective_count=25) == ("25", "客观")
    assert classify_question_type("26", objective_count=25) == ("26", "主观")
    assert classify_question_type("26-1", objective_count=25) == ("26-1", "主观")


def test_classify_type_fallback_without_count():
    # 未配置客观题数：按题号格式回退（纯数字客观、带小题主观）
    assert classify_question_type("5") == ("5", "客观")
    assert classify_question_type("26(1)") == ("26-1", "主观")
