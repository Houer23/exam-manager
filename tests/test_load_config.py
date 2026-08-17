"""配置加载的单元测试。"""

import datetime
from pathlib import Path

import pytest
import yaml

from grade_analyzer.config import load_config


def _write_global(tmp_path: Path, exams_dir: str | None = None, **overrides) -> Path:
    data = {
        "subjects": ["语文", "数学", "外语", "物理", "化学", "生物", "政治", "历史", "地理", "技术"],
        "subject_defaults": {
            "语文": {"full_score": 150},
            "地理": {
                "full_score": 100,
                "objective_full_score": 50,
                "subjective_full_score": 50,
            },
        },
        "exams_dir": exams_dir or str(tmp_path / "exams"),
    }
    data.update(overrides)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return cfg


def _write_exam(
    exams_dir: Path, folder_name: str | None, file_name: str, **fields
) -> Path:
    folder = exams_dir if folder_name is None else exams_dir / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    data = {"folder": "data/input", "file": f"{file_name}.xlsx", "subject": "地理"}
    data.update(fields)
    f = folder / f"{file_name}.yaml"
    f.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return f


def test_load_global_and_exams_from_folder(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第二学期", "周测", name="周测", date="2026-05-12")
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))

    assert len(cfg.exams) == 1
    exam = cfg.exams[0]
    assert exam.name == "高一下地理周测"  # 规范名 = 学期简写 + 科目 + 考试名
    assert exam.semester == "高一第二学期"  # 来自子文件夹名
    assert exam.date == "2026-05-12"
    assert exam.type == "默认"
    assert exam.subject == "地理"
    assert cfg.defaults_for("地理").objective_full_score == 50.0


def test_default_school_loaded(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测")
    cfg = load_config(
        str(_write_global(tmp_path, exams_dir=str(exams_dir), default_school="青田中学"))
    )
    assert cfg.default_school == "青田中学"


def test_date_defaults_to_today(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测")
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))
    assert cfg.exams[0].date == datetime.date.today().isoformat()


def test_date_without_padding_normalized(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测", date="2026-4-20")
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))
    assert cfg.exams[0].date == "2026-04-20"


def test_invalid_date_raises(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测", date="2026/04/20")
    with pytest.raises(ValueError, match="date"):
        load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))


def test_explicit_semester_overrides_folder(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(
        exams_dir, "高一第二学期", "周测", name="周测", semester="高一第一学期"
    )
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))
    assert cfg.exams[0].semester == "高一第一学期"
    assert cfg.exams[0].name == "高一上地理周测"


def test_empty_strings_normalized(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "周测", name="", format="")
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))
    assert cfg.exams[0].name is None
    assert cfg.exams[0].format is None


def test_missing_semester_raises(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, None, "周测", name="周测")
    with pytest.raises(ValueError, match="semester"):
        load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))


def test_duplicate_exam_name_raises(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测")
    _write_exam(exams_dir, "高一第一学期", "周测2", name="周测")
    with pytest.raises(ValueError, match="重复"):
        load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))


def test_missing_file_raises(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测", file="")
    with pytest.raises(ValueError, match="file"):
        load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))


def test_explicit_name_gets_semester_prefix(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第二学期", "联考", name="联考")
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))
    assert cfg.exams[0].name == "高一下地理联考"


def test_filter_by_selection_default_and_override(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "甲", name="甲")
    _write_exam(
        exams_dir, "高一第二学期", "乙", name="乙", filter_by_selection=False
    )
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))
    by_name = {e.name: e for e in cfg.exams}
    assert by_name["高一上地理甲"].filter_by_selection is True
    assert by_name["高一下地理乙"].filter_by_selection is False


def test_short_name_parsed(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "甲", name="甲", short_name="限时练一")
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))
    assert cfg.exams[0].short_name == "限时练一"


def test_joint_name_can_be_empty(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "联考", format="joint")
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))
    assert cfg.exams[0].name is None  # name 非必填，留空由文件名提取


def test_normalize_name_skips_subject_alias(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(
        exams_dir, "高一第二学期", "英语周测",
        name="英语周测", subject="外语",
    )
    cfg = load_config(
        str(
            _write_global(
                tmp_path,
                exams_dir=str(exams_dir),
                subject_aliases={"外语": ["英语", "俄语", "日语"]},
            )
        )
    )
    assert cfg.exams[0].name == "高一下英语周测"  # 别名已存在，不重复加"外语"


def test_normalize_name_keeps_full_name(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(
        exams_dir, "高一第二学期", "周测",
        name="高一下地理周测", subject="地理",
    )
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))
    assert cfg.exams[0].name == "高一下地理周测"


