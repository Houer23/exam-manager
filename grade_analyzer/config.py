"""配置加载与校验。

从 config/config.yaml 加载全局配置（科目词表、科目默认值、统计口径），
并从 config/exams/ 目录扫描加载每场考试的条目文件。
条目字段留空（None）表示"自动识别或使用默认值"。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date, datetime as _datetime
from pathlib import Path

import yaml


_GLOBAL_KEYS = {
    "analysis", "subjects", "subject_aliases", "subject_defaults",
    "default_full_score", "default_grade", "current_semester",
    "current_exam", "default_school", "input_dir", "parsed_dir", "parsed_format",
    "exams_dir", "classes_dir", "subjects_dir", "roster_dir", "charts_dir",
    "results_dir", "results_config_dir", "output_dir", "report_excel_name",
    "plugins",
}
_ANALYSIS_KEYS = {"pass_ratio", "excellent_ratio", "absent_strategy", "score_bands"}
_EXAM_KEYS = {
    "name", "format", "type", "importance", "folder", "file", "subject",
    "semester", "date", "full_score", "objective_full_score",
    "subjective_full_score", "objective_question_count", "default_grade",
    "sheet", "filter_by_selection",
    "short_name", "question_display", "show_big_questions",
}
_SUBJECT_DEFAULT_KEYS = {"full_score", "objective_full_score", "subjective_full_score"}
_CLASS_CONFIG_KEYS = {"level", "course"}


@dataclass
class ExamConfig:
    """一场考试的元信息。

    三个独立维度：
    - format：原始数据格式（weekly/joint），决定适配器，留空自动识别
    - type：考试类型（默认/学考/模考…），联合分析的筛选维度，缺省"默认"
    - importance：重要度（平时/联考），留空由 format 推导（joint->联考）

    其余字段：
    - name：weekly 从文件名提取；联考需显式填写
    - short_name：考试简称（个人成绩单内使用，必填，check 校验）
    - folder/file：原始成绩单所在文件夹与文件名（file 必填，folder 留空 = 全局 input_dir）
    - semester：学期全称（如 高一第一学期），规范表按此分目录
    - date：考试日期（YYYY-MM-DD，缺省=程序运行当日），决定趋势顺序
    - subject：留空从文件名推测
    - full_score / objective_full_score / subjective_full_score：留空用科目默认值
    - default_grade：留空用全局默认年级
    """

    name: str | None = None
    format: str | None = None
    type: str = "默认"
    importance: str | None = None
    folder: str | None = None
    file: str | None = None
    subject: str | None = None
    semester: str | None = None
    date: str | None = None
    full_score: float | None = None
    objective_full_score: float | None = None
    subjective_full_score: float | None = None
    objective_question_count: int | None = None  # 客观题数（题号大于该数为主观题；留空=按格式判定）
    default_grade: str | None = None
    sheet: str | None = None
    filter_by_selection: bool = True  # 名单核对是否按七选三过滤
    short_name: str | None = None  # 考试简称（留空 = 使用考试全称）
    question_display: str = "split"  # 个人成绩单小题呈现：split=分列 / merged=合并
    show_big_questions: bool = False  # 是否显示主观大题汇总分列
    config_path: str | None = None  # 考试条目 yaml 路径（内部用于缓存有效性判断）

    def effective_importance(self) -> str:
        """返回重要度：显式指定优先，否则由格式推导。"""
        if self.importance:
            return self.importance
        return "联考" if self.format == "joint" else "平时"

    @property
    def full_path(self) -> str:
        """原始成绩单完整路径（folder/file，folder 留空兜底 data/input）。"""
        folder = self.folder or "data/input"
        return str(Path(folder) / (self.file or ""))

    @property
    def effective_short_name(self) -> str:
        """考试简称：short_name 为空时使用考试全称。"""
        return self.short_name or self.name or ""


@dataclass
class SubjectDefaults:
    """一个科目的默认满分设置。"""

    full_score: float | None = None
    objective_full_score: float | None = None
    subjective_full_score: float | None = None


@dataclass
class ClassInfo:
    """班级配置：学情层次（A/B）与选科组合。"""

    level: str = "A"
    course: str = ""


@dataclass
class TeacherMap:
    """学科配置：教师代号（A 起连续大写字母）与班级分配。"""

    subject: str = ""
    teacher_count: int = 0
    teacher_names: dict[str, str] = field(default_factory=dict)
    class_teachers: dict[str, str] = field(default_factory=dict)

    def teacher_for(self, class_name: str) -> str | None:
        """返回班级的任课教师名称（字母代号转名称）；未分配返回 None。"""
        code = self.class_teachers.get(class_name)
        if code is None:
            return None
        return self.teacher_names.get(code)


@dataclass
class OutputConfig:
    """输出配置。"""

    dir: str = "data/output"
    excel_name: str = "成绩分析汇总.xlsx"


@dataclass
class AnalysisConfig:
    """完整分析配置。"""

    input_dir: str = "data/input"  # 默认成绩单输入目录（考试配置 folder 留空时使用）
    exams_dir: str = "config/exams"
    parsed_dir: str = "data/parsed"
    parsed_format: str = "csv"
    classes_dir: str = "config/classes"
    subjects_dir: str = "config/subjects"
    roster_dir: str = "data/roster"
    charts_dir: str = "config/charts"
    results_dir: str = "data/output/results"
    results_config_dir: str = "config/results"
    output_dir: str = "data/output"  # 总输出目录
    report_excel_name: str = "成绩分析汇总.xlsx"  # reports 汇总报告文件名
    output: OutputConfig = field(default_factory=OutputConfig)  # 兼容属性（加载后组装）
    # 插件白名单：None=自动发现全部 enabled 插件；[]=禁用全部；列表=只加载列出的插件
    plugins: list[str] | None = None
    # 常见科目词表（用于文件名识别）
    subjects: list[str] = field(
        default_factory=lambda: [
            "语文", "数学", "外语", "物理", "化学",
            "生物", "政治", "历史", "地理", "技术",
        ]
    )
    # 科目别名：如 英语/俄语/日语 -> 外语，信息技术/通用技术 -> 技术
    # （外语、技术为特殊科目，当前不做深入分析，仅保留识别词表）
    subject_aliases: dict[str, list[str]] = field(
        default_factory=lambda: {
            "外语": ["英语", "俄语", "日语"],
            "技术": ["信息技术", "通用技术"],
        }
    )
    # 科目默认值：full_score 缺省时用 default_full_score；
    # objective/subjective 缺省表示该科目默认无客观/主观满分
    subject_defaults: dict[str, SubjectDefaults] = field(
        default_factory=lambda: {
            "语文": SubjectDefaults(full_score=150.0),
            "数学": SubjectDefaults(full_score=150.0),
            "外语": SubjectDefaults(full_score=150.0),
            "地理": SubjectDefaults(
                full_score=100.0, objective_full_score=50.0, subjective_full_score=50.0
            ),
        }
    )
    default_full_score: float = 100.0
    default_grade: str = "高一"
    default_school: str | None = None  # 原始表无学校列时填充到规范表
    current_semester: str | None = None  # run/merge 默认按当前学期
    current_exam: list[int] | None = None  # 场次序号列表（1-n 按日期升序；0=第一场；负数=倒数；空=全部）
    pass_ratio: float = 0.6
    excellent_ratio: float = 0.85
    absent_strategy: str = "exclude"
    score_bands: list[float] = field(default_factory=lambda: [0.9, 0.8, 0.7, 0.6])
    exams: list[ExamConfig] = field(default_factory=list)
    # 运行时加载的元数据配置（不在 YAML 中配置）
    class_infos: dict[tuple[str, str], ClassInfo] = field(default_factory=dict)
    teacher_maps: dict[tuple[str, str], TeacherMap] = field(default_factory=dict)

    def defaults_for(self, subject: str) -> SubjectDefaults:
        """返回科目默认值；未配置的科目用全局默认满分。"""
        return self.subject_defaults.get(
            subject, SubjectDefaults(full_score=self.default_full_score)
        )

    def class_info(self, semester: str, class_name: str) -> ClassInfo | None:
        """按（学期, 班级）返回班级配置；未配置返回 None。"""
        return self.class_infos.get((semester, class_name))

    def teacher_for(
        self, semester: str, subject: str, class_name: str
    ) -> str | None:
        """按（学期, 学科, 班级）返回任课教师名称；未配置返回 None。"""
        teacher_map = self.teacher_maps.get((semester, subject))
        return teacher_map.teacher_for(class_name) if teacher_map else None


def _clean(value: object) -> object:
    """把空字符串归一化为 None，其余原样返回。"""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _to_positive_float(
    value: object, label: str, where: Path, required: bool = True
) -> float | None:
    """把配置值转为正数 float；空值与缺省返回 None（required=False 时）。"""
    value = _clean(value)
    if value is None:
        if required:
            raise ValueError(f"{where}: {label} 必填")
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{where}: {label} 应为数值，当前为 {value!r}")
    if num <= 0:
        raise ValueError(f"{where}: {label} 应大于 0，当前为 {num}")
    return num


def _load_exam_file(
    path: Path,
    folder_semester: str | None,
    subject_aliases: dict[str, list[str]] | None = None,
    input_dir: str = "data/input",
) -> ExamConfig:
    """解析单个考试条目文件。"""
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: 考试条目应为映射")
    unknown = set(raw) - _EXAM_KEYS
    if unknown:
        raise ValueError(f"{path}: 未知字段 {sorted(unknown)}")

    name = _clean(raw.get("name"))
    fmt = _clean(raw.get("format"))
    # 格式名不在此处硬校验：未知格式在 check/parse 时按注册表给出提示
    if fmt is not None and not isinstance(fmt, str):
        raise ValueError(f"{path}: format 应为字符串，当前为 {fmt!r}")
    exam_type = _clean(raw.get("type")) or "默认"
    importance = _clean(raw.get("importance"))
    folder = _clean(raw.get("folder")) or input_dir
    file_name = _clean(raw.get("file"))
    if not file_name:
        raise ValueError(f"{path}: file 必填")
    subject = _clean(raw.get("subject"))

    semester, _ = resolve_semester(_clean(raw.get("semester")), folder_semester)
    if not semester:
        raise ValueError(
            f"{path}: semester 缺失（请在条目中声明，或放入学期子文件夹）"
        )

    date = _clean(raw.get("date"))
    if date is None:
        date = _date.today().isoformat()
    else:
        try:
            parsed = _datetime.strptime(str(date), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"{path}: date 格式应为 YYYY-MM-DD，当前为 {date!r}")
        date = parsed.isoformat()  # 归一化：2026-4-20 -> 2026-04-20

    full_score = _to_positive_float(raw.get("full_score"), "full_score", path, False)
    objective_full_score = _to_positive_float(
        raw.get("objective_full_score"), "objective_full_score", path, False
    )
    subjective_full_score = _to_positive_float(
        raw.get("subjective_full_score"), "subjective_full_score", path, False
    )
    raw_oqc = _clean(raw.get("objective_question_count"))
    objective_question_count = None
    if raw_oqc is not None:
        try:
            objective_question_count = int(str(raw_oqc))
        except (TypeError, ValueError):
            raise ValueError(
                f"{path}: objective_question_count 应为正整数，当前为 {raw_oqc!r}"
            )
        if objective_question_count <= 0:
            raise ValueError(
                f"{path}: objective_question_count 应大于 0，当前为 {objective_question_count}"
            )
    default_grade = _clean(raw.get("default_grade"))
    sheet = _clean(raw.get("sheet"))
    short_name = _clean(raw.get("short_name"))
    raw_fbs = raw.get("filter_by_selection", True)
    if isinstance(raw_fbs, str):
        filter_by_selection = raw_fbs.strip().lower() not in (
            "", "false", "0", "no", "否",
        )
    else:
        filter_by_selection = bool(raw_fbs)
    question_display = str(raw.get("question_display", "split"))
    if question_display not in {"split", "merged"}:
        raise ValueError(f"{path}: question_display 应为 split/merged")
    raw_sbq = raw.get("show_big_questions", False)
    if isinstance(raw_sbq, str):
        show_big_questions = raw_sbq.strip().lower() not in (
            "", "false", "0", "no", "否",
        )
    else:
        show_big_questions = bool(raw_sbq)

    # name 非必填：留空由文件名提取；规范名 = 学期简写 + 科目 + 考试名
    name = normalize_exam_name(name, semester, subject, subject_aliases)

    return ExamConfig(
        name=name,
        format=fmt,
        type=exam_type,
        importance=importance,
        folder=folder,
        file=file_name,
        subject=subject,
        semester=semester,
        date=date,
        full_score=full_score,
        objective_full_score=objective_full_score,
        subjective_full_score=subjective_full_score,
        objective_question_count=objective_question_count,
        default_grade=default_grade,
        sheet=sheet,
        filter_by_selection=filter_by_selection,
        short_name=short_name,
        question_display=question_display,
        show_big_questions=show_big_questions,
        config_path=str(path),
    )


def _load_exams(
    exams_dir: str,
    cfg_path: Path,
    subject_aliases: dict[str, list[str]] | None = None,
    input_dir: str = "data/input",
) -> list[ExamConfig]:
    """扫描并解析全部考试条目，检查名称唯一性。"""
    root = Path(exams_dir)
    if not root.is_dir():
        raise ValueError(f"{cfg_path}: exams_dir 不存在: {root}")

    exams = [
        _load_exam_file(
            Path(file_path), folder_semester, subject_aliases, input_dir
        )
        for file_path, folder_semester in discover_exam_files(exams_dir)
    ]
    seen: dict[str, str] = {}
    for exam in exams:
        if exam.name is None:
            continue  # weekly 名称在解析阶段从文件名提取后再校验
        if exam.name in seen:
            raise ValueError(
                f"{cfg_path}: 考试名称重复 {exam.name!r}（{seen[exam.name]} 与 {exam.full_path}）"
            )
        seen[exam.name] = exam.full_path
    return exams


def load_config(path: str = "config/config.yaml") -> AnalysisConfig:
    """加载全局配置与 exams 目录下所有考试条目，校验后返回 AnalysisConfig。"""
    cfg_path = Path(path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"配置文件不存在: {cfg_path}")
    with open(cfg_path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{cfg_path}: 配置根节点应为映射")

    unknown = set(raw) - _GLOBAL_KEYS
    if unknown:
        raise ValueError(f"{cfg_path}: 未知配置键 {sorted(unknown)}")

    analysis = raw.get("analysis") or {}
    if not isinstance(analysis, dict):
        raise ValueError(f"{cfg_path}: analysis 应为映射")
    unknown = set(analysis) - _ANALYSIS_KEYS
    if unknown:
        raise ValueError(f"{cfg_path}: analysis 下未知配置键 {sorted(unknown)}")

    pass_ratio = float(analysis.get("pass_ratio", 0.6))
    excellent_ratio = float(analysis.get("excellent_ratio", 0.85))
    if not (0 < pass_ratio <= 1):
        raise ValueError(f"{cfg_path}: pass_ratio 应在 (0,1] 之间，当前为 {pass_ratio}")
    if not (0 < excellent_ratio <= 1):
        raise ValueError(
            f"{cfg_path}: excellent_ratio 应在 (0,1] 之间，当前为 {excellent_ratio}"
        )
    absent_strategy = analysis.get("absent_strategy", "exclude")
    if absent_strategy not in {"exclude", "include_zero"}:
        raise ValueError(
            f"{cfg_path}: absent_strategy 应为 exclude 或 include_zero"
        )
    score_bands = [float(v) for v in analysis.get("score_bands", [0.9, 0.8, 0.7, 0.6])]
    if not score_bands or sorted(score_bands, reverse=True) != score_bands:
        raise ValueError(f"{cfg_path}: score_bands 应为非空降序数值列表")
    if any(not (0 < v <= 1) for v in score_bands):
        raise ValueError(f"{cfg_path}: score_bands 值应在 (0,1] 之间")

    raw_current_exam = _clean(raw.get("current_exam"))
    current_exam: list[int] | None = None
    if raw_current_exam is not None:
        if isinstance(raw_current_exam, (list, tuple)):
            parts = [str(v).strip() for v in raw_current_exam]
        else:
            parts = [p.strip() for p in str(raw_current_exam).split(",")]
        parsed: list[int] = []
        for part in parts:
            if part == "":
                continue
            try:
                parsed.append(int(part))
            except ValueError:
                raise ValueError(
                    f"{cfg_path}: current_exam 应为整数列表"
                    f"（1-n 按日期升序；0=第一场；负数=倒数；逗号分隔），"
                    f"当前为 {raw_current_exam!r}"
                )
        if parsed:
            current_exam = parsed

    subjects_raw = raw.get("subjects")
    if not isinstance(subjects_raw, list) or not subjects_raw:
        raise ValueError(f"{cfg_path}: subjects 应为非空列表")
    subjects = [str(s) for s in subjects_raw]

    aliases_raw = raw.get("subject_aliases") or {}
    if not isinstance(aliases_raw, dict):
        raise ValueError(f"{cfg_path}: subject_aliases 应为映射")
    subject_aliases: dict[str, list[str]] = {}
    for canonical, words in aliases_raw.items():
        if canonical not in subjects:
            raise ValueError(f"{cfg_path}: 别名目标 {canonical!r} 不在 subjects 中")
        if not isinstance(words, list) or not words:
            raise ValueError(f"{cfg_path}: subject_aliases[{canonical}] 应为非空列表")
        subject_aliases[str(canonical)] = [str(w) for w in words]

    sd_raw = raw.get("subject_defaults") or {}
    if not isinstance(sd_raw, dict):
        raise ValueError(f"{cfg_path}: subject_defaults 应为映射")
    subject_defaults: dict[str, SubjectDefaults] = {}
    for subject, info in sd_raw.items():
        if subject not in subjects:
            raise ValueError(f"{cfg_path}: subject_defaults 中 {subject!r} 不在 subjects 中")
        if not isinstance(info, dict):
            raise ValueError(f"{cfg_path}: subject_defaults[{subject}] 应为映射")
        unknown = set(info) - _SUBJECT_DEFAULT_KEYS
        if unknown:
            raise ValueError(
                f"{cfg_path}: subject_defaults[{subject}] 未知键 {sorted(unknown)}"
            )
        subject_defaults[str(subject)] = SubjectDefaults(
            full_score=_to_positive_float(
                info.get("full_score"), f"subject_defaults[{subject}].full_score", cfg_path, False
            ),
            objective_full_score=_to_positive_float(
                info.get("objective_full_score"),
                f"subject_defaults[{subject}].objective_full_score",
                cfg_path,
                False,
            ),
            subjective_full_score=_to_positive_float(
                info.get("subjective_full_score"),
                f"subject_defaults[{subject}].subjective_full_score",
                cfg_path,
                False,
            ),
        )

    raw_plugins = raw.get("plugins")
    plugins: list[str] | None = None
    if raw_plugins is not None:
        if not isinstance(raw_plugins, list):
            raise ValueError(f"{cfg_path}: plugins 应为列表（插件名白名单）或留空")
        plugins = [str(v) for v in raw_plugins]

    config = AnalysisConfig(
        input_dir=str(raw.get("input_dir", "data/input")),
        exams_dir=str(raw.get("exams_dir", "config/exams")),
        classes_dir=str(raw.get("classes_dir", "config/classes")),
        subjects_dir=str(raw.get("subjects_dir", "config/subjects")),
        parsed_dir=str(raw.get("parsed_dir", "data/parsed")),
        parsed_format=str(raw.get("parsed_format", "csv")),
        roster_dir=str(raw.get("roster_dir", "data/roster")),
        charts_dir=str(raw.get("charts_dir", "config/charts")),
        results_dir=str(raw.get("results_dir", "data/output/results")),
        results_config_dir=str(raw.get("results_config_dir", "config/results")),
        output_dir=str(raw.get("output_dir", "data/output")),
        report_excel_name=str(
            raw.get("report_excel_name", "成绩分析汇总.xlsx")
        ),
        plugins=plugins,
        subjects=subjects,
        subject_aliases=subject_aliases,
        subject_defaults=subject_defaults,
        default_full_score=_to_positive_float(
            raw.get("default_full_score", 100.0), "default_full_score", cfg_path
        ) or 100.0,
        default_grade=str(raw.get("default_grade", "高一")) or "高一",
        default_school=_clean(raw.get("default_school")),
        current_semester=_clean(raw.get("current_semester")),
        current_exam=current_exam,
        pass_ratio=pass_ratio,
        excellent_ratio=excellent_ratio,
        absent_strategy=absent_strategy,
        score_bands=score_bands,
    )
    config.output = OutputConfig(
        dir=config.output_dir, excel_name=config.report_excel_name
    )
    config.exams = _load_exams(
        config.exams_dir, cfg_path, subject_aliases, config.input_dir
    )
    config.class_infos = load_class_configs(config.classes_dir)
    config.teacher_maps = load_subject_configs(config.subjects_dir)
    return config


def load_class_configs(classes_dir: str) -> dict[tuple[str, str], ClassInfo]:
    """加载班级配置：<classes_dir>/<学期>.yaml，键为班级名（默认学校）。"""
    root = Path(classes_dir)
    if not root.is_dir():
        return {}
    result: dict[tuple[str, str], ClassInfo] = {}
    for f in sorted(root.glob("*.yaml")):
        if f.name.startswith("_"):
            continue
        semester = f.stem
        with open(f, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"{f}: 班级配置应为映射（班级 -> level/course）")
        for class_name, info in raw.items():
            if not isinstance(info, dict):
                raise ValueError(f"{f}: 班级 {class_name} 的配置应为映射")
            unknown = set(info) - _CLASS_CONFIG_KEYS
            if unknown:
                raise ValueError(f"{f}: 班级 {class_name} 未知键 {sorted(unknown)}")
            level = str(info.get("level", "A")).strip()
            if level not in {"A", "B"}:
                raise ValueError(
                    f"{f}: 班级 {class_name} 的 level 只能为 A/B，当前为 {level!r}"
                )
            course = str(info.get("course", "")).strip()
            key = (semester, class_name)
            if key in result:
                raise ValueError(f"{f}: 班级重复配置 {semester}/{class_name}")
            result[key] = ClassInfo(level=level, course=course)
    return result


def load_subject_configs(
    subjects_dir: str,
) -> dict[tuple[str, str], TeacherMap]:
    """加载学科配置：<subjects_dir>/<学期>_<学科>.yaml。"""
    root = Path(subjects_dir)
    if not root.is_dir():
        return {}
    result: dict[tuple[str, str], TeacherMap] = {}
    for f in sorted(root.glob("*.yaml")):
        if f.name.startswith("_"):
            continue
        if "_" not in f.stem:
            raise ValueError(f"{f}: 学科配置文件名应为 <学期>_<学科>.yaml")
        semester, subject = f.stem.split("_", 1)
        with open(f, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"{f}: 学科配置应为映射")
        allowed = {"subject", "teacher_count", "teacher_names", "class_teachers"}
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"{f}: 未知键 {sorted(unknown)}")

        subject = str(raw.get("subject", subject)).strip() or subject
        try:
            teacher_count = int(raw.get("teacher_count", 0))
        except (TypeError, ValueError):
            raise ValueError(f"{f}: teacher_count 应为整数")
        if teacher_count <= 0:
            raise ValueError(f"{f}: teacher_count 应大于 0")

        names_raw = raw.get("teacher_names") or {}
        class_raw = raw.get("class_teachers") or {}
        if not isinstance(names_raw, dict) or not isinstance(class_raw, dict):
            raise ValueError(f"{f}: teacher_names/class_teachers 应为映射")
        teacher_names = {str(k): str(v) for k, v in names_raw.items()}
        expected_codes = [chr(ord("A") + i) for i in range(teacher_count)]
        actual_codes = sorted(teacher_names)
        if actual_codes != expected_codes or len(teacher_names) != teacher_count:
            raise ValueError(
                f"{f}: 教师代号应为 {expected_codes}（数量 {teacher_count}），"
                f"当前为 {actual_codes}"
            )

        class_teachers = {str(k): str(v) for k, v in class_raw.items()}
        for class_name, code in class_teachers.items():
            if code not in teacher_names:
                raise ValueError(
                    f"{f}: 班级 {class_name} 的教师代号 {code!r} 不在 teacher_names 中"
                )
        key = (semester, subject)
        if key in result:
            raise ValueError(f"{f}: 学科配置重复 {semester}/{subject}")
        result[key] = TeacherMap(
            subject=subject,
            teacher_count=teacher_count,
            teacher_names=teacher_names,
            class_teachers=class_teachers,
        )
    return result


def resolve_semester(
    explicit: str | None, folder_default: str | None
) -> tuple[str | None, bool]:
    """解析考试条目所属学期。

    优先级：配置文件显式声明 > 子文件夹名称。
    返回 (学期, 是否来自文件夹默认值)。
    """
    if explicit:
        return explicit, False
    return folder_default, True


_SEMESTER_TERM_ABBR = {"第一学期": "上", "第二学期": "下"}


def semester_abbr(semester: str) -> str | None:
    """学期简称：高一第一学期 -> 高一上；无法识别返回 None。"""
    for term, abbr in _SEMESTER_TERM_ABBR.items():
        if semester.endswith(term):
            grade = semester[: -len(term)]
            if grade.startswith("高") and len(grade) == 2:
                return grade + abbr
    return None


def normalize_exam_name(
    name: str | None,
    semester: str | None,
    subject: str | None = None,
    subject_aliases: dict[str, list[str]] | None = None,
) -> str | None:
    """规范化考试名称：学期简写 + 科目 + 考试名，逐段判断已存在则不重复添加。

    - name 为 None（留待文件名提取）时原样返回；
    - 学期：已含学期全称或简称时不再添加，无法推导简称时不添加；
    - 科目：name 已含科目规范名或其别名时不再添加（如 外语 的别名 英语）。
    """
    if not name:
        return name
    parts = ""
    abbr = semester_abbr(semester) if semester else None
    if abbr and abbr not in name and semester not in name:
        # 考试名已含年级（如 高一）时，去掉原年级，避免 高一下高一... 重复
        grade = abbr[:-1]  # 学期简写去掉 上/下 -> 年级（如 高一）
        if (
            grade
            and name.startswith(grade)
            and not name.startswith(grade + "上")
            and not name.startswith(grade + "下")
        ):
            name = name[len(grade):]
        parts += abbr
    if subject and subject not in name:
        aliases = (subject_aliases or {}).get(subject, [])
        if not any(alias and alias in name for alias in aliases):
            parts += subject
    return parts + name


def discover_exam_files(
    exams_dir: str,
) -> list[tuple[str, str | None]]:
    """扫描 exams 目录，返回 [(条目文件路径, 默认学期)]。

    - 根目录下的 *.yaml：默认学期为 None（条目须显式声明 semester）；
    - 子目录（如 高一第二学期/）下的 *.yaml：默认学期 = 子目录名；
    - 忽略 _ 开头文件（如 _template.yaml）与 _ 开头目录。
    """
    root = Path(exams_dir)
    if not root.is_dir():
        return []
    result: list[tuple[str, str | None]] = []
    for f in sorted(root.glob("*.yaml")):
        if f.name.startswith("_"):
            continue
        result.append((str(f), None))
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        for f in sorted(d.glob("*.yaml")):
            if f.name.startswith("_"):
                continue
            result.append((str(f), d.name))
    return result
