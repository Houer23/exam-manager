"""模板生成与扫描脚本（项目新部署 / 模板缺失 / 模板变更）。

用法：
    python template_tools.py generate --type all          # 重新生成模板（config 缺失时一并生成）
    python template_tools.py scan --mode existence        # 存在性检验：缺失才生成
    python template_tools.py scan --mode diff             # 变更检验：模板与内置默认值不同则重新生成
    python template_tools.py scan --mode existence --prompt  # 只提示，不自动生成

内置默认值即本文件中的 DEFAULT_* 常量，修改它们即可修改生成模板的默认值。
"""

from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_CHARTS = r"""# 统计图（组合图）配置 —— 默认值全部显式列出，可按需修改

# 输出与启用
enabled: true              # run 时是否生成统计图
format: png                # png / svg / pdf
dpi: 150
figure_width: 10           # 画布宽度
row_height: 1              # 每班行高（画布高度 = max(min_figure_height, 行数×row_height)）
min_figure_height: 6       # 画布最小高度

# 分组与内容
group_by: [层次, 教师]     # 生成哪些分组图
sort_metric: median        # 折线降序字段：median / mean / q1 / q3
show_violin: true          # 是否画半提琴图
show_lines: true           # 是否画指标折线

# 坐标轴
axis:
  range_mode: auto         # auto=满分×0.1~满分 / fixed=10-100 / custom=自定义
  fixed_min: 10
  fixed_max: 100
  custom_min: 25
  custom_max: 95
  tick_step: 10            # 刻度步长（整十）
  y_label: class_name      # class_name=班级规范名 / row_number=数字行号
  xlim_factor: 1           # 横轴右侧扩展系数（为指标标注预留空间，>=1）

# 字体
font:
  family: [微软雅黑, SimHei, Arial Unicode MS]
  title_size: 16
  label_size: 12
  tick_size: 10
  annot_size: 10
  legend_size: 7

# 配色
colors:
  palette: seaborn         # seaborn / tab10
  metrics:
    Q1: {color: tab:blue, marker: s}
    中位数: {color: tab:orange, marker: o}
    平均数: {color: tab:red, marker: D}
    Q3: {color: tab:green, marker: ^}

# 半提琴图
violin:
  split: true
  fill: false
  inner: quart             # quart / box / point / stick / null
  linewidth: 1.0
  width: 0.58              # 半提琴图宽度（占单位行高比例，为标注留空间）

# 标注
annotations:
  ave_std_x_offset: 1      # ave/std 放在 横轴下限 + 偏移
  ave_width: 5             # ave/std 数字宽度（右对齐空格补齐）
  text_y_offset: 0.45      # M/Q1/Q3 相对行中心的 y 偏移
  ave_std_format: .2f      # ave/std 小数格式
  point_format: .1f        # M/Q1/Q3 小数格式

# 组间分隔线
separator:
  show: true
  color: gray
  style: --
  linewidth: 0.6
"""

DEFAULT_GLOBAL = r"""# 成绩单分析配置（全局）
# 修改本文件后重新运行程序即可生效。

# 统计口径
analysis:
  pass_ratio: 0.6
  excellent_ratio: 0.85
  absent_strategy: exclude
  score_bands: [0.9, 0.8, 0.7, 0.6]

# 统计图配置目录：config/charts/config.yaml（默认值已全部显式列出）
charts_dir: config/charts
# 成绩单输出目录（按学期归类）与成绩单配置目录
results_dir: data/output/results
results_config_dir: config/results

# 常见科目词表（用于文件名识别）
subjects: [语文, 数学, 外语, 物理, 化学, 生物, 政治, 历史, 地理, 技术]

# 科目别名：识别到别名时映射为规范科目名
subject_aliases:
  外语: [英语, 俄语, 日语]
  技术: [信息技术, 通用技术]

# 科目默认值
subject_defaults:
  语文: {full_score: 150}
  数学: {full_score: 150}
  外语: {full_score: 150}
  地理: {full_score: 100, objective_full_score: 50, subjective_full_score: 50}

default_full_score: 100
default_grade: 高一
default_school: 示例中学

# 规范表存储与复用
parsed_dir: data/parsed
parsed_format: csv
current_semester: 高一第二学期
# 当前场次序号列表（整数，逗号分隔）：1-n 按日期升序编号，0=第一场，负数=倒数第 |k| 场；
# 留空 = 处理全部考试；命令行 --exam（名称或序号列表）优先级最高
current_exam: ""

# 目录配置
# 默认成绩单输入目录：考试配置 folder 留空时使用
input_dir: data/input
exams_dir: config/exams
classes_dir: config/classes
subjects_dir: config/subjects
roster_dir: data/roster

# 输出配置
output:
  dir: data/output
  excel_name: 成绩分析汇总.xlsx
"""

