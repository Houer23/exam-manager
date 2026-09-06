"""题型配置（question_types）解析与方案测试。"""

from __future__ import annotations

import pytest

from grade_analyzer.question_types import (
    parse_question_types,
    parse_question_types_text,
    resolve_question_types,
)


def test_parse_text_full_width_and_spaces():
    r = parse_question_types_text(
        "客观题，20；单选，1-10；多选，11-20；主观题，21-25"
    )
    assert r == {
        "客观题": 20,
        "单选": "1-10",
        "多选": "11-20",
        "主观题": "21-25",
    }


def test_parse_text_half_width_and_extra_spaces():
    r = parse_question_types_text(
        " 客观题 , 20 ; 单选, 1 - 10 ; 多选, 11-20; 主观题,21-25 "
    )
    assert r["客观题"] == 20
    assert r["单选"] == "1-10"


def test_parse_text_empty():
    assert parse_question_types_text("") is None
    assert parse_question_types_text("   ") is None
    assert parse_question_types_text(None) is None


def test_parse_text_invalid_missing_comma():
    with pytest.raises(ValueError, match="题型项格式"):
        parse_question_types_text("客观题20")


def test_parse_text_trailing_comma_is_question_number():
    r = parse_question_types_text("作文题，26,；客观题，1-25")
    assert r == {"作文题": "26,", "客观题": "1-25"}


def test_parse_count_first_row_then_list():
    r = parse_question_types({"客观题": 20, "主观题": "21-25"})
    assert r == {"客观": list(range(1, 21)), "主观": list(range(21, 26))}


def test_parse_all_count_sequential():
    r = parse_question_types({"听力": 5, "阅读": 10, "作文题": 3})
    assert r == {
        "听力": [1, 2, 3, 4, 5],
        "阅读": list(range(6, 16)),
        "作文题": [16, 17, 18],
    }


def test_parse_mixed_leading_counts_then_list():
    r = parse_question_types({"听力": 5, "阅读": 10, "作文题": "16,18,20"})
    assert r["听力"] == [1, 2, 3, 4, 5]
    assert r["阅读"] == list(range(6, 16))
    assert r["作文题"] == [16, 18, 20]


def test_parse_count_after_list_rejected():
    with pytest.raises(ValueError, match="列表式后不允许出现数量式"):
        parse_question_types({"客观题": "1-20", "主观题": 5})


def test_parse_text_count_after_list_rejected():
    with pytest.raises(ValueError, match="列表式后不允许出现数量式"):
        parse_question_types_text("听力，1-5；阅读，10")


def test_parse_text_leading_counts_ok():
    r = parse_question_types_text("听力，5；阅读，10；作文题，16,18,20")
    assert r == {"听力": 5, "阅读": 10, "作文题": "16,18,20"}


def test_parse_question_list_trailing_comma():
    assert parse_question_types({"作文题": "26,"}) == {"作文题": [26]}


def test_parse_column_name_tokens():
    r = parse_question_types(
        {"客观题": 55, "主观题": "语法填空56-65,应用文，续写"}
    )
    assert r["客观"] == list(range(1, 56))
    assert r["主观"] == ["语法填空56-65", "应用文", "续写"]


def test_parse_forced_column_marker():
    # 纯 "56-65" 会按范围解析；加 @ 前缀后强制作为得分列列名
    assert parse_question_types({"主观题": "56-65"}) == {
        "主观": list(range(56, 66))
    }
    assert parse_question_types({"主观题": "@56-65"}) == {
        "主观": ["56-65"]
    }


def test_full_width_comma_normalized_before_split():
    r = parse_question_types(
        {"主观题": "应用文，续写,语法填空56-65"}
    )
    assert r["主观"] == ["应用文", "续写", "语法填空56-65"]