def test_folder_defaults_to_global_input_dir(tmp_path):
    exams_dir = tmp_path / "exams"
    input_dir = tmp_path / "input"
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测", folder=None)
    cfg = load_config(
        str(
            _write_global(
                tmp_path, exams_dir=str(exams_dir), input_dir=str(input_dir)
            )
        )
    )
    assert cfg.exams[0].folder == str(input_dir)
    assert cfg.exams[0].full_path == str(input_dir / "周测.xlsx")


def test_effective_short_name_falls_back_to_full_name(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第二学期", "周测", name="周测")
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))
    exam = cfg.exams[0]
    assert exam.short_name is None
    assert exam.effective_short_name == "高一下地理周测"


def test_current_exam_int_loaded(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测")
    cfg = load_config(
        str(_write_global(tmp_path, exams_dir=str(exams_dir), current_exam=3))
    )
    assert cfg.current_exam == [3]


def test_current_exam_string_int_loaded(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测")
    cfg = load_config(
        str(_write_global(tmp_path, exams_dir=str(exams_dir), current_exam="2"))
    )
    assert cfg.current_exam == [2]


def test_current_exam_invalid_raises(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测")
    with pytest.raises(ValueError, match="current_exam"):
        load_config(
            str(_write_global(tmp_path, exams_dir=str(exams_dir), current_exam="abc"))
        )
    with pytest.raises(ValueError, match="current_exam"):
        load_config(
            str(_write_global(tmp_path, exams_dir=str(exams_dir), current_exam=1.5))
        )


def test_current_exam_empty_is_none(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测")
    cfg = load_config(
        str(_write_global(tmp_path, exams_dir=str(exams_dir), current_exam=""))
    )
    assert cfg.current_exam is None


def test_current_exam_list_loaded(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测")
    cfg = load_config(
        str(_write_global(tmp_path, exams_dir=str(exams_dir), current_exam=[1, 3]))
    )
    assert cfg.current_exam == [1, 3]
    cfg2 = load_config(
        str(_write_global(tmp_path, exams_dir=str(exams_dir), current_exam="1,3"))
    )
    assert cfg2.current_exam == [1, 3]


def test_normalize_name_dedup_grade(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(
        exams_dir, "高一第二学期", "周测",
        name="高一限时练一", subject="地理",
    )
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))
    # 考试名已含年级"高一"，学期简写"高一下"不再重复年级
    assert cfg.exams[0].name == "高一下地理限时练一"


def test_objective_question_count_parsed(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(
        exams_dir, "高一第一学期", "周测",
        name="周测", objective_question_count=25,
    )
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))
    assert cfg.exams[0].objective_question_count == 25


def test_objective_question_count_invalid_raises(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(
        exams_dir, "高一第一学期", "周测",
        name="周测", objective_question_count="abc",
    )
    with pytest.raises(ValueError, match="objective_question_count"):
        load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))


def test_unknown_global_key_raises(tmp_path):
    cfg_path = _write_global(tmp_path, nope=1)
    with pytest.raises(ValueError, match="未知配置键"):
        load_config(str(cfg_path))


def test_unknown_exam_key_raises(tmp_path):
    exams_dir = tmp_path / "exams"
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测", ful_score=100)
    with pytest.raises(ValueError, match="未知字段"):
        load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))


def test_pass_ratio_out_of_range(tmp_path):
    cfg_path = _write_global(tmp_path, analysis={"pass_ratio": 1.5})
    with pytest.raises(ValueError, match="pass_ratio"):
        load_config(str(cfg_path))


def test_underscore_template_ignored(tmp_path):
    exams_dir = tmp_path / "exams"
    exams_dir.mkdir(exist_ok=True)
    (exams_dir / "_template.yaml").write_text("path: x\n", encoding="utf-8")
    _write_exam(exams_dir, "高一第一学期", "周测", name="周测")
    cfg = load_config(str(_write_global(tmp_path, exams_dir=str(exams_dir))))
    assert len(cfg.exams) == 1


def test_missing_config_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(str(tmp_path / "nope.yaml"))
