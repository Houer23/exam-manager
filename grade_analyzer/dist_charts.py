"""数据统计图（matplotlib 组合图，配置驱动）。

每张组合图 = 半提琴图（seaborn，透明、同组同色）+ 指标折线图
（Q1/中位数/平均数/Q3，组内连续、组间断开）。
配置见 config/charts/config.yaml（ChartsConfig）。
"""

from __future__ import annotations

import os
import re
import tempfile

# 提前设置缓存目录（避免沙箱无法写入用户主目录下的 .matplotlib）
os.environ.setdefault(
    "MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "mplconfig")
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .chart_config import METRIC_NAMES, ChartsConfig
from .config import ExamConfig, OutputConfig
from .consolidate import date_range_suffix
from .outputs import type_dir

_METRIC_COL = {
    "Q1": "Q1",
    "中位数": "中位数",
    "平均数": "平均分",
    "Q3": "Q3",
}
_SORT_COL = {"median": "中位数", "mean": "平均分", "q1": "Q1", "q3": "Q3"}


def compute_class_metrics(score_df: pd.DataFrame) -> pd.DataFrame:
    """按班级计算统计指标：人数/平均分/标准差/中位数/Q1/Q3。"""
    valid = score_df[score_df["total_score"].notna()]
    rows = []
    for class_name, g in valid.groupby("class_name"):
        scores = g["total_score"].to_numpy(dtype=float)
        rows.append(
            {
                "班级": class_name,
                "层次": g["class_level"].iloc[0],
                "教师": g["teacher"].iloc[0],
                "人数": len(scores),
                "平均分": scores.mean(),
                "标准差": scores.std(ddof=1),
                "中位数": float(np.median(scores)),
                "Q1": float(np.percentile(scores, 25)),
                "Q3": float(np.percentile(scores, 75)),
            }
        )
    return pd.DataFrame(rows)


def build_group_chart(
    exam: ExamConfig,
    score_df: pd.DataFrame,
    metrics: pd.DataFrame,
    group_col: str,
    charts_cfg: ChartsConfig,
    output: OutputConfig,
) -> str:
    """生成按某分组（层次/教师）的组合图，返回输出路径。"""
    plt.rcParams["font.sans-serif"] = list(charts_cfg.font.family)
    plt.rcParams["axes.unicode_minus"] = False

    axis = charts_cfg.axis
    if axis.range_mode == "fixed":
        xmin, xmax = axis.fixed_min, axis.fixed_max
    elif axis.range_mode == "custom":
        xmin, xmax = axis.custom_min, axis.custom_max
    else:
        full = exam.full_score or 100.0
        xmin, xmax = full * 0.1, full
    step = axis.tick_step
    start = int(np.ceil(xmin / step)) * step
    ticks = list(range(start, int(xmax) + 1, step))

    sort_col = _SORT_COL[charts_cfg.sort_metric]
    ordered: list[tuple[object, pd.DataFrame]] = []
    for group in _order_groups(metrics, group_col, sort_col):
        sub = metrics[metrics[group_col] == group].sort_values(
            sort_col, ascending=False
        )
        ordered.append((group, sub))

    positions: dict[str, int] = {}
    pos = 0
    for _, sub in ordered:
        for _, row in sub.iterrows():
            positions[row["班级"]] = pos
            pos += 1
    n = pos

    fig, ax = plt.subplots(
        figsize=(
            charts_cfg.figure_width,
            max(charts_cfg.min_figure_height, charts_cfg.row_height * n),
        )
    )
    valid = score_df[score_df["total_score"].notna()]

    group_colors: dict[object, object] = {}
    if charts_cfg.colors.palette == "tab10":
        palette = plt.cm.tab10.colors
    else:
        palette = sns.color_palette()

    if charts_cfg.show_violin:
        for gi, (group, sub) in enumerate(ordered):
            color = palette[gi % len(palette)]
            group_colors[group] = color
            tmp = valid[valid["class_name"].isin(sub["班级"])].copy()
            if tmp.empty:
                continue
            tmp["ypos"] = tmp["class_name"].map(positions)
            sns.violinplot(
                data=tmp,
                x="total_score",
                y="ypos",
                orient="h",
                split=charts_cfg.violin.split,
                fill=charts_cfg.violin.fill,
                inner=charts_cfg.violin.inner,
                color=color,
                ax=ax,
                linewidth=charts_cfg.violin.linewidth,
                width=charts_cfg.violin.width,
            )

    if charts_cfg.show_lines:
        for group, sub in ordered:
            for metric in METRIC_NAMES:
                style = charts_cfg.colors.metrics[metric]
                col = _METRIC_COL[metric]
                xs = [row[col] for _, row in sub.iterrows()]
                ys = [positions[row["班级"]] for _, row in sub.iterrows()]
                ax.plot(
                    xs,
                    ys,
                    color=style.color,
                    marker=style.marker,
                    linewidth=1.0,
                    markersize=4.0,
                        label=metric if group == ordered[0][0] else None,
                )

    # 统计标注：左端 ave/std 两行 + 点位旁 M/Q1/Q3
    annot = charts_cfg.annotations
    text_move = annot.text_y_offset
    for _, row in metrics.iterrows():
        cls = row["班级"]
        if cls not in positions:
            continue  # 该班级无当前分组维度（如未配置层次/教师）时不在图中
        y = positions[cls]
        color_text = group_colors.get(row[group_col], "black")
        ax.text(
            xmin + annot.ave_std_x_offset,
            y,
            f"ave:{row['平均分']:>{annot.ave_width}{annot.ave_std_format}}\n"
            f"std:{row['标准差']:>{annot.ave_width}{annot.ave_std_format}}",
            va="center",
            size=charts_cfg.font.annot_size,
            color=color_text,
        )
        ax.text(
            row["中位数"], y + text_move,
            f"M:{row['中位数']:{annot.point_format}}",
            ha="center", size=charts_cfg.font.annot_size, color=color_text,
        )
        ax.text(
            row["Q1"], y + text_move,
            f"Q1:{row['Q1']:{annot.point_format}}",
            ha="right", size=charts_cfg.font.annot_size, color=color_text,
        )
        ax.text(
            row["Q3"], y + text_move,
            f"Q3:{row['Q3']:{annot.point_format}}",
            ha="left", size=charts_cfg.font.annot_size, color=color_text,
        )

    if charts_cfg.separator.show:
        boundary = 0
        for _, sub in ordered[:-1]:
            boundary += len(sub)
            ax.axhline(
                y=boundary - 0.5,
                color=charts_cfg.separator.color,
                linestyle=charts_cfg.separator.style,
                linewidth=charts_cfg.separator.linewidth,
            )

    ax.set_xlim(xmin, xmax * charts_cfg.axis.xlim_factor)
    ax.set_xticks(ticks)
    ax.tick_params(axis="both", labelsize=charts_cfg.font.tick_size)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_yticks(list(positions.values()))
    if axis.y_label == "row_number":
        ax.set_yticklabels([str(i) for i in range(n)])
    else:
        ax.set_yticklabels(list(positions.keys()))
    ax.set_xlabel("成绩", size=charts_cfg.font.label_size)
    ax.set_ylabel("班级", size=charts_cfg.font.label_size)
    ax.set_title(
        f"{exam.name} 按{group_col}组合图（半提琴+指标）",
        size=charts_cfg.font.title_size,
    )
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(
            handles, labels, loc="lower right",
            fontsize=charts_cfg.font.legend_size,
        )

    out_dir = type_dir(output, "charts") / (exam.semester or "")
    out_dir.mkdir(parents=True, exist_ok=True)
    date_part = str(exam.date or "").replace("-", "")
    middle = f"{date_part}_" if date_part else ""
    path = out_dir / f"按{group_col}_{middle}{exam.name}.{charts_cfg.format}"
    fig.savefig(path, dpi=charts_cfg.dpi, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def _order_groups(
    metrics: pd.DataFrame, group_col: str, sort_col: str
) -> list[object]:
    """组间排序：按各组平均指标降序（指标与方向同组内排序）。"""
    groups = sorted(metrics[group_col].dropna().unique())
    return sorted(
        groups,
        key=lambda g: metrics[metrics[group_col] == g][sort_col].mean(),
        reverse=True,
    )


def _class_label(classes: list[str]) -> str:
    """班级标签：单班级用规范全称；多班级用 <年级><序号1>、<序号2>...班。"""
    if len(classes) == 1:
        return classes[0]
    grade = ""
    nums: list[str] = []
    for c in classes:
        m = re.match(r"^(.*?)(\d+)班$", c)
        if not m:
            return "+".join(classes)  # 无法解析则回退
        grade = grade or m.group(1)
        nums.append(m.group(2))
    return f"{grade}" + "、".join(nums) + "班"


def build_exam_series_chart(
    exams: list[ExamConfig],
    scores: list[pd.DataFrame],
    classes: list[str],
    charts_cfg: ChartsConfig,
    output: OutputConfig,
) -> str:
    """按 班级×考试 绘制组合图：纵轴为 班级×考试 组合，横轴为成绩。

    按班级分组（组内为考试，日期升序），每组合一个半提琴；
    指标折线跨考试连续、跨班级断开；绘图方式与原统计图相同。
    """
    plt.rcParams["font.sans-serif"] = list(charts_cfg.font.family)
    plt.rcParams["axes.unicode_minus"] = False

    axis = charts_cfg.axis
    if axis.range_mode == "fixed":
        xmin, xmax = axis.fixed_min, axis.fixed_max
    elif axis.range_mode == "custom":
        xmin, xmax = axis.custom_min, axis.custom_max
    else:
        full = exams[0].full_score or 100.0
        xmin, xmax = full * 0.1, full
    step = axis.tick_step
    start = int(np.ceil(xmin / step)) * step
    ticks = list(range(start, int(xmax) + 1, step))

    # 每个 班级×考试 组合的指标（按班级分组、组内考试日期升序）
    rows: list[dict] = []
    labels: list[str] = []
    valid_by_exam: list[pd.DataFrame] = []
    class_of_pos: list[str] = []
    group_boundaries: list[int] = []
    for class_name in classes:
        start = len(rows)
        for exam, score in zip(exams, scores):
            valid = score[
                (score["class_name"] == class_name)
                & score["total_score"].notna()
            ]
            if valid.empty:
                continue
            arr = valid["total_score"].to_numpy(dtype=float)
            rows.append(
                {
                    "人数": len(arr),
                    "平均分": arr.mean(),
                    "标准差": arr.std(ddof=1),
                    "中位数": float(np.median(arr)),
                    "Q1": float(np.percentile(arr, 25)),
                    "Q3": float(np.percentile(arr, 75)),
                }
            )
            labels.append(f"{class_name}\n{exam.effective_short_name}")
            valid_by_exam.append(valid)
            class_of_pos.append(class_name)
        if len(rows) > start:
            group_boundaries.append(len(rows))
    if not rows:
        return ""
    metrics = pd.DataFrame(rows)
    n = len(metrics)

    fig, ax = plt.subplots(
        figsize=(
            charts_cfg.figure_width,
            max(charts_cfg.min_figure_height, charts_cfg.row_height * n),
        )
    )

    if charts_cfg.colors.palette == "tab10":
        palette = plt.cm.tab10.colors
    else:
        palette = sns.color_palette()
    class_color = {
        c: palette[i % len(palette)] for i, c in enumerate(classes)
    }

    if charts_cfg.show_violin:
        for i, (valid, class_name) in enumerate(zip(valid_by_exam, class_of_pos)):
            tmp = valid.copy()
            tmp["ypos"] = i
            sns.violinplot(
                data=tmp,
                x="total_score",
                y="ypos",
                orient="h",
                split=charts_cfg.violin.split,
                fill=charts_cfg.violin.fill,
                inner=charts_cfg.violin.inner,
                color=class_color[class_name],
                ax=ax,
                linewidth=charts_cfg.violin.linewidth,
                width=charts_cfg.violin.width,
            )

    if charts_cfg.separator.show:
        for boundary in group_boundaries[:-1]:
            ax.axhline(
                y=boundary - 0.5,
                color=charts_cfg.separator.color,
                linestyle=charts_cfg.separator.style,
                linewidth=charts_cfg.separator.linewidth,
            )

    if charts_cfg.show_lines:
        for metric in METRIC_NAMES:
            style = charts_cfg.colors.metrics[metric]
            col = _METRIC_COL[metric]
            for class_name in classes:
                idx = [
                    i for i, c in enumerate(class_of_pos) if c == class_name
                ]
                if not idx:
                    continue
                ax.plot(
                    [metrics.loc[i, col] for i in idx],
                    idx,
                    color=style.color,
                    marker=style.marker,
                    linewidth=1.0,
                    markersize=4.0,
                    label=metric if class_name == classes[0] else None,
                )

    annot = charts_cfg.annotations
    text_move = annot.text_y_offset
    for i, row in metrics.iterrows():
        ax.text(
            xmin + annot.ave_std_x_offset,
            i,
            f"ave:{row['平均分']:>{annot.ave_width}{annot.ave_std_format}}\n"
            f"std:{row['标准差']:>{annot.ave_width}{annot.ave_std_format}}",
            va="center",
            size=charts_cfg.font.annot_size,
        )
        ax.text(
            row["中位数"], i + text_move,
            f"M:{row['中位数']:{annot.point_format}}",
            ha="center", size=charts_cfg.font.annot_size,
        )
        ax.text(
            row["Q1"], i + text_move,
            f"Q1:{row['Q1']:{annot.point_format}}",
            ha="right", size=charts_cfg.font.annot_size,
        )
        ax.text(
            row["Q3"], i + text_move,
            f"Q3:{row['Q3']:{annot.point_format}}",
            ha="left", size=charts_cfg.font.annot_size,
        )

    ax.set_xlim(xmin, xmax * charts_cfg.axis.xlim_factor)
    ax.set_xticks(ticks)
    ax.tick_params(axis="both", labelsize=charts_cfg.font.tick_size)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_yticks(list(range(n)))
    ax.set_yticklabels(labels)
    ax.set_xlabel("成绩", size=charts_cfg.font.label_size)
    ax.set_ylabel("班级·考试", size=charts_cfg.font.label_size)
    ax.set_title(
        f"{'+'.join(classes)} 多场考试组合图（半提琴+指标）",
        size=charts_cfg.font.title_size,
    )
    if charts_cfg.show_lines:
        ax.legend(loc="lower right", fontsize=charts_cfg.font.legend_size)

    out_dir = type_dir(output, "charts") / (exams[0].semester or "")
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = date_range_suffix(exams)
    class_label = _class_label(classes)
    path = out_dir / f"按班级_{suffix}_{class_label}.{charts_cfg.format}"
    fig.savefig(path, dpi=charts_cfg.dpi, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def build_all_charts(
    exam: ExamConfig,
    score_df: pd.DataFrame,
    charts_cfg: ChartsConfig,
    output: OutputConfig,
) -> list[str]:
    """按配置的分组方式各生成一张组合图，返回路径列表。"""
    if not charts_cfg.enabled:
        return []
    metrics = compute_class_metrics(score_df)
    if metrics.empty:
        return []
    paths = []
    for group_col in charts_cfg.group_by:
        paths.append(
            build_group_chart(exam, score_df, metrics, group_col, charts_cfg, output)
        )
    return paths
