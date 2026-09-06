"""图表配置加载与校验。

配置文件：config/charts/config.yaml（默认值全部显式列出）；
缺失时使用代码内默认值。考试级覆盖接口预留，暂不实现。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

METRIC_NAMES = ["Q1", "中位数", "平均数", "Q3"]
_GROUP_OPTIONS = {"层次", "教师"}
_SORT_OPTIONS = {"median", "mean", "q1", "q3"}
_FORMAT_OPTIONS = {"png", "svg", "pdf"}
_RANGE_OPTIONS = {"auto", "fixed", "custom"}
_YLABEL_OPTIONS = {"class_name", "row_number"}
_PALETTE_OPTIONS = {"seaborn", "tab10"}
_INNER_OPTIONS = {None, "quart", "box", "point", "stick"}

_TOP_KEYS = {
    "enabled", "format", "dpi", "figure_width", "row_height",
    "min_figure_height", "group_by", "sort_metric", "show_violin",
    "show_lines", "axis", "font", "colors", "violin",
    "annotations", "separator",
    "output_dir", "folder_semester", "folder_exam", "folder_type",
    "type_folder_name",
}
_AXIS_KEYS = {
    "range_mode", "fixed_min", "fixed_max", "custom_min",
    "custom_max", "tick_step", "y_label", "xlim_factor",
}
_FONT_KEYS = {
    "family", "title_size", "label_size", "tick_size",
    "annot_size", "legend_size",
}
_COLORS_KEYS = {"palette", "metrics"}
_METRIC_KEYS = {"color", "marker"}
_VIOLIN_KEYS = {"split", "fill", "inner", "linewidth", "width"}
_ANNOT_KEYS = {
    "ave_std_x_offset", "ave_width", "text_y_offset",
    "ave_std_format", "point_format",
}
_SEP_KEYS = {"show", "color", "style", "linewidth"}


@dataclass
class AxisConfig:
    """坐标轴配置。"""

    range_mode: str = "auto"  # auto=满分×0.1~满分 / fixed / custom
    fixed_min: float = 10.0
    fixed_max: float = 100.0
    custom_min: float = 25.0
    custom_max: float = 95.0
    tick_step: int = 10
    y_label: str = "class_name"  # class_name / row_number
    xlim_factor: float = 1.1  # 横轴右侧扩展系数（为指标标注预留空间）


@dataclass
class FontConfig:
    """字体配置。"""

    family: list[str] = field(
        default_factory=lambda: ["微软雅黑", "SimHei", "Arial Unicode MS"]
    )
    title_size: int = 16
    label_size: int = 12
    tick_size: int = 10
    annot_size: int = 10
    legend_size: int = 7


@dataclass
class MetricsStyle:
    """单个指标的样式（颜色 + 点符号）。"""

    color: str = "tab:blue"
    marker: str = "s"


@dataclass
class ColorsConfig:
    """配色配置。"""

    palette: str = "seaborn"  # seaborn / tab10
    metrics: dict[str, MetricsStyle] = field(
        default_factory=lambda: {
            "Q1": MetricsStyle(color="tab:blue", marker="s"),
            "中位数": MetricsStyle(color="tab:orange", marker="o"),
            "平均数": MetricsStyle(color="tab:green", marker="D"),
            "Q3": MetricsStyle(color="tab:red", marker="^"),
        }
    )


@dataclass
class ViolinConfig:
    """半提琴图配置。"""

    split: bool = True
    fill: bool = False
    inner: str | None = "quart"
    linewidth: float = 1.0
    width: float = 0.8  # 半提琴图宽度（占单位行高比例，用于为标注留出空间）


@dataclass
class AnnotationsConfig:
    """标注配置。"""

    ave_std_x_offset: float = 1.0
    ave_width: int = 5
    text_y_offset: float = 0.58
    ave_std_format: str = ".2f"
    point_format: str = ".1f"


@dataclass
class SeparatorConfig:
    """组间分隔线配置。"""

    show: bool = True
    color: str = "gray"
    style: str = "--"
    linewidth: float = 0.6


@dataclass
class ChartsConfig:
    """统计图（组合图）完整配置。"""

    enabled: bool = True
    format: str = "png"
    dpi: int = 150
    # 输出位置：留空 = 全局 output_dir 下的 charts（保持现状）；
    # 指定后作为统计图输出根目录
    output_dir: str = ""
    # 目录层级开关（外→内）：学期 -> 考试名 -> “统计图”文件夹
    folder_semester: bool = True
    folder_exam: bool = False
    folder_type: bool = False
    type_folder_name: str = "统计图"
    figure_width: float = 14.0
    row_height: float = 0.55
    min_figure_height: float = 6.0
    group_by: list[str] = field(default_factory=lambda: ["层次", "教师"])
    sort_metric: str = "median"
    show_violin: bool = True
    show_lines: bool = True
    axis: AxisConfig = field(default_factory=AxisConfig)
    font: FontConfig = field(default_factory=FontConfig)
    colors: ColorsConfig = field(default_factory=ColorsConfig)
    violin: ViolinConfig = field(default_factory=ViolinConfig)
    annotations: AnnotationsConfig = field(default_factory=AnnotationsConfig)
    separator: SeparatorConfig = field(default_factory=SeparatorConfig)


def _check_unknown(data: dict, allowed: set, where: str, path: Path) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"{path}: {where} 下未知配置键 {sorted(unknown)}")


def _as_bool(value: object, name: str, path: Path) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in ("", "false", "0", "no", "否")
    return bool(value)


def _as_int(value: object, name: str, path: Path, minimum: int) -> int:
    try:
        num = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{path}: {name} 应为整数")
    if num < minimum:
        raise ValueError(f"{path}: {name} 应不小于 {minimum}")
    return num


def _as_float(value: object, name: str, path: Path, minimum: float) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{path}: {name} 应为数值")
    if num < minimum:
        raise ValueError(f"{path}: {name} 应不小于 {minimum}")
    return num


def load_charts_config(charts_dir: str = "config/charts") -> ChartsConfig:
    """加载 config/charts/config.yaml；缺失时使用默认值。"""
    path = Path(charts_dir) / "config.yaml"
    if not path.is_file():
        return ChartsConfig()
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: 图表配置应为映射")
    _check_unknown(raw, _TOP_KEYS, "图表配置", path)

    cfg = ChartsConfig()
    cfg.enabled = _as_bool(raw.get("enabled", cfg.enabled), "enabled", path)
    cfg.format = str(raw.get("format", cfg.format))
    if cfg.format not in _FORMAT_OPTIONS:
        raise ValueError(f"{path}: format 应为 {sorted(_FORMAT_OPTIONS)}")
    cfg.output_dir = str(raw.get("output_dir", cfg.output_dir)).strip()
    cfg.folder_semester = _as_bool(
        raw.get("folder_semester", cfg.folder_semester),
        "folder_semester",
        path,
    )
    cfg.folder_exam = _as_bool(
        raw.get("folder_exam", cfg.folder_exam), "folder_exam", path
    )
    cfg.folder_type = _as_bool(
        raw.get("folder_type", cfg.folder_type), "folder_type", path
    )
    cfg.type_folder_name = str(
        raw.get("type_folder_name", cfg.type_folder_name)
    ).strip()
    if not cfg.type_folder_name:
        raise ValueError(f"{path}: type_folder_name 不能为空")
    if any(c in cfg.type_folder_name for c in ("/", "\\")):
        raise ValueError(f"{path}: type_folder_name 不能包含路径分隔符")
    cfg.dpi = _as_int(raw.get("dpi", cfg.dpi), "dpi", path, 1)
    cfg.figure_width = _as_float(
        raw.get("figure_width", cfg.figure_width), "figure_width", path, 1.0
    )
    cfg.row_height = _as_float(
        raw.get("row_height", cfg.row_height), "row_height", path, 0.1
    )
    cfg.min_figure_height = _as_float(
        raw.get("min_figure_height", cfg.min_figure_height),
        "min_figure_height",
        path,
        1.0,
    )

    group_by = raw.get("group_by", cfg.group_by)
    if not isinstance(group_by, list) or not group_by:
        raise ValueError(f"{path}: group_by 应为非空列表")
    cfg.group_by = [str(g) for g in group_by]
    if not set(cfg.group_by) <= _GROUP_OPTIONS:
        raise ValueError(f"{path}: group_by 只能在 {sorted(_GROUP_OPTIONS)} 中")

    cfg.sort_metric = str(raw.get("sort_metric", cfg.sort_metric))
    if cfg.sort_metric not in _SORT_OPTIONS:
        raise ValueError(f"{path}: sort_metric 应为 {sorted(_SORT_OPTIONS)}")
    cfg.show_violin = _as_bool(
        raw.get("show_violin", cfg.show_violin), "show_violin", path
    )
    cfg.show_lines = _as_bool(
        raw.get("show_lines", cfg.show_lines), "show_lines", path
    )

    axis_raw = raw.get("axis") or {}
    if not isinstance(axis_raw, dict):
        raise ValueError(f"{path}: axis 应为映射")
    _check_unknown(axis_raw, _AXIS_KEYS, "axis", path)
    a = cfg.axis
    a.range_mode = str(axis_raw.get("range_mode", a.range_mode))
    if a.range_mode not in _RANGE_OPTIONS:
        raise ValueError(f"{path}: axis.range_mode 应为 {sorted(_RANGE_OPTIONS)}")
    a.fixed_min = _as_float(axis_raw.get("fixed_min", a.fixed_min), "axis.fixed_min", path, 0)
    a.fixed_max = _as_float(axis_raw.get("fixed_max", a.fixed_max), "axis.fixed_max", path, 1)
    a.custom_min = _as_float(axis_raw.get("custom_min", a.custom_min), "axis.custom_min", path, 0)
    a.custom_max = _as_float(axis_raw.get("custom_max", a.custom_max), "axis.custom_max", path, 1)
    a.tick_step = _as_int(axis_raw.get("tick_step", a.tick_step), "axis.tick_step", path, 1)
    a.y_label = str(axis_raw.get("y_label", a.y_label))
    if a.y_label not in _YLABEL_OPTIONS:
        raise ValueError(f"{path}: axis.y_label 应为 {sorted(_YLABEL_OPTIONS)}")
    a.xlim_factor = _as_float(
        axis_raw.get("xlim_factor", a.xlim_factor), "axis.xlim_factor", path, 1.0
    )

    font_raw = raw.get("font") or {}
    if not isinstance(font_raw, dict):
        raise ValueError(f"{path}: font 应为映射")
    _check_unknown(font_raw, _FONT_KEYS, "font", path)
    f = cfg.font
    family = font_raw.get("family", f.family)
    if not isinstance(family, list) or not family:
        raise ValueError(f"{path}: font.family 应为非空列表")
    f.family = [str(x) for x in family]
    f.title_size = _as_int(font_raw.get("title_size", f.title_size), "font.title_size", path, 1)
    f.label_size = _as_int(font_raw.get("label_size", f.label_size), "font.label_size", path, 1)
    f.tick_size = _as_int(font_raw.get("tick_size", f.tick_size), "font.tick_size", path, 1)
    f.annot_size = _as_int(font_raw.get("annot_size", f.annot_size), "font.annot_size", path, 1)
    f.legend_size = _as_int(font_raw.get("legend_size", f.legend_size), "font.legend_size", path, 1)

    colors_raw = raw.get("colors") or {}
    if not isinstance(colors_raw, dict):
        raise ValueError(f"{path}: colors 应为映射")
    _check_unknown(colors_raw, _COLORS_KEYS, "colors", path)
    c = cfg.colors
    c.palette = str(colors_raw.get("palette", c.palette))
    if c.palette not in _PALETTE_OPTIONS:
        raise ValueError(f"{path}: colors.palette 应为 {sorted(_PALETTE_OPTIONS)}")
    metrics_raw = colors_raw.get("metrics") or {}
    if not isinstance(metrics_raw, dict):
        raise ValueError(f"{path}: colors.metrics 应为映射")
    _check_unknown(metrics_raw, set(METRIC_NAMES), "colors.metrics", path)
    for name, info in metrics_raw.items():
        if not isinstance(info, dict):
            raise ValueError(f"{path}: colors.metrics.{name} 应为映射")
        _check_unknown(info, _METRIC_KEYS, f"colors.metrics.{name}", path)
        base = c.metrics[name]
        c.metrics[name] = MetricsStyle(
            color=str(info.get("color", base.color)),
            marker=str(info.get("marker", base.marker)),
        )

    violin_raw = raw.get("violin") or {}
    if not isinstance(violin_raw, dict):
        raise ValueError(f"{path}: violin 应为映射")
    _check_unknown(violin_raw, _VIOLIN_KEYS, "violin", path)
    v = cfg.violin
    v.split = _as_bool(violin_raw.get("split", v.split), "violin.split", path)
    v.fill = _as_bool(violin_raw.get("fill", v.fill), "violin.fill", path)
    v.width = _as_float(
        violin_raw.get("width", v.width), "violin.width", path, 0.1
    )
    inner = violin_raw.get("inner", v.inner)
    if isinstance(inner, str) and inner.strip().lower() in ("none", ""):
        inner = None
    if inner not in _INNER_OPTIONS:
        raise ValueError(f"{path}: violin.inner 应为 {sorted(_INNER_OPTIONS)}")
    v.inner = inner
    v.linewidth = _as_float(
        violin_raw.get("linewidth", v.linewidth), "violin.linewidth", path, 0.1
    )

    annot_raw = raw.get("annotations") or {}
    if not isinstance(annot_raw, dict):
        raise ValueError(f"{path}: annotations 应为映射")
    _check_unknown(annot_raw, _ANNOT_KEYS, "annotations", path)
    an = cfg.annotations
    an.ave_std_x_offset = _as_float(
        annot_raw.get("ave_std_x_offset", an.ave_std_x_offset),
        "annotations.ave_std_x_offset",
        path,
        0,
    )
    an.ave_width = _as_int(
        annot_raw.get("ave_width", an.ave_width), "annotations.ave_width", path, 1
    )
    an.text_y_offset = _as_float(
        annot_raw.get("text_y_offset", an.text_y_offset),
        "annotations.text_y_offset",
        path,
        0,
    )
    an.ave_std_format = str(annot_raw.get("ave_std_format", an.ave_std_format))
    an.point_format = str(annot_raw.get("point_format", an.point_format))

    sep_raw = raw.get("separator") or {}
    if not isinstance(sep_raw, dict):
        raise ValueError(f"{path}: separator 应为映射")
    _check_unknown(sep_raw, _SEP_KEYS, "separator", path)
    s = cfg.separator
    s.show = _as_bool(sep_raw.get("show", s.show), "separator.show", path)
    s.color = str(sep_raw.get("color", s.color))
    s.style = str(sep_raw.get("style", s.style))
    s.linewidth = _as_float(
        sep_raw.get("linewidth", s.linewidth), "separator.linewidth", path, 0.1
    )
    return cfg
