"""图表配置加载与校验的单元测试。"""

import pytest

from grade_analyzer.chart_config import load_charts_config


def _write(tmp_path, content):
    p = tmp_path / "config.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_defaults_when_file_missing(tmp_path):
    cfg = load_charts_config(str(tmp_path))
    assert cfg.enabled is True
    assert cfg.format == "png"
    assert cfg.sort_metric == "median"
    assert cfg.group_by == ["层次", "教师"]
    assert cfg.axis.range_mode == "auto"
    assert cfg.violin.inner == "quart"
    assert cfg.colors.metrics["中位数"].marker == "o"


def test_load_override(tmp_path):
    _write(
        tmp_path,
        "enabled: false\n"
        "format: svg\n"
        "group_by: [层次]\n"
        "sort_metric: mean\n"
        "axis:\n"
        "  range_mode: fixed\n"
        "  fixed_min: 20\n"
        "  fixed_max: 120\n"
        "font:\n"
        "  title_size: 20\n"
        "colors:\n"
        "  metrics:\n"
        "    中位数: {color: red, marker: x}\n"
        "annotations:\n"
        "  point_format: .2f\n",
    )
    cfg = load_charts_config(str(tmp_path))
    assert cfg.enabled is False
    assert cfg.format == "svg"
    assert cfg.group_by == ["层次"]
    assert cfg.sort_metric == "mean"
    assert cfg.axis.range_mode == "fixed"
    assert cfg.axis.fixed_min == 20.0
    assert cfg.font.title_size == 20
    assert cfg.colors.metrics["中位数"].marker == "x"
    assert cfg.annotations.point_format == ".2f"


def test_invalid_sort_metric(tmp_path):
    _write(tmp_path, "sort_metric: max\n")
    with pytest.raises(ValueError, match="sort_metric"):
        load_charts_config(str(tmp_path))


def test_invalid_format(tmp_path):
    _write(tmp_path, "format: gif\n")
    with pytest.raises(ValueError, match="format"):
        load_charts_config(str(tmp_path))


def test_unknown_top_key(tmp_path):
    _write(tmp_path, "nope: 1\n")
    with pytest.raises(ValueError, match="未知配置键"):
        load_charts_config(str(tmp_path))


def test_invalid_group_by(tmp_path):
    _write(tmp_path, "group_by: [层次, 年级]\n")
    with pytest.raises(ValueError, match="group_by"):
        load_charts_config(str(tmp_path))


def test_invalid_axis_range_mode(tmp_path):
    _write(tmp_path, "axis:\n  range_mode: unknown\n")
    with pytest.raises(ValueError, match="range_mode"):
        load_charts_config(str(tmp_path))


def test_invalid_metric_key(tmp_path):
    _write(tmp_path, "colors:\n  metrics:\n    方差: {color: red}\n")
    with pytest.raises(ValueError, match="metrics"):
        load_charts_config(str(tmp_path))


def test_axis_xlim_factor_default_and_override(tmp_path):
    assert load_charts_config(str(tmp_path)).axis.xlim_factor == 1.1
    _write(tmp_path, "axis:\n  xlim_factor: 1.05\n")
    assert load_charts_config(str(tmp_path)).axis.xlim_factor == 1.05


def test_axis_xlim_factor_invalid(tmp_path):
    _write(tmp_path, "axis:\n  xlim_factor: 0.5\n")
    with pytest.raises(ValueError, match="xlim_factor"):
        load_charts_config(str(tmp_path))


def test_violin_width_default_and_override(tmp_path):
    assert load_charts_config(str(tmp_path)).violin.width == 0.8
    _write(tmp_path, "violin:\n  width: 0.5\n")
    assert load_charts_config(str(tmp_path)).violin.width == 0.5


def test_violin_width_invalid(tmp_path):
    _write(tmp_path, "violin:\n  width: 0\n")
    with pytest.raises(ValueError, match="violin.width"):
        load_charts_config(str(tmp_path))
