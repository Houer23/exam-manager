"""CLI 配置修改操作的单元测试。"""

import pytest

from grade_analyzer.config_ops import validate_config_value


def test_number_value_valid():
    assert validate_config_value("pass_ratio", "0.65") == "0.65"


def test_number_out_of_range_raises():
    with pytest.raises(ValueError):
        validate_config_value("pass_ratio", "1.5")


def test_number_negative_raises():
    with pytest.raises(ValueError):
        validate_config_value("default_full_score", "-5")


def test_unknown_key_raises():
    with pytest.raises(ValueError):
        validate_config_value("nope", "1")


def test_text_value_ok():
    assert validate_config_value("current_semester", "高一第一学期") == "高一第一学期"
