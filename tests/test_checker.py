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


def _check_cfg(tmp_path, folder="data/input/测试样例", file=None, name="高一下地理限时练一"):
    exams_dir = tmp_path / "exams"
    (exams_dir / "高一第二学期").mkdir(parents=True)
    (exams_dir / "高一第二学期" / "周测.yaml").write_text(
        f"name: {name}\n"
        f"folder: {folder}\n"
        f"file: {file or '【教学班报告--高一下地理限时练一】所有班级学生小题得分明细.xlsx'}\n"
        f"subject: 地理\n"
        f"short_name: 限时练一\n",
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
    return str(cfg_path)


def test_check_mark_skips_unchanged(tmp_path, capsys):
    from grade_analyzer.config import load_config

    cfg_path = _check_cfg(tmp_path)
    assert run_check(load_config(cfg_path)) == 0
    out1 = capsys.readouterr().out
    assert "=== 检查: 高一下地理限时练一 ===" in out1

    assert run_check(load_config(cfg_path)) == 0
    out2 = capsys.readouterr().out
    assert "[跳过] 高一下地理限时练一" in out2
    assert "1 场跳过" in out2
    assert "=== 检查:" not in out2
    mark = tmp_path / "out" / "quality" / "checked" / "高一下地理限时练一.yaml"
    assert mark.is_file()


def test_check_force_rechecks(tmp_path, capsys):
    from grade_analyzer.config import load_config

    cfg_path = _check_cfg(tmp_path)
    run_check(load_config(cfg_path))
    capsys.readouterr()
    run_check(load_config(cfg_path), force=True)
    out = capsys.readouterr().out
    assert "=== 检查: 高一下地理限时练一 ===" in out
    assert "[跳过]" not in out


def test_check_rechecks_when_raw_changed(tmp_path, capsys):
    import os
    import time

    from grade_analyzer.config import load_config

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw_file = raw_dir / "测试.xlsx"
    raw_file.write_text("not excel", encoding="utf-8")
    cfg_path = _check_cfg(
        tmp_path, folder=str(raw_dir), file="测试.xlsx", name="高一下地理测试"
    )

    run_check(load_config(cfg_path))
    capsys.readouterr()
    # 原始文件时间戳变化 -> 重新完整检查
    later = time.time() + 2
    os.utime(raw_file, (later, later))
    run_check(load_config(cfg_path))
    out = capsys.readouterr().out
    assert "=== 检查: 高一下地理测试 ===" in out
    assert "[跳过]" not in out


def test_run_check_exam_subset(tmp_path, capsys):
    from grade_analyzer.config import load_config

    cfg_path = _check_cfg(tmp_path)
    cfg = load_config(cfg_path)
    run_check(cfg, exams=[cfg.exams[0]], force=True)
    out = capsys.readouterr().out
    assert "=== 检查: 高一下地理限时练一 ===" in out
    assert "1 场检查（0 场跳过）" in out


def test_cli_check_exam_parses():
    from grade_analyzer.cli import build_parser

    args = build_parser().parse_args(["check", "--exam", "1,3", "--force"])
    assert args.exam == "1,3"
    assert args.force is True
