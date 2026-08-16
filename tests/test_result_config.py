"""成绩单（results）配置的单元测试。"""

import pytest

from grade_analyzer.result_config import load_results_config


def _write(tmp_path, content):
    p = tmp_path / "config.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_defaults_when_missing(tmp_path):
    cfg = load_results_config(str(tmp_path))
    assert cfg.personal.scope.mode == "all"
    assert cfg.personal.sort_by_score_desc is True
    assert cfg.personal.big_score_prefix == ""
    assert cfg.personal.merged_suffix == ""
    assert cfg.personal.bold_total_score is True
    cw = cfg.personal.layout.column_widths
    assert cw["first10"] == [10, 10, 10, 5, 6, 8, 6, 6, 6, 6]
    assert cw["split_question_cols"] == 4
    assert cw["merged_question_cols"] == 8
    assert cw["big_question_cols"] == 4
    assert cfg.personal.layout.font["header"].name == "宋体"
    assert cfg.personal.layout.alignment["right_from"] == "客观分"
    assert cfg.personal.layout.borders["header_top_style"] == "medium"
    assert cfg.class_summary.group_by_teacher is True
    assert cfg.class_summary.data_bar.color == "67C487"


def test_load_override(tmp_path):
    _write(
        tmp_path,
        "personal:\n"
        "  scope:\n"
        "    mode: teacher\n"
        "    teachers: [柯]\n"
        "  sort_by_score_desc: false\n"
        "  big_score_prefix: S\n"
        "  merged_prefix: M\n"
        "  bold_total_score: false\n"
        "  layout:\n"
        "    column_widths:\n"
        "      first10: [9, 9, 9, 5, 6, 8, 6, 6, 6, 6]\n"
        "      split_question_cols: 5\n"
        "    font:\n"
        "      data: {name: 楷体, size: 12, bold: true}\n"
        "    alignment:\n"
        "      center_cols: [班级, 姓名]\n"
        "      right_from: 总分\n"
        "    borders:\n"
        "      enabled: false\n"
        "class_summary:\n"
        "  all_classes_summary: false\n"
        "  data_bar:\n"
        "    color: FF0000\n",
    )
    cfg = load_results_config(str(tmp_path))
    assert cfg.personal.scope.mode == "teacher"
    assert cfg.personal.scope.teachers == ["柯"]
    assert cfg.personal.sort_by_score_desc is False
    assert cfg.personal.big_score_prefix == "S"
    assert cfg.personal.merged_prefix == "M"
    assert cfg.personal.bold_total_score is False
    assert cfg.personal.layout.column_widths["first10"][0] == 9.0
    assert cfg.personal.layout.column_widths["split_question_cols"] == 5.0
    assert cfg.personal.layout.font["data"].name == "楷体"
    assert cfg.personal.layout.alignment["center_cols"] == ["班级", "姓名"]
    assert cfg.personal.layout.alignment["right_from"] == "总分"
    assert cfg.personal.layout.borders["enabled"] is False
    assert cfg.class_summary.all_classes_summary is False
    assert cfg.class_summary.data_bar.color == "FF0000"


def test_invalid_scope_mode(tmp_path):
    _write(tmp_path, "personal:\n  scope:\n    mode: unknown\n")
    with pytest.raises(ValueError, match="scope.mode"):
        load_results_config(str(tmp_path))


def test_invalid_alignment_center_cols(tmp_path):
    _write(
        tmp_path,
        "personal:\n  layout:\n    alignment:\n      center_cols: 班级\n",
    )
    with pytest.raises(ValueError, match="center_cols"):
        load_results_config(str(tmp_path))


def test_print_rows_per_page(tmp_path):
    _write(
        tmp_path,
        "personal:\n"
        "  print:\n"
        "    rows_per_page: 41\n",
    )
    cfg = load_results_config(str(tmp_path))
    assert cfg.personal.print.rows_per_page == 41.0


def test_print_rows_per_page_empty_is_none(tmp_path):
    _write(
        tmp_path,
        "personal:\n"
        "  print:\n"
        "    rows_per_page: ''\n",
    )
    cfg = load_results_config(str(tmp_path))
    assert cfg.personal.print.rows_per_page is None


def test_print_rows_per_page_invalid_raises(tmp_path):
    _write(
        tmp_path,
        "personal:\n"
        "  print:\n"
        "    rows_per_page: abc\n",
    )
    with pytest.raises(ValueError, match="rows_per_page"):
        load_results_config(str(tmp_path))
