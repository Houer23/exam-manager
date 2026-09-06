"""数据清洗与质量校验。

职责：考号校验、班级归一化、总分边界校验、去重、缺失/缺考处理，
并生成数据质量问题清单。
"""

from __future__ import annotations

import re

import pandas as pd

from .config import AnalysisConfig, ExamConfig


def extract_grade(class_raw: str) -> str | None:
    """从班级原始值提取年级（高一/高二/高三），无法提取返回 None。"""
    match = re.search(r"高[一二三]", class_raw or "")
    return match.group(0) if match else None


def normalize_class_name(
    class_raw: str, default_grade: str
) -> tuple[str, str | None]:
    """班级归一化为 高XDD班，返回 (规范班级, 年级)。

    规则（按顺序尝试）：
    1. 高一年级4班 / 高一年级16班 -> 高一04班 / 高一16班；
    2. 高一(10) -> 高一10班；
    3. 纯数字 3 -> 年级取 default_grade，输出 高一03班。

    全部失败返回 (原始班级, None)。
    """
    text = str(class_raw).strip() if class_raw is not None else ""
    if not text:
        return "", None

    m = re.fullmatch(r"高([一二三])(?:年级)?(\d+)班?", text)
    if m:
        grade = f"高{m.group(1)}"
        return f"{grade}{int(m.group(2)):02d}班", grade

    m = re.fullmatch(r"高([一二三])[（(](\d+)[)）]班?", text)
    if m:
        grade = f"高{m.group(1)}"
        return f"{grade}{int(m.group(2)):02d}班", grade

    m = re.fullmatch(r"(\d+)", text)
    if m:
        grade = extract_grade(default_grade) or default_grade
        return f"{grade}{int(m.group(1)):02d}班", grade

    return text, extract_grade(text)


def resolve_class_spec(text: str, default_grade: str) -> list[str]:
    """把数字班级写法解析为规范班级名列表（与 CLI --class 一致）。

    支持逗号分隔、n-m 连续区间（含两端；n>m 时取反向），
    如 "10,12-14" -> 高一10/12/13/14班；"14-12" -> 14,13,12班。
    """
    nums: list[int] = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                a_s, b_s = part.split("-", 1)
                a, b = int(a_s), int(b_s)
            except ValueError:
                raise ValueError(
                    f"班级区间应为 n-m（如 10-12），当前为 {part!r}"
                )
            if a <= b:
                nums.extend(range(a, b + 1))
            else:
                nums.extend(range(a, b - 1, -1))
        else:
            try:
                nums.append(int(part))
            except ValueError:
                raise ValueError(
                    f"班级应为数字或区间（如 10,11 或 10-12），当前为 {part!r}"
                )
    if not nums:
        raise ValueError("班级写法未提供有效班级数字")
    seen: set[int] = set()
    ordered: list[int] = []
    for n in nums:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return [f"{default_grade}{n:02d}班" for n in ordered]


def validate_student_ids(df: pd.DataFrame) -> None:
    """校验考号：缺失、非 12 位数字、场次内重复 -> 报错终止。"""
    ids = df["student_id"].astype(str).str.strip()
    problems: list[str] = []

    missing = ids.isin(["", "nan", "None"]).sum()
    if missing:
        problems.append(f"{missing} 行考号缺失")

    bad_mask = ~ids.str.fullmatch(r"\d{12}")
    bad = ids[bad_mask]
    if len(bad):
        problems.append(f"{len(bad)} 行考号非 12 位数字，如 {bad.head(5).tolist()}")

    dup = ids[ids.duplicated(keep=False)]
    if len(dup):
        problems.append(f"{len(dup)} 行考号重复，如 {sorted(set(dup))[:5]}")

    if problems:
        raise ValueError("考号校验失败：" + "；".join(problems))


def validate_total_score(df: pd.DataFrame, full_score: float) -> None:
    """总分边界校验：0 <= 总分 <= 满分，超界报错终止。"""
    if full_score is None:
        return
    totals = pd.to_numeric(df["total_score"], errors="coerce")
    bad = df[totals.notna() & ((totals > full_score) | (totals < 0))]
    if len(bad):
        ids = bad["student_id"].astype(str).tolist()
        raise ValueError(
            f"总分越界（满分 {full_score:g}）：{len(bad)} 行，如 {ids[:5]}"
        )