DEFAULT_RESULTS = r"""# 成绩单（results）配置 —— 默认值全部显式列出

# ==================== 个人成绩单 ====================
personal:
  scope:
    mode: teacher              # teacher=按教师分组 / all=全部班级 / custom=自定义班级列表
    teachers: [A]           # mode=teacher 时填写教师列表
    classes: []            # mode=custom 时填写班级列表
  sort_by_score_desc: true # 学生顺序：true=总分降序；false=班级->班次升序
  single_sheet: true       # true=单 sheet 全部学生；false=每班一个 sheet
  big_score_prefix: ""     # 大题总分列前缀（show_big_questions=true 时生效）
  big_score_suffix: ""     # 大题总分列后缀
  merged_prefix: "M"        # 合并模式大题列前缀（question_display=merged 时生效）
  merged_suffix: ""        # 合并模式大题列后缀
  bold_total_score: true   # 是否加粗总分值
  layout:
    blank_rows_between: 1  # 成绩条之间空行数
    row_height: 20
    column_widths:
      first10: [10, 10, 10, 5, 6, 8, 6, 6, 6, 6]  # 前10固定列：班级/姓名/考试/班次/校次/总分/客观/主观/单选/多选
      split_question_cols: 5               # 单独小题列宽
      merged_question_cols: 8              # 合并小题列宽
      big_question_cols: 4                 # 大题列宽
    font:
      header: {name: 宋体, size: 11, bold: false}
      data: {name: 宋体, size: 11, bold: false}
    alignment:
      header: center_center
      data_vertical: center
      center_cols: [班级, 姓名, 考试, 班次, 校次, 总分]
      right_from: 客观分
    borders:
      enabled: true
      style: thin               # 正常框线
      header_top_style: medium  # 每个成绩条表头上框线（略粗）
  header_footer:
    enabled: false         # 个人成绩单默认无页眉页脚
    header: {left: "", center: "", right: ""}
    footer: {left: "", center: "", right: ""}
    fonts:
      header_left: {name: 微软雅黑, size: 20, bold: true}
      header_center: {name: 方正小标宋_GBK, size: 20, bold: false}
      header_right: {name: "", size: 14, bold: false}
      footer_left: {name: "", size: 12, bold: false}
  print:
    orientation: portrait
    paper_size: A4
    margin: {top: 0.5, bottom: 0.5, left: 0.5, right: 0.5}
    fit_to_width: false
    rows_per_page: 41          # 每页行数；留空 = 按纸张/边距/行高自动计算

# ==================== 班级成绩汇总 ====================
class_summary:
  group_by_teacher: true   # 按教师分文件
  per_class_sheet: true    # 每班一个 sheet
  all_classes_summary: true  # 额外生成包含所有班级的汇总表
  header:
    date_format: "%Y年%m月%d日"
    left_font: {name: 微软雅黑, size: 20, bold: true}
    center_font: {name: 方正小标宋_GBK, size: 20, bold: false}
    right_font: {name: "", size: 14, bold: false}
  footer:
    left_font_size: 12
    half_width: true       # 页脚是否用半角标点
  fonts:
    header: {name: 方正小标宋_GBK, size: 12, bold: false}
    data: {name: 宋体, size: 11, bold: false}
    average: {name: 宋体, size: 11, bold: false}
  row_height:
    header: 20
  column_widths:
    first7: [6, 8, 6, 7, 7, 5, 5]
    question_cols: 6
    last2: [5, 5]
  alignment:
    header: center_center
    total_col: center
    average_label: center
  borders:
    enabled: true
    style: thin
    remove_single_multi: true   # 单选|多选之间去竖线
    remove_same_big: true       # 同一大题小题之间去竖线
  data_bar:
    enabled: true
    color: 67C487
  average_rows:
    labels: [平均(全班), 平均(前半), 平均(后半)]
    half_ceil: true
    decimals: 2
"""

