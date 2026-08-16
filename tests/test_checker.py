"""check 命令的单元测试。"""

import yaml
import pandas as pd

from grade_analyzer.checker import (
    _extract_class_samples,
    _metadata_coverage_checks,
    run_check,
)
from grade_analyzer.config import load_config
from grade_analyzer.config import AnalysisConfig, ClassInfo, ExamConfig, TeacherMap
import pandas as pd


def test_extract_class_samples():
    df = pd.DataFrame(
        [
            ["标题", None],
            ["班级", "其他"],
            ["高一(10)", "x"],
            ["高一(10)", "y"],
            ["高一(11)", "z"],
        ]
    )
    assert _extract_class_samples(df) == ["高一(10)", "高一(11)"]


def test_extract_class_samples_not_found():
    df = pd.DataFrame([["a", "b"], [1, 2]])
    assert _extract_class_samples(df) == []


def test_run_check_real_config(capsys):
    cfg = load_config()
    problems = run_check(cfg)
    out = capsys.readouterr().out
    for exam in cfg.exams:
        if exam.name:
            assert exam.name in out
    assert "地理" in out
    assert "汇总" in out
    assert problems == 0


def test_run_check_missing_file_reports_problem(tmp_path, capsys):
    exams_dir = tmp_path / "exams"
    (exams_dir / "高一第一学期").mkdir(parents=True)
    exam_file = exams_dir / "高一第一学期" / "测试.yaml"
    exam_file.write_text(
        "name: 测试\nfolder: data/input\nfile: 不存在.xlsx\nsubject: 地理\n",
        encoding="utf-8",
    )
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "subjects": ["语文", "数学", "外语", "物理", "化学", "生物", "政治", "历史", "地理", "技术"],
                "exams_dir": str(exams_dir),
                "output_dir": str(tmp_path / "out"),
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    problems = run_check(load_config(str(cfg_path)))
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert problems == 1


def test_run_check_name_extracted_from_filename(tmp_path, capsys):
    exams_dir = tmp_path / "exams"
    (exams_dir / "高一第一学期").mkdir(parents=True)
    exam_file = exams_dir / "高一第一学期" / "测试.yaml"
    exam_file.write_text(
        "name: ''\n"
        "folder: data/input/测试样例\n"
        "file: 【教学班报告--高一下地理限时练一】所有班级学生小题得分明细.xlsx\n"
        "subject: 地理\n",
        encoding="utf-8",
    )
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "subjects": ["语文", "数学", "外语", "物理", "化学", "生物", "政治", "历史", "地理", "技术"],
                "exams_dir": str(exams_dir),
                "output_dir": str(tmp_path / "out"),
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    problems = run_check(load_config(str(cfg_path)))
    out = capsys.readouterr().out
    assert "文件名提取" in out
    assert "留空，使用考试全称" in out  # short_name 为空不 FAIL，用全称
    assert problems == 0


def test_run_check_missing_subject_reports_problem(tmp_path, capsys):
    exams_dir = tmp_path / "exams"
    (exams_dir / "高一第一学期").mkdir(parents=True)
    exam_file = exams_dir / "高一第一学期" / "测试.yaml"
    exam_file.write_text(
        "name: 测试\n"
        "folder: data/input/测试样例\n"
        "file: 【教学班报告--高一下地理限时练一】所有班级学生小题得分明细.xlsx\n"
        "subject: ''\n",
        encoding="utf-8",
    )
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "subjects": ["语文", "数学", "外语", "物理", "化学", "生物", "政治", "历史", "地理", "技术"],
                "exams_dir": str(exams_dir),
                "output_dir": str(tmp_path / "out"),
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    problems = run_check(load_config(str(cfg_path)))
    out = capsys.readouterr().out
    assert "科目（subject）必填" in out
    assert "FAIL" in out
    assert problems == 1


def test_metadata_coverage_checks():
    cfg = AnalysisConfig()
    cfg.class_infos = {
        ("高一第二学期", "高一10班"): ClassInfo(level="A", course="物化地")
    }
    cfg.teacher_maps = {
        ("高一第二学期", "地理"): TeacherMap(
            subject="地理",
            teacher_count=1,
            teacher_names={"A": "柯老师"},
            class_teachers={"高一10班": "A", "高一11班": "A"},
        )
    }
    exam = ExamConfig(
        name="测试", semester="高一第二学期", subject="地理"
    )
    score = pd.DataFrame(
        {
            "class_name": ["高一10班", "高一11班", "高一12班"],
            "total_score": [70.0, 80.0, 90.0],
        }
    )
    checks = _metadata_coverage_checks(score, exam, cfg)
    texts = [d for _, d in checks]
    assert any("未配置教师" in t for t in texts)  # 高一12班有成绩但未配置
    assert any("level/course" in t for t in texts)  # 高一11班未配置班级层次