def drop_empty_score_records(
    score: pd.DataFrame,
    questions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """去掉所有得分列均为空的记录。

    以小题明细为准：某学生没有任何一道题得分（含空白/非数值）时，
    视为空记录，从总分表与小题明细中同步删除。
    全部为 0 分的学生不算空记录（0 分也是有效得分）。
    """
    if questions.empty or "score" not in questions.columns:
        return score, questions, 0
    q = questions.copy()
    q["_score"] = pd.to_numeric(q["score"], errors="coerce")
    has_any = q.groupby("student_id")["_score"].transform(
        lambda s: s.notna().any()
    )
    keep_ids = set(q.loc[has_any, "student_id"].astype(str).unique())
    score_mask = score["student_id"].astype(str).isin(keep_ids)
    dropped = int((~score_mask).sum())
    if dropped == 0:
        return score, questions, 0
    questions_mask = questions["student_id"].astype(str).isin(keep_ids)
    return (
        score[score_mask].reset_index(drop=True),
        questions[questions_mask].reset_index(drop=True),
        dropped,
    )


def collect_quality_issues(
    score: pd.DataFrame, exam: ExamConfig, config: AnalysisConfig
) -> pd.DataFrame:
    """软校验清单：客观/主观超满分、客观+主观≠总分、班级无法归一化。"""
    rows: list[tuple[str, str, str]] = []
    totals = pd.to_numeric(score["total_score"], errors="coerce")
    obj = pd.to_numeric(score["objective_score"], errors="coerce")
    subj = pd.to_numeric(score["subjective_score"], errors="coerce")

    if exam.objective_full_score:
        over = score[obj.notna() & (obj > exam.objective_full_score)]
        for _, r in over.iterrows():
            rows.append(
                (
                    str(r["student_id"]),
                    "客观分超满分",
                    f"{r['objective_score']:g} > {exam.objective_full_score:g}",
                )
            )
    if exam.subjective_full_score:
        over = score[subj.notna() & (subj > exam.subjective_full_score)]
        for _, r in over.iterrows():
            rows.append(
                (
                    str(r["student_id"]),
                    "主观分超满分",
                    f"{r['subjective_score']:g} > {exam.subjective_full_score:g}",
                )
            )

    mask = totals.notna() & obj.notna() & subj.notna()
    diff = (obj + subj - totals).abs()
    for i in score.index[mask & (diff > 1e-6)]:
        rows.append(
            (
                str(score.loc[i, "student_id"]),
                "客观+主观≠总分",
                f"差 {diff.loc[i]:g}",
            )
        )

    for _, r in score.iterrows():
        raw = str(r["class_raw"]).strip()
        cls = str(r["class_name"]).strip()
        if raw and cls == raw and extract_grade(raw) is None:
            rows.append((str(r["student_id"]), "班级无法归一化", raw))

    issues_df = pd.DataFrame(rows, columns=["考号", "问题类型", "说明"])
    if issues_df.empty:
        return issues_df.reindex(columns=["考试名称", "考号", "问题类型", "说明"])
    issues_df["考试名称"] = exam.name
    return issues_df[["考试名称", "考号", "问题类型", "说明"]]


def compute_ranks(score: pd.DataFrame) -> None:
    """以考号为索引，计算总成绩在所在班级、学校的排位。

    竞争排名：同分同名次（取靠前的较小名次），名次 = 前面真实人数 + 1，
    可能出现不连续（如 90/90/80 -> 1/1/3）。
    班次按（学校, 班级）联合分组，不同学校的同名班级不合并。
    班级、学校缺失或总分为缺考的行排位为空。
    """
    score["班次"] = float("nan")
    score["校次"] = float("nan")
    has_class = score["class_name"].fillna("").astype(str).str.strip() != ""
    has_school = score["school"].fillna("").astype(str).str.strip() != ""
    has_both = has_school & has_class
    if has_both.any():
        score.loc[has_both, "班次"] = (
            score.loc[has_both]
            .groupby(["school", "class_name"])["total_score"]
            .rank(method="min", ascending=False)
        )
    if has_school.any():
        score.loc[has_school, "校次"] = (
            score.loc[has_school]
            .groupby("school")["total_score"]
            .rank(method="min", ascending=False)
        )


def add_question_type_scores(
    score: pd.DataFrame, questions: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """按题型动态汇总得分与满分。

    每题实际满分 = 该题最高得分；
    score 表为每个题型（除 客观/主观，对应 objective_score/subjective_score）新增
    {题型}分 / {题型}满分（如 单选分/多选分/听力分/作文分）；
    questions 表回填每题 full_score。缺考学生的分项得分为空。
    """
    q = questions.copy()
    q["full_score"] = q.groupby("question_id")["score"].transform("max")
    score = score.copy()
    for qtype in q["question_type"].dropna().unique():
        if qtype in ("客观", "主观"):
            continue  # 对应 objective_score / subjective_score
        sub = q[q["question_type"] == qtype]
        score[f"{qtype}分"] = score["student_id"].map(
            sub.groupby("student_id")["score"].sum()
        )
        score[f"{qtype}满分"] = (
            sub.groupby("question_id")["full_score"].first().sum()
        )
    return score, q


def classify_objective_types(
    questions: pd.DataFrame, exam=None
) -> pd.DataFrame:
    """区分客观题中的单选题/多选题。

    - 题型配置显式含 单选/多选 时以配置为准（不做自动区分）；
    - 考试开关 auto_single_multi=false（默认）时不做自动区分，客观题保持 客观；
    - 开关为 true 时才按各题实际最高得分区分
      （最高得分较小的为单选题，较大的为多选题）；
    - 若所有客观题最高得分相同，则该场无多选题（保持 客观）。
    """
    if exam is not None and exam.question_types:
        from .question_types import resolve_question_types

        plan = resolve_question_types(
            exam.question_types, exam.binary_split, exam.objective_question_count
        )
        if plan is not None and ("单选" in plan.ranges or "多选" in plan.ranges):
            return questions
    if exam is not None and not exam.auto_single_multi:
        return questions
    obj = questions[questions["question_type"] == "客观"]
    if obj.empty:
        return questions
    max_by_q = obj.groupby("question_id")["score"].max()
    distinct = sorted(max_by_q.unique())
    if len(distinct) < 2:
        return questions
    single_max = distinct[0]
    multi_ids = set(max_by_q[max_by_q > single_max].index)
    mask = questions["question_type"] == "客观"
    questions.loc[mask & questions["question_id"].isin(multi_ids), "question_type"] = "多选"
    questions.loc[mask & ~questions["question_id"].isin(multi_ids), "question_type"] = "单选"
    return questions


def filter_default_school(
    score: pd.DataFrame,
    questions: pd.DataFrame,
    default_school: str | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """单学校模型：只保留默认学校的学生（成绩表与小题表同步过滤）。"""
    if not default_school:
        return score, questions
    kept = score[score["school"] == default_school]
    if kept.empty:
        raise ValueError(f"默认学校 {default_school} 在数据中无记录")
    ids = set(kept["student_id"])
    return (
        kept.reset_index(drop=True),
        questions[questions["student_id"].isin(ids)].reset_index(drop=True),
    )


def enrich_metadata(
    score: pd.DataFrame, exam: ExamConfig, config: AnalysisConfig
) -> pd.DataFrame:
    """补齐班级学情层次/选科组合/任课教师；未配置的班级留空（归"未配置"组）。"""
    score = score.copy()
    level_map: dict[str, str] = {}
    course_map: dict[str, str] = {}
    for (semester, class_name), info in config.class_infos.items():
        if semester == exam.semester:
            level_map[class_name] = info.level
            course_map[class_name] = info.course
    teacher_map: dict[str, str] = {}
    teacher_map_obj = config.teacher_maps.get((exam.semester, exam.subject))
    if teacher_map_obj:
        teacher_map = {
            class_name: teacher_map_obj.teacher_for(class_name)
            for class_name in teacher_map_obj.class_teachers
        }
    score["class_level"] = score["class_name"].map(level_map).fillna("")
    score["course"] = score["class_name"].map(course_map).fillna("")
    score["teacher"] = score["class_name"].map(teacher_map).fillna("")
    return score


def clean_score_table(
    score: pd.DataFrame, exam: ExamConfig, config: AnalysisConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """清洗一场考试的科目总分表，返回 (清洗后表, 质量问题清单)。

    考号/总分校验失败时抛 ValueError 终止；
    班级归一化失败与客观/主观异常进入质量清单（不阻断）。
    """
    validate_student_ids(score)
    validate_total_score(score, exam.full_score)
    default_grade = exam.default_grade or config.default_grade
    pairs = [
        normalize_class_name(c, default_grade) for c in score["class_raw"]
    ]
    score["class_name"] = [p[0] for p in pairs]
    score["grade"] = [p[1] for p in pairs]
    compute_ranks(score)
    score = enrich_metadata(score, exam, config)
    issues = collect_quality_issues(score, exam, config)
    return score, issues


def clean_long_table(
    df: pd.DataFrame, config: AnalysisConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """清洗长表数据，返回 (清洗后数据, 质量问题清单)。

    TODO:
    1. 分数列转数值，空值按缺考标记；
    2. 完全重复记录（同学号+科目+场次）保留第一条；
    3. 生成质量问题清单（缺考号、班级无法归一化、客观/主观分与总分不一致等）。
    """
    raise NotImplementedError("清洗逻辑将在后续实现")