def test_plan_keeps_column_top_level():
    plan = resolve_question_types(
        parse_question_types(
            {"客观题": 55, "主观题": "语法填空56-65,应用文，续写"}
        ),
        binary_split=False,
        objective_count=None,
    )
    assert plan is not None
    assert plan.columns == {
        "主观": ["语法填空56-65", "应用文", "续写"]
    }
    for token in plan.column_names():
        assert plan.top_of_column(token) == "主观"


def test_column_token_in_parent_and_subtype():
    plan = resolve_question_types(
        parse_question_types(
            {
                "客观题": 11,
                "主观题": "填空题12-14,15-19",
                "单选": "1-8",
                "多选": "9-11",
                "填空": "填空题12-14",
            }
        ),
        binary_split=True,
        objective_count=11,
    )
    assert plan is not None
    assert plan.parent["填空"] == "主观"
    assert plan.type_for_column("填空题12-14") == "填空"
    assert plan.top_of_column("填空题12-14") == "主观"


def test_binary_mode_subtypes():
    plan = resolve_question_types(
        parse_question_types(
            {"客观题": 20, "单选": "1-10", "多选": "11-20", "主观题": "21-25"}
        ),
        binary_split=True,
        objective_count=20,
    )
    assert plan is not None
    assert plan.mode == "binary"
    assert plan.top_level == ["客观", "主观"]
    assert plan.parent == {"单选": "客观", "多选": "客观"}
    assert plan.type_for(5) == "单选"
    assert plan.type_for(15) == "多选"
    assert plan.type_for(22) == "主观"
    assert plan.top_of(5) == "客观"
    assert plan.top_of(22) == "主观"


def test_config_mode_with_arbitrary_types():
    plan = resolve_question_types(
        parse_question_types({"听力": "1-5", "阅读": "6-15", "作文题": "16,"}),
        binary_split=True,
        objective_count=None,
    )
    assert plan is not None
    assert plan.mode == "config"
    assert plan.top_level == ["听力", "阅读", "作文题"]
    assert plan.type_for(3) == "听力"
    assert plan.type_for(16) == "作文题"
    assert plan.type_for(9) == "阅读"


def test_nested_subtype_resolves_deepest():
    plan = resolve_question_types(
        parse_question_types(
            {"客观题": "1-20", "单选": "1-10", "多选": "11-20"}
        ),
        binary_split=True,
        objective_count=20,
    )
    assert plan is not None
    assert plan.type_for(8) == "单选"
    assert plan.type_for(15) == "多选"


def test_partial_overlap_rejected():
    with pytest.raises(ValueError, match="部分重叠"):
        resolve_question_types(
            parse_question_types({"客观题": "1-20", "单选": "10-25"}),
            binary_split=True,
            objective_count=20,
        )


def test_binary_subtype_crossing_rejected():
    with pytest.raises(ValueError, match="跨越客观/主观"):
        resolve_question_types(
            parse_question_types({"单选": "15-25"}),
            binary_split=True,
            objective_count=20,
        )


def test_add_exam_writes_question_types(tmp_path):
    from grade_analyzer.config import load_config
    from grade_analyzer.config_ops import add_exam

    exams_dir = tmp_path / "exams"
    (exams_dir / "高一第二学期").mkdir(parents=True)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "subjects: [语文, 数学, 外语, 物理, 化学, 生物, 政治, 历史, 地理, 技术]\n"
        f"current_semester: 高一第二学期\n"
        f"exams_dir: '{exams_dir}'\n",
        encoding="utf-8",
    )
    add_exam(
        config_path=str(cfg),
        folder="data/input",
        file="英语测试.xlsx",
        name="英语听力测试",
        subject="外语",
        semester="高一第二学期",
        date="2026-06-01",
        fmt="weekly",
        question_types="听力，5；阅读，6-15；作文题，16,",
    )
    loaded = load_config(str(cfg))
    exam = [e for e in loaded.exams if e.subject == "外语"][0]
    assert exam.question_types == {
        "听力": [1, 2, 3, 4, 5],
        "阅读": list(range(6, 16)),
        "作文题": [16],
    }
