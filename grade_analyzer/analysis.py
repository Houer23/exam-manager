"""统计分析计算。

包含：科目统计、分数段分布、个人排名、分组对比、多场次趋势。
输入为合并长表或单场规范表，输出 DataFrame；缺考（NaN）不参与统计。
"""

from __future__ import annotations

import pandas as pd


ZH_COLUMNS = {
    "exam_name": "考试名称",
    "student_id": "考号",
    "name": "姓名",
    "class_name": "班级",
    "class_level": "学情层次",
    "teacher": "教师",
    "course": "选科组合",
    "subject": "科目",
    "total_score": "总分",
    "total_ratio": "得分率",
}


def zh_columns(df: pd.DataFrame) -> pd.DataFrame:
    """把英文变量名列名替换为中文列名。"""
    return df.rename(columns=ZH_COLUMNS)


def compute_subject_stats(df: pd.DataFrame, config) -> pd.DataFrame:
    """每场考试 × 每科：考生数、平均分、最高/最低、标准差、及格率、优秀率。"""
    rows = []
    for (exam_name, subject), g in df.groupby(["exam_name", "subject"]):
        valid = g[g["total_score"].notna()]
        n = len(valid)
        if n == 0:
            continue
        ratios = valid["total_ratio"]
        rows.append(
            {
                "考试名称": exam_name,
                "科目": subject,
                "考生数": n,
                "平均分": valid["total_score"].mean(),
                "最高分": valid["total_score"].max(),
                "最低分": valid["total_score"].min(),
                "标准差": valid["total_score"].std(),
                "平均得分率": round(ratios.mean(), 5),
                "及格率": round((ratios >= config.pass_ratio).mean(), 5),
                "优秀率": round((ratios >= config.excellent_ratio).mean(), 5),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "考试名称", "科目", "考生数", "平均分", "最高分", "最低分",
            "标准差", "平均得分率", "及格率", "优秀率",
        ],
    )


def compute_distribution(df: pd.DataFrame, config) -> pd.DataFrame:
    """分数段分布（得分率口径，按分数段降序排列）。

    - 90+ 分段始终保留；
    - 60 分以下每 10 分一段继续细分，直至最底段占比 < 0.1；
      最底段为该段及以下所有学生的合并段（如 <40）。
    """
    bands = sorted(config.score_bands, reverse=True)
    all_rows: list[dict] = []
    for (exam_name, subject), g in df.groupby(["exam_name", "subject"]):
        ratios = pd.to_numeric(g["total_ratio"], errors="coerce").dropna()
        total = len(ratios)
        if total == 0:
            continue
        band_rows = _band_rows(ratios, bands, total)
        props = [count / total for _, count in band_rows]
        fwd: list[float] = []
        acc = 0.0
        for p in props:
            acc += p
            fwd.append(acc)
        rev = [0.0] * len(props)
        acc = 0.0
        for i in range(len(props) - 1, -1, -1):
            acc += props[i]
            rev[i] = acc
        for (label, count), p, f, r in zip(band_rows, props, fwd, rev):
            all_rows.append(
                {
                    "考试名称": exam_name,
                    "科目": subject,
                    "分数段": label,
                    "人数": count,
                    "占比": round(p, 5),
                    "正向累计占比": round(f, 5),
                    "逆向累计占比": round(r, 5),
                }
            )
    return pd.DataFrame(
        all_rows,
        columns=[
            "考试名称", "科目", "分数段", "人数",
            "占比", "正向累计占比", "逆向累计占比",
        ],
    )


def _band_rows(
    ratios: pd.Series, bands: list[float], total: int
) -> list[tuple[str, int]]:
    """计算单个（考试, 科目）的分数段行，返回 [(标签, 人数)]（降序）。"""
    rows: list[tuple[str, int]] = []
    for i, b in enumerate(bands):
        if i == 0:
            count = int((ratios >= b).sum())
            rows.append((f"{b * 100:g}+", count))
        else:
            count = int(((ratios >= b) & (ratios < bands[i - 1])).sum())
            rows.append((f"{b * 100:g}-{bands[i - 1] * 100 - 1:g}", count))

    # 60 分以下每 10 分一段，从最底向上累加，直至底段占比 >= 0.1
    below = bands[-1]
    step = 0.1
    slices: list[tuple[float, float]] = []
    top = round(below * 10)  # 十分位段数，如 0.6 -> 6
    for i in range(top, 0, -1):
        slices.append(((i - 1) / 10.0, i / 10.0))
    slices = list(reversed(slices))  # 升序：0-9, 10-19, ...

    acc = 0
    bottom_upper = below
    for lower, upper in slices:
        count = int(((ratios >= lower) & (ratios < upper)).sum())
        acc += count
        if acc / total >= 0.1:
            bottom_upper = lower
            break

    # 底段之上的独立十分段（降序：50-59, 40-49, ...）
    for lower, upper in reversed(slices):
        if lower < bottom_upper - 1e-9:
            continue
        count = int(((ratios >= lower) & (ratios < upper)).sum())
        rows.append((f"{lower * 100:g}-{upper * 100 - 1:g}", count))

    # 最底段（占比 < 0.1）
    if bottom_upper > 1e-9:
        rows.append((f"<{bottom_upper * 100:g}", int((ratios < bottom_upper).sum())))
    return rows