DEFAULT_EXAMS = r"""# 考试条目模板：复制本文件并改名（如 2026-期中-地理.yaml）
# 文件名不要以 _ 开头（下划线开头的文件会被忽略，如本模板）。
# 所有字段均可省略，省略表示"自动识别或使用默认值"。
# 规范考试名称 = 学期简写 + 科目 + 考试名（已含相关内容时不重复添加）。

subject: ""                  # 必填：科目（check 校验，留空不通过）
semester: ""                 # 可省略：放入"高一第一学期"这类子文件夹时默认取文件夹名；显式声明优先
date: ""                     # 考试日期（YYYY-MM-DD）；留空 = 程序运行当日
folder: ""                   # 可省略：留空 = 取全局配置 input_dir 默认成绩单位置
file: xxx.xlsx               # 必填：成绩文件名
name: ""                     # 可省略：留空 = 从文件名自动提取；提取失败时 check 不通过
short_name: ""               # 可省略：留空 = 使用考试全称作为简称
question_display: split      # 个人成绩单小题呈现：split=每小题一列；merged=按大题合并为 值|值|值
show_big_questions: false    # 是否额外显示主观大题汇总分列

format: ""                   # 留空 = 按表头特征自动识别（weekly/joint）
type: 默认                   # 考试类型：默认/学考/模考…（联合分析筛选用）
importance: ""               # 留空 = 由 format 推导（joint=联考，weekly=平时）
full_score: 100              # 留空 = 使用科目默认值
objective_full_score: 50     # 留空 = 使用科目默认值；无默认时必填
subjective_full_score: 50    # 留空 = 使用科目默认值；无默认时必填
default_grade: ""            # 留空 = 使用全局默认年级（高一）
sheet: ""                    # 留空 = 自动选择 sheet
filter_by_selection: true    # 名单核对是否按七选三过滤：true=按选课过滤；false=按全部班级核对
"""

DEFAULT_CLASSES = r"""# 班级配置模板：复制并改名为 <学期>.yaml（如 高一第二学期.yaml）
# 只配置默认学校的班级，键为班级名（高XDD班），不写学校。
# level: 学情层次，只能 A 或 B；course: 选科组合，自由文本。

高一10班: {level: A, course: 物化地}
高一11班: {level: B, course: 政史地}
"""

DEFAULT_SUBJECTS = r"""# 学科配置模板：复制并改名为 <学期>_<学科>.yaml（如 高一第二学期_地理.yaml）
# teacher_count: 本学科教师数量，必须与 teacher_names 数量一致
# teacher_names: 从 A 开始连续大写字母代号 -> 教师名称
# class_teachers: 默认学校的班级 -> 字母代号；使用时转换为教师名称

subject: 地理
teacher_count: 2
teacher_names:
  A: 张老师
  B: 李老师
class_teachers:
  高一10班: A
  高一11班: B
"""

