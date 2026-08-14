"""配置模块的单元测试。"""

from grade_analyzer.config import (
    AnalysisConfig,
    ExamConfig,
    normalize_exam_name,
    resolve_semester,
    semester_abbr,
)


def test_default_thresholds():
    cfg = AnalysisConfig()
    assert cfg.pass_ratio == 0.6
    assert cfg.excellent_ratio == 0.85
    assert cfg.absent_strategy == "exclude"


def test_subject_full_score_defaults():
    cfg = AnalysisConfig()
    assert cfg.defaults_for("语文").full_score == 150.0
    assert cfg.defaults_for("数学").full_score == 150.0
    assert cfg.defaults_for("外语").full_score == 150.0
    assert cfg.defaults_for("地理").full_score == 100.0
    assert cfg.defaults_for("技术").full_score == 100.0


def test_geography_objective_subjective_defaults():
    cfg = AnalysisConfig()
    geo = cfg.defaults_for("地理")
    assert geo.objective_full_score == 50.0
    assert geo.subjective_full_score == 50.0


def test_subject_word_list():
    cfg = AnalysisConfig()
    assert "语文" in cfg.subjects
    assert "技术" in cfg.subjects
    assert cfg.subject_aliases["外语"] == ["英语", "俄语", "日语"]


def test_exam_defaults_are_auto():
    exam = ExamConfig()
    assert exam.format is None
    assert exam.subject is None
    assert exam.default_grade is None
    assert exam.type == "默认"


def test_importance_derived_and_override():
    assert ExamConfig(format="weekly").effective_importance() == "平时"
    assert ExamConfig(format="joint").effective_importance() == "联考"
    override = ExamConfig(format="weekly", importance="联考")
    assert override.effective_importance() == "联考"


def test_resolve_semester_prefers_explicit():
    assert resolve_semester("高一第一学期", "高一第二学期") == ("高一第一学期", False)
    assert resolve_semester(None, "高一第二学期") == ("高一第二学期", True)
    assert resolve_semester(None, None) == (None, True)


def test_semester_abbr():
    assert semester_abbr("高一第一学期") == "高一上"
    assert semester_abbr("高一第二学期") == "高一下"
    assert semester_abbr("高二第一学期") == "高二上"
    assert semester_abbr("高三第二学期") == "高三下"
    assert semester_abbr("未知学期") is None


def test_normalize_exam_name():
    assert normalize_exam_name("联考", "高一第二学期") == "高一下联考"
    assert (
        normalize_exam_name("高一下地理限时练一", "高一第二学期")
        == "高一下地理限时练一"
    )
    assert (
        normalize_exam_name("高一第二学期期中", "高一第二学期")
        == "高一第二学期期中"
    )
    assert normalize_exam_name(None, "高一第二学期") is None


def test_full_path_default_folder():
    p1 = ExamConfig(file="地理原始数据.xlsx").full_path.replace("\\", "/")
    assert p1 == "data/input/地理原始数据.xlsx"
    p2 = ExamConfig(
        folder="data/input/测试样例", file="地理原始数据.xlsx"
    ).full_path.replace("\\", "/")
    assert p2 == "data/input/测试样例/地理原始数据.xlsx"


def test_default_school_default_none():
    assert AnalysisConfig().default_school is None


def test_metadata_dirs_defaults():
    cfg = AnalysisConfig()
    assert cfg.classes_dir == "config/classes"
    assert cfg.subjects_dir == "config/subjects"
    assert cfg.class_infos == {}
    assert cfg.teacher_maps == {}