def compute_rankings(score_df: pd.DataFrame) -> pd.DataFrame:
    """单场个人排名：按总分降序，缺考（NaN）排最后。"""
    df = score_df.sort_values(
        "total_score", ascending=False, na_position="last"
    ).copy()
    cols = [
        c
        for c in [
            "exam_name", "student_id", "name", "class_name",
            "total_score", "total_ratio", "班次", "校次",
        ]
        if c in df.columns
    ]
    return zh_columns(df[cols].reset_index(drop=True))


def compute_average_rankings(long_df: pd.DataFrame) -> pd.DataFrame:
    """多场综合排名：按平均得分率降序，附参考场次。"""
    valid = long_df.dropna(subset=["total_ratio"])
    grouped = valid.groupby("student_id")
    rows = []
    for sid, g in grouped:
        rows.append(
            {
                "考号": sid,
                "班级": g["class_name"].dropna().iloc[-1] if g["class_name"].notna().any() else "",
                "学校": g["school"].dropna().iloc[-1] if g["school"].notna().any() else "",
                "平均得分率": round(g["total_ratio"].mean(), 5),
                "参考场次": len(g),
            }
        )
    result = pd.DataFrame(rows, columns=["考号", "班级", "学校", "平均得分率", "参考场次"])
    return result.sort_values("平均得分率", ascending=False).reset_index(drop=True)


def compute_group_comparison(
    long_df: pd.DataFrame, group_cols: list[str], config
) -> pd.DataFrame:
    """分组对比：按指定列分组统计，组内按平均得分率排名（复用同一套逻辑）。"""
    rows = []
    keys = ["exam_name"] + list(group_cols)
    for key_vals, g in long_df.groupby(keys, dropna=False):
        valid = g[g["total_score"].notna()]
        n = len(valid)
        if n == 0:
            continue
        if not isinstance(key_vals, tuple):
            key_vals = (key_vals,)
        item = dict(zip(keys, key_vals))
        ratios = valid["total_ratio"]
        item.update(
            {
                "考生数": n,
                "平均分": valid["total_score"].mean(),
                "平均得分率": round(ratios.mean(), 5),
                "及格率": round((ratios >= config.pass_ratio).mean(), 5),
                "优秀率": round((ratios >= config.excellent_ratio).mean(), 5),
            }
        )
        rows.append(item)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    rank_keys = ["exam_name"] + (list(group_cols[:-1]) if len(group_cols) > 1 else [])
    result["组内排名"] = result.groupby(rank_keys)["平均得分率"].rank(
        method="min", ascending=False
    )
    result = zh_columns(result)
    sort_cols = ["考试名称"] + (
        [ZH_COLUMNS.get(c, c) for c in group_cols[:-1]]
        if len(group_cols) > 1
        else []
    ) + ["组内排名"]
    result = result.sort_values(sort_cols).reset_index(drop=True)
    return result


def compute_trends(long_df: pd.DataFrame, config) -> tuple[pd.DataFrame, pd.DataFrame]:
    """多场趋势：返回 (场次趋势表, 学生进退步表)。"""
    df = long_df.copy()
    df["exam_date"] = pd.to_datetime(df["exam_date"], errors="coerce")
    df = df.sort_values(["subject", "school", "student_id", "exam_date"])

    trend_rows = []
    for (exam_name, subject), g in df.groupby(["exam_name", "subject"]):
        valid = g[g["total_ratio"].notna()]
        n = len(valid)
        ratios = valid["total_ratio"]
        trend_rows.append(
            {
                "考试名称": exam_name,
                "科目": subject,
                "日期": g["exam_date"].dropna().max(),
                "考生数": n,
                "平均得分率": round(ratios.mean(), 5) if n else None,
                "及格率": round((ratios >= config.pass_ratio).mean(), 5) if n else None,
                "优秀率": round((ratios >= config.excellent_ratio).mean(), 5) if n else None,
            }
        )
    trends = pd.DataFrame(
        trend_rows,
        columns=["考试名称", "科目", "日期", "考生数", "平均得分率", "及格率", "优秀率"],
    )
    if not trends.empty:
        trends = trends.sort_values(["科目", "日期"]).reset_index(drop=True)

    progress_rows = []
    for _, g in df.groupby(["subject", "school", "student_id"]):
        g = g.dropna(subset=["total_ratio"])
        if len(g) < 2:
            continue
        prev_ratio = None
        prev_rank = None
        for _, row in g.iterrows():
            cur_ratio = row["total_ratio"]
            cur_rank = row.get("校次")
            if prev_ratio is not None:
                diff = cur_ratio - prev_ratio
                status = "进步" if diff > 0.001 else ("退步" if diff < -0.001 else "持平")
                rank_change = (
                    (prev_rank - cur_rank)
                    if prev_rank is not None and cur_rank is not None
                    else None
                )
                progress_rows.append(
                    {
                        "考号": row["student_id"],
                        "班级": row.get("class_name"),
                        "学校": row.get("school"),
                        "科目": row["subject"],
                        "考试名称": row["exam_name"],
                        "日期": row["exam_date"],
                        "本次得分率": round(cur_ratio, 5),
                        "上次得分率": round(prev_ratio, 5),
                        "得分率变化": round(diff, 5),
                        "状态": status,
                        "本次校次": cur_rank,
                        "上次校次": prev_rank,
                        "校次变化": rank_change,
                    }
                )
            prev_ratio = cur_ratio
            prev_rank = cur_rank
    progress = pd.DataFrame(progress_rows)
    return trends, progress
