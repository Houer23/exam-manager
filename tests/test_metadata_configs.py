"""班级/学科元数据配置的单元测试。"""

import pytest

from grade_analyzer.config import (
    load_class_configs,
    load_subject_configs,
)


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_load_class_configs_valid(tmp_path):
    _write(
        tmp_path,
        "高一第二学期.yaml",
        "高一10班: {level: A, course: 物化地}\n"
        "高一11班: {level: B, course: 政史地}\n",
    )
    cfg = load_class_configs(str(tmp_path))
    info = cfg[("高一第二学期", "高一10班")]
    assert info.level == "A"
    assert info.course == "物化地"
    assert cfg[("高一第二学期", "高一11班")].level == "B"


def test_load_class_configs_invalid_level(tmp_path):
    _write(tmp_path, "高一第二学期.yaml", "高一10班: {level: C}\n")
    with pytest.raises(ValueError, match="level"):
        load_class_configs(str(tmp_path))


def test_load_class_configs_unknown_key(tmp_path):
    _write(tmp_path, "高一第二学期.yaml", "高一10班: {level: A, extra: 1}\n")
    with pytest.raises(ValueError, match="未知键"):
        load_class_configs(str(tmp_path))


def test_load_subject_configs_valid(tmp_path):
    _write(
        tmp_path,
        "高一第二学期_地理.yaml",
        "subject: 地理\n"
        "teacher_count: 2\n"
        "teacher_names:\n"
        "  A: 张老师\n"
        "  B: 李老师\n"
        "class_teachers:\n"
        "  高一10班: A\n"
        "  高一11班: B\n",
    )
    cfg = load_subject_configs(str(tmp_path))
    tm = cfg[("高一第二学期", "地理")]
    assert tm.teacher_for("高一10班") == "张老师"
    assert tm.teacher_for("高一11班") == "李老师"
    assert tm.teacher_for("高一12班") is None


def test_load_subject_configs_count_mismatch(tmp_path):
    _write(
        tmp_path,
        "高一第二学期_地理.yaml",
        "teacher_count: 3\n"
        "teacher_names:\n"
        "  A: 张老师\n"
        "  B: 李老师\n"
        "class_teachers:\n"
        "  高一10班: A\n",
    )
    with pytest.raises(ValueError, match="代号"):
        load_subject_configs(str(tmp_path))


def test_load_subject_configs_unknown_code(tmp_path):
    _write(
        tmp_path,
        "高一第二学期_地理.yaml",
        "teacher_count: 1\n"
        "teacher_names:\n"
        "  A: 张老师\n"
        "class_teachers:\n"
        "  高一10班: C\n",
    )
    with pytest.raises(ValueError, match="teacher_names"):
        load_subject_configs(str(tmp_path))


def test_load_subject_configs_bad_filename(tmp_path):
    _write(tmp_path, "无下划线.yaml", "subject: 地理\n")
    with pytest.raises(ValueError, match="文件名"):
        load_subject_configs(str(tmp_path))


def test_underscore_files_ignored(tmp_path):
    _write(tmp_path, "_template.yaml", "高一10班: {level: A}\n")
    assert load_class_configs(str(tmp_path)) == {}