TEMPLATE_TYPES = {
    "global": {
        "template": None,
        "config": "config/config.yaml",
        "default": DEFAULT_GLOBAL,
        "diff": False,  # 全局配置为实际配置，diff 模式不覆盖
    },
    "charts": {
        "template": "config/charts/_template.yaml",
        "config": "config/charts/config.yaml",
        "default": DEFAULT_CHARTS,
        "diff": True,
    },
    "results": {
        "template": "config/results/_template.yaml",
        "config": "config/results/config.yaml",
        "default": DEFAULT_RESULTS,
        "diff": True,
    },
    "exams": {
        "template": "config/exams/_template.yaml",
        "config": None,
        "default": DEFAULT_EXAMS,
        "diff": True,
    },
    "classes": {
        "template": "config/classes/_template.yaml",
        "config": None,
        "default": DEFAULT_CLASSES,
        "diff": True,
    },
    "subjects": {
        "template": "config/subjects/_template.yaml",
        "config": None,
        "default": DEFAULT_SUBJECTS,
        "diff": True,
    },
}


def generate_type(name: str, root: Path = Path(".")) -> list[str]:
    """在对应位置重新生成模板；相关配置文件缺失时一并生成，返回写入路径。"""
    if name not in TEMPLATE_TYPES:
        raise ValueError(f"未知模板类型: {name}（可选 {list(TEMPLATE_TYPES)}）")
    info = TEMPLATE_TYPES[name]
    written: list[str] = []
    if info["config"]:
        cfg = root / info["config"]
        if not cfg.is_file():
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text(info["default"], encoding="utf-8")
            written.append(str(cfg))
    if info["template"]:
        tpl = root / info["template"]
        tpl.parent.mkdir(parents=True, exist_ok=True)
        tpl.write_text(info["default"], encoding="utf-8")
        written.append(str(tpl))
    return written


def scan(
    mode: str = "existence",
    prompt: bool = False,
    types: list[str] | None = None,
    root: Path = Path("."),
) -> dict[str, str]:
    """扫描模板：existence=缺失才生成；diff=与内置默认值不同则重新生成。

    prompt=True 时只提示不自动生成。返回 {类型: ok/generated/prompted}。
    """
    names = types or list(TEMPLATE_TYPES)
    results: dict[str, str] = {}
    for name in names:
        info = TEMPLATE_TYPES[name]
        tpl = root / info["template"] if info["template"] else None
        cfg = root / info["config"] if info["config"] else None
        missing = (tpl is not None and not tpl.is_file()) or (
            cfg is not None and not cfg.is_file()
        )
        diff = False
        if tpl is not None and tpl.is_file():
            diff = tpl.read_text(encoding="utf-8") != info["default"]
        need = missing or (mode == "diff" and info.get("diff", True) and diff)
        if not need:
            results[name] = "ok"
            continue
        if prompt:
            print(
                f"[提示] {name}: 模板缺失或与内置默认值不同，"
                f"请手动运行 generate --type {name}"
            )
            results[name] = "prompted"
        else:
            written = generate_type(name, root)
            print(f"[生成] {name}: {', '.join(written)}")
            results[name] = "generated"
    return results


def _parse_types(value: str | None) -> list[str] | None:
    if not value:
        return None
    types = [t.strip() for t in value.split(",")]
    unknown = [t for t in types if t not in TEMPLATE_TYPES]
    if unknown:
        raise ValueError(f"未知模板类型: {unknown}（可选 {list(TEMPLATE_TYPES)}）")
    return types


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="template-tools", description="模板生成与扫描")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="重新生成模板（相关配置文件缺失时一并生成）")
    gen.add_argument(
        "--type",
        default="all",
        help="模板类型：all/global/charts/results/exams/classes/subjects",
    )

    sc = sub.add_parser("scan", help="扫描模板并视情况生成")
    sc.add_argument("--mode", default="existence", choices=["existence", "diff"])
    sc.add_argument("--type", default=None, help="模板类型（逗号分隔，缺省全部）")
    sc.add_argument("--prompt", action="store_true", help="只提示，不自动生成")

    args = parser.parse_args(argv)
    if args.command == "generate":
        names = (
            list(TEMPLATE_TYPES)
            if args.type == "all"
            else _parse_types(args.type)
        )
        for name in names:
            print(f"[生成] {name}: {', '.join(generate_type(name))}")
    else:
        scan(mode=args.mode, prompt=args.prompt, types=_parse_types(args.type))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
