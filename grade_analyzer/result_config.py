"""成绩单（results）配置：班级成绩汇总 + 个人成绩单。

配置文件：config/results/config.yaml（默认值全部显式列出）；
缺失时使用代码内默认值。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_TOP_KEYS = {"personal", "class_summary"}
_SCOPE_KEYS = {"mode", "teachers", "classes"}
_PERSONAL_KEYS = {
    "scope", "sort_by_score_desc", "single_sheet",
    "big_score_prefix", "big_score_suffix", "merged_prefix", "merged_suffix",
    "bold_total_score", "layout", "header_footer", "print",
}
_LAYOUT_KEYS = {
    "blank_rows_between", "row_height", "column_widths", "font",
    "alignment", "borders",
}
_COL_WIDTHS_KEYS = {
    "first10", "split_question_cols", "merged_question_cols", "big_question_cols",
}
_FONT_KEYS = {"name", "size", "bold"}
_FONT_BLOCK_KEYS = {"header", "data"}
_ALIGN_KEYS = {"header", "data_vertical", "center_cols", "right_from"}
_PERSONAL_BORDER_KEYS = {"enabled", "style", "header_top_style"}
_HF_KEYS = {"enabled", "header", "footer", "fonts"}
_HF_SECTION_KEYS = {"left", "center", "right"}
_HF_FONTS_KEYS = {"header_left", "header_center", "header_right", "footer_left"}
_PRINT_KEYS = {"orientation", "paper_size", "margin", "fit_to_width"}
_MARGIN_KEYS = {"top", "bottom", "left", "right"}
_CS_KEYS = {
    "group_by_teacher", "per_class_sheet", "all_classes_summary",
    "header", "footer", "fonts", "row_height", "column_widths",
    "alignment", "borders", "data_bar", "average_rows",
}
_CS_HEADER_KEYS = {"date_format", "left_font", "center_font", "right_font"}
_CS_FOOTER_KEYS = {"left_font_size", "half_width"}
_CS_FONTS_KEYS = {"header", "data", "average"}
_CS_ROW_KEYS = {"header"}
_CS_COLW_KEYS = {"first7", "question_cols", "last2"}
_CS_ALIGN_KEYS = {"header", "total_col", "average_label"}
_CS_BORDERS_KEYS = {"enabled", "style", "remove_single_multi", "remove_same_big"}
_CS_DATABAR_KEYS = {"enabled", "color"}
_CS_AVG_KEYS = {"labels", "half_ceil", "decimals"}


@dataclass
class FontSpec:
    """字体规格。"""

    name: str = "Calibri"
    size: int = 11
    bold: bool = False


@dataclass
class ScopeConfig:
    """个人成绩单范围。"""

    mode: str = "all"  # teacher / all / custom
    teachers: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)


@dataclass
class PersonalLayoutConfig:
    """个人成绩单布局。"""

    blank_rows_between: int = 1
    row_height: float = 20.0
    column_widths: dict = field(
        default_factory=lambda: {
            "first10": [10, 10, 10, 5, 6, 8, 6, 6, 6, 6],
            "split_question_cols": 4,
            "merged_question_cols": 8,
            "big_question_cols": 4,
        }
    )
    font: dict = field(
        default_factory=lambda: {
            "header": FontSpec("宋体", 11, False),
            "data": FontSpec("宋体", 11, False),
        }
    )
    alignment: dict = field(
        default_factory=lambda: {
            "header": "center_center",
            "data_vertical": "center",
            "center_cols": ["班级", "姓名", "考试", "班次", "校次", "总分"],
            "right_from": "客观分",
        }
    )
    borders: dict = field(
        default_factory=lambda: {
            "enabled": True,
            "style": "thin",
            "header_top_style": "medium",
        }
    )


@dataclass
class HFSectionConfig:
    """页眉页脚某段（左/中/右）。"""

    left: str = ""
    center: str = ""
    right: str = ""


@dataclass
class HeaderFooterConfig:
    """个人成绩单页眉页脚（参考文件默认无）。"""

    enabled: bool = False
    header: HFSectionConfig = field(default_factory=HFSectionConfig)
    footer: HFSectionConfig = field(default_factory=HFSectionConfig)
    fonts: dict = field(
        default_factory=lambda: {
            "header_left": FontSpec("微软雅黑", 20, True),
            "header_center": FontSpec("方正小标宋_GBK", 20, False),
            "header_right": FontSpec("", 14, False),
            "footer_left": FontSpec("", 12, False),
        }
    )


@dataclass
class PrintConfig:
    """打印设置。"""

    orientation: str = "portrait"
    paper_size: str = "A4"
    margin: dict = field(
        default_factory=lambda: {"top": 0.5, "bottom": 0.5, "left": 0.5, "right": 0.5}
    )
    fit_to_width: bool = True


@dataclass
class PersonalConfig:
    """个人成绩单配置。"""

    scope: ScopeConfig = field(default_factory=ScopeConfig)
    sort_by_score_desc: bool = True
    single_sheet: bool = True
    big_score_prefix: str = ""  # 大题总分列前缀（show_big_questions=true 时生效）
    big_score_suffix: str = ""  # 大题总分列后缀
    merged_prefix: str = ""  # 合并模式大题列前缀（question_display=merged 时生效）
    merged_suffix: str = ""  # 合并模式大题列后缀
    bold_total_score: bool = True  # 是否加粗总分值
    layout: PersonalLayoutConfig = field(default_factory=PersonalLayoutConfig)
    header_footer: HeaderFooterConfig = field(default_factory=HeaderFooterConfig)
    print: PrintConfig = field(default_factory=PrintConfig)


@dataclass
class CSHeaderConfig:
    """班级汇总页眉。"""

    date_format: str = "%Y年%m月%d日"
    left_font: FontSpec = field(default_factory=lambda: FontSpec("微软雅黑", 20, True))
    center_font: FontSpec = field(
        default_factory=lambda: FontSpec("方正小标宋_GBK", 20, False)
    )
    right_font: FontSpec = field(default_factory=lambda: FontSpec("", 14, False))


@dataclass
class CSFooterConfig:
    """班级汇总页脚。"""

    left_font_size: int = 12
    half_width: bool = True


@dataclass
class CSFontsConfig:
    """班级汇总字体。"""

    header: FontSpec = field(default_factory=lambda: FontSpec("方正小标宋_GBK", 12, False))
    data: FontSpec = field(default_factory=lambda: FontSpec("宋体", 11, False))
    average: FontSpec = field(default_factory=lambda: FontSpec("宋体", 11, False))


@dataclass
class CSRowHeightConfig:
    """班级汇总行高。"""

    header: float = 20.0


@dataclass
class CSColumnWidthsConfig:
    """班级汇总列宽。"""

    first7: list = field(default_factory=lambda: [6, 8, 6, 7, 7, 5, 5])
    question_cols: int = 6
    last2: list = field(default_factory=lambda: [5, 5])


@dataclass
class CSAlignmentConfig:
    """班级汇总对齐。"""

    header: str = "center_center"
    total_col: str = "center"
    average_label: str = "center"


@dataclass
class CSBordersConfig:
    """班级汇总边框。"""

    enabled: bool = True
    style: str = "thin"
    remove_single_multi: bool = True
    remove_same_big: bool = True


@dataclass
class CSDataBarConfig:
    """班级汇总条件格式（数据条）。"""

    enabled: bool = True
    color: str = "67C487"


@dataclass
class CSAverageRowsConfig:
    """班级汇总平均行。"""

    labels: list = field(
        default_factory=lambda: ["平均(全班)", "平均(前半)", "平均(后半)"]
    )
    half_ceil: bool = True
    decimals: int = 2


@dataclass
class ClassSummaryConfig:
    """班级成绩汇总配置。"""

    group_by_teacher: bool = True
    per_class_sheet: bool = True
    all_classes_summary: bool = True
    header: CSHeaderConfig = field(default_factory=CSHeaderConfig)
    footer: CSFooterConfig = field(default_factory=CSFooterConfig)
    fonts: CSFontsConfig = field(default_factory=CSFontsConfig)
    row_height: CSRowHeightConfig = field(default_factory=CSRowHeightConfig)
    column_widths: CSColumnWidthsConfig = field(default_factory=CSColumnWidthsConfig)
    alignment: CSAlignmentConfig = field(default_factory=CSAlignmentConfig)
    borders: CSBordersConfig = field(default_factory=CSBordersConfig)
    data_bar: CSDataBarConfig = field(default_factory=CSDataBarConfig)
    average_rows: CSAverageRowsConfig = field(default_factory=CSAverageRowsConfig)


@dataclass
class ResultsConfig:
    """成绩单完整配置。"""

    personal: PersonalConfig = field(default_factory=PersonalConfig)
    class_summary: ClassSummaryConfig = field(default_factory=ClassSummaryConfig)


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


def _font(data: dict, base: FontSpec, where: str, path: Path) -> FontSpec:
    _check_unknown(data, _FONT_KEYS, where, path)
    name = str(data.get("name", base.name))
    size = _as_int(data.get("size", base.size), f"{where}.size", path, 1)
    bold = _as_bool(data.get("bold", base.bold), f"{where}.bold", path)
    return FontSpec(name=name, size=size, bold=bold)


def _sub(data: dict, key: str, keys: set, where: str, path: Path) -> dict:
    d = data.get(key) or {}
    if not isinstance(d, dict):
        raise ValueError(f"{path}: {where} 应为映射")
    _check_unknown(d, keys, where, path)
    return d


def load_results_config(results_dir: str = "config/results") -> ResultsConfig:
    """加载 config/results/config.yaml；缺失时使用默认值。"""
    path = Path(results_dir) / "config.yaml"
    if not path.is_file():
        return ResultsConfig()
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: 成绩单配置应为映射")
    _check_unknown(raw, _TOP_KEYS, "成绩单配置", path)

    cfg = ResultsConfig()

    # ---- 个人成绩单 ----
    p_raw = _sub(raw, "personal", _PERSONAL_KEYS, "personal", path)
    p = cfg.personal
    scope_raw = _sub(p_raw, "scope", _SCOPE_KEYS, "personal.scope", path)
    p.scope.mode = str(scope_raw.get("mode", p.scope.mode))
    if p.scope.mode not in {"teacher", "all", "custom"}:
        raise ValueError(f"{path}: personal.scope.mode 应为 teacher/all/custom")
    teachers = scope_raw.get("teachers", p.scope.teachers)
    classes = scope_raw.get("classes", p.scope.classes)
    if not isinstance(teachers, list) or not isinstance(classes, list):
        raise ValueError(f"{path}: personal.scope.teachers/classes 应为列表")
    p.scope.teachers = [str(t) for t in teachers]
    p.scope.classes = [str(c) for c in classes]
    p.sort_by_score_desc = _as_bool(
        p_raw.get("sort_by_score_desc", p.sort_by_score_desc),
        "personal.sort_by_score_desc", path,
    )
    p.single_sheet = _as_bool(
        p_raw.get("single_sheet", p.single_sheet), "personal.single_sheet", path
    )
    p.big_score_prefix = str(p_raw.get("big_score_prefix", p.big_score_prefix))
    p.big_score_suffix = str(p_raw.get("big_score_suffix", p.big_score_suffix))
    p.merged_prefix = str(p_raw.get("merged_prefix", p.merged_prefix))
    p.merged_suffix = str(p_raw.get("merged_suffix", p.merged_suffix))
    p.bold_total_score = _as_bool(
        p_raw.get("bold_total_score", p.bold_total_score),
        "personal.bold_total_score", path,
    )
    lay_raw = _sub(p_raw, "layout", _LAYOUT_KEYS, "personal.layout", path)
    lay = p.layout
    lay.blank_rows_between = _as_int(
        lay_raw.get("blank_rows_between", lay.blank_rows_between),
        "personal.layout.blank_rows_between", path, 0,
    )
    lay.row_height = _as_float(
        lay_raw.get("row_height", lay.row_height), "personal.layout.row_height", path, 1
    )
    cw_raw = _sub(
        lay_raw, "column_widths", _COL_WIDTHS_KEYS,
        "personal.layout.column_widths", path,
    )
    first10 = cw_raw.get("first10", lay.column_widths["first10"])
    if not isinstance(first10, list) or len(first10) != 10:
        raise ValueError(f"{path}: personal.layout.column_widths.first10 应为 10 个数值")
    lay.column_widths["first10"] = [float(x) for x in first10]
    for key in ("split_question_cols", "merged_question_cols", "big_question_cols"):
        lay.column_widths[key] = _as_float(
            cw_raw.get(key, lay.column_widths[key]),
            f"personal.layout.column_widths.{key}", path, 1,
        )
    font_raw = _sub(lay_raw, "font", _FONT_BLOCK_KEYS, "personal.layout.font", path)
    lay.font["header"] = _font(
        font_raw.get("header") or {}, lay.font["header"],
        "personal.layout.font.header", path,
    )
    lay.font["data"] = _font(
        font_raw.get("data") or {}, lay.font["data"],
        "personal.layout.font.data", path,
    )
    align_raw = _sub(
        lay_raw, "alignment", _ALIGN_KEYS, "personal.layout.alignment", path
    )
    lay.alignment["header"] = str(align_raw.get("header", lay.alignment["header"]))
    lay.alignment["data_vertical"] = str(
        align_raw.get("data_vertical", lay.alignment["data_vertical"])
    )
    center_cols = align_raw.get("center_cols", lay.alignment["center_cols"])
    if not isinstance(center_cols, list) or not center_cols:
        raise ValueError(f"{path}: personal.layout.alignment.center_cols 应为非空列表")
    lay.alignment["center_cols"] = [str(c) for c in center_cols]
    lay.alignment["right_from"] = str(
        align_raw.get("right_from", lay.alignment["right_from"])
    )

    pb_raw = _sub(
        lay_raw, "borders", _PERSONAL_BORDER_KEYS, "personal.layout.borders", path
    )
    lay.borders["enabled"] = _as_bool(
        pb_raw.get("enabled", lay.borders["enabled"]),
        "personal.layout.borders.enabled", path,
    )
    lay.borders["style"] = str(pb_raw.get("style", lay.borders["style"]))
    lay.borders["header_top_style"] = str(
        pb_raw.get("header_top_style", lay.borders["header_top_style"])
    )

    hf_raw = _sub(p_raw, "header_footer", _HF_KEYS, "personal.header_footer", path)
    hf = p.header_footer
    hf.enabled = _as_bool(hf_raw.get("enabled", hf.enabled), "personal.header_footer.enabled", path)
    hf.header = HFSectionConfig(
        left=str(hf_raw.get("header", {}).get("left", hf.header.left)),
        center=str(hf_raw.get("header", {}).get("center", hf.header.center)),
        right=str(hf_raw.get("header", {}).get("right", hf.header.right)),
    )
    hf.footer = HFSectionConfig(
        left=str(hf_raw.get("footer", {}).get("left", hf.footer.left)),
        center=str(hf_raw.get("footer", {}).get("center", hf.footer.center)),
        right=str(hf_raw.get("footer", {}).get("right", hf.footer.right)),
    )
    hff_raw = _sub(
        hf_raw, "fonts", _HF_FONTS_KEYS, "personal.header_footer.fonts", path
    )
    for key, base in (
        ("header_left", hf.fonts["header_left"]),
        ("header_center", hf.fonts["header_center"]),
        ("header_right", hf.fonts["header_right"]),
        ("footer_left", hf.fonts["footer_left"]),
    ):
        hf.fonts[key] = _font(
            hff_raw.get(key) or {}, base, f"personal.header_footer.fonts.{key}", path
        )

    pr_raw = _sub(p_raw, "print", _PRINT_KEYS, "personal.print", path)
    pr = p.print
    pr.orientation = str(pr_raw.get("orientation", pr.orientation))
    if pr.orientation not in {"portrait", "landscape"}:
        raise ValueError(f"{path}: personal.print.orientation 应为 portrait/landscape")
    pr.paper_size = str(pr_raw.get("paper_size", pr.paper_size))
    margin_raw = _sub(
        pr_raw, "margin", _MARGIN_KEYS, "personal.print.margin", path
    )
    for k in ("top", "bottom", "left", "right"):
        pr.margin[k] = _as_float(
            margin_raw.get(k, pr.margin[k]), f"personal.print.margin.{k}", path, 0
        )
    pr.fit_to_width = _as_bool(
        pr_raw.get("fit_to_width", pr.fit_to_width), "personal.print.fit_to_width", path
    )

    # ---- 班级成绩汇总 ----
    cs_raw = _sub(raw, "class_summary", _CS_KEYS, "class_summary", path)
    cs = cfg.class_summary
    cs.group_by_teacher = _as_bool(
        cs_raw.get("group_by_teacher", cs.group_by_teacher),
        "class_summary.group_by_teacher", path,
    )
    cs.per_class_sheet = _as_bool(
        cs_raw.get("per_class_sheet", cs.per_class_sheet),
        "class_summary.per_class_sheet", path,
    )
    cs.all_classes_summary = _as_bool(
        cs_raw.get("all_classes_summary", cs.all_classes_summary),
        "class_summary.all_classes_summary", path,
    )

    h_raw = _sub(cs_raw, "header", _CS_HEADER_KEYS, "class_summary.header", path)
    cs.header.date_format = str(h_raw.get("date_format", cs.header.date_format))
    cs.header.left_font = _font(
        h_raw.get("left_font") or {}, cs.header.left_font,
        "class_summary.header.left_font", path,
    )
    cs.header.center_font = _font(
        h_raw.get("center_font") or {}, cs.header.center_font,
        "class_summary.header.center_font", path,
    )
    cs.header.right_font = _font(
        h_raw.get("right_font") or {}, cs.header.right_font,
        "class_summary.header.right_font", path,
    )

    fo_raw = _sub(cs_raw, "footer", _CS_FOOTER_KEYS, "class_summary.footer", path)
    cs.footer.left_font_size = _as_int(
        fo_raw.get("left_font_size", cs.footer.left_font_size),
        "class_summary.footer.left_font_size", path, 1,
    )
    cs.footer.half_width = _as_bool(
        fo_raw.get("half_width", cs.footer.half_width),
        "class_summary.footer.half_width", path,
    )

    fonts_raw = _sub(cs_raw, "fonts", _CS_FONTS_KEYS, "class_summary.fonts", path)
    cs.fonts.header = _font(
        fonts_raw.get("header") or {}, cs.fonts.header,
        "class_summary.fonts.header", path,
    )
    cs.fonts.data = _font(
        fonts_raw.get("data") or {}, cs.fonts.data,
        "class_summary.fonts.data", path,
    )
    cs.fonts.average = _font(
        fonts_raw.get("average") or {}, cs.fonts.average,
        "class_summary.fonts.average", path,
    )

    row_raw = _sub(cs_raw, "row_height", _CS_ROW_KEYS, "class_summary.row_height", path)
    cs.row_height.header = _as_float(
        row_raw.get("header", cs.row_height.header),
        "class_summary.row_height.header", path, 1,
    )

    cw_raw = _sub(
        cs_raw, "column_widths", _CS_COLW_KEYS,
        "class_summary.column_widths", path,
    )
    first7 = cw_raw.get("first7", cs.column_widths.first7)
    last2 = cw_raw.get("last2", cs.column_widths.last2)
    if not isinstance(first7, list) or len(first7) != 7:
        raise ValueError(f"{path}: class_summary.column_widths.first7 应为 7 个数值")
    if not isinstance(last2, list) or len(last2) != 2:
        raise ValueError(f"{path}: class_summary.column_widths.last2 应为 2 个数值")
    cs.column_widths.first7 = [float(x) for x in first7]
    cs.column_widths.question_cols = _as_float(
        cw_raw.get("question_cols", cs.column_widths.question_cols),
        "class_summary.column_widths.question_cols", path, 1,
    )
    cs.column_widths.last2 = [float(x) for x in last2]

    al_raw = _sub(cs_raw, "alignment", _CS_ALIGN_KEYS, "class_summary.alignment", path)
    cs.alignment.header = str(al_raw.get("header", cs.alignment.header))
    cs.alignment.total_col = str(al_raw.get("total_col", cs.alignment.total_col))
    cs.alignment.average_label = str(
        al_raw.get("average_label", cs.alignment.average_label)
    )

    b_raw = _sub(cs_raw, "borders", _CS_BORDERS_KEYS, "class_summary.borders", path)
    cs.borders.enabled = _as_bool(
        b_raw.get("enabled", cs.borders.enabled), "class_summary.borders.enabled", path
    )
    cs.borders.style = str(b_raw.get("style", cs.borders.style))
    cs.borders.remove_single_multi = _as_bool(
        b_raw.get("remove_single_multi", cs.borders.remove_single_multi),
        "class_summary.borders.remove_single_multi", path,
    )
    cs.borders.remove_same_big = _as_bool(
        b_raw.get("remove_same_big", cs.borders.remove_same_big),
        "class_summary.borders.remove_same_big", path,
    )

    db_raw = _sub(cs_raw, "data_bar", _CS_DATABAR_KEYS, "class_summary.data_bar", path)
    cs.data_bar.enabled = _as_bool(
        db_raw.get("enabled", cs.data_bar.enabled),
        "class_summary.data_bar.enabled", path,
    )
    cs.data_bar.color = str(db_raw.get("color", cs.data_bar.color))

    av_raw = _sub(
        cs_raw, "average_rows", _CS_AVG_KEYS, "class_summary.average_rows", path
    )
    labels = av_raw.get("labels", cs.average_rows.labels)
    if not isinstance(labels, list) or len(labels) != 3:
        raise ValueError(f"{path}: class_summary.average_rows.labels 应为 3 个文本")
    cs.average_rows.labels = [str(x) for x in labels]
    cs.average_rows.half_ceil = _as_bool(
        av_raw.get("half_ceil", cs.average_rows.half_ceil),
        "class_summary.average_rows.half_ceil", path,
    )
    cs.average_rows.decimals = _as_int(
        av_raw.get("decimals", cs.average_rows.decimals),
        "class_summary.average_rows.decimals", path, 0,
    )
    return cfg
