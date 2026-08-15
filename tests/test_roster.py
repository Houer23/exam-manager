"""名单清洗与核对的单元测试。"""

import os
import time

import pandas as pd

from grade_analyzer.config import AnalysisConfig, ExamConfig, OutputConfig
from grade_analyzer.roster import (
    clean_roster,
    load_roster,
    normalize_roster,
    _selects_subject,
    verify_exam,
)


def _raw_roster_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "姓名": ["张一", "李二", "王三", "赵四", "钱五", "孙六"],
            "考号": [
                "250907010001",
                "250907010002",
                "250907010003",
                "bad123",
                "250907010005",
                "",
            ],
            "性别": ["男", "女", "男", "男", "女", "女"],
            "七选三": ["物化地", "政史地", "物化生", "物化地", "政史地", "物化生"],
            "班级": ["高一(10)", "高一年级11班", "12", "", "", "高一(10)"],
        }
    )


def test_clean_roster():
    config = AnalysisConfig(default_grade="高一")
    roster_df, issues_df = clean_roster(_raw_roster_df(), config)
    assert len(roster_df) == 3
    assert roster_df["班级"].tolist() == ["高一10班", "高一11班", "高一12班"]
    assert roster_df["七选三"].tolist() == ["物化地", "政史地", "物化生"]
    assert len(issues_df) == 3
    types = set(issues_df["问题类型"])
    assert "考号异常" in types
    assert "班级缺失" in types


def test_normalize_and_reuse_freshness(tmp_path):
    config = AnalysisConfig(
        default_grade="高一",
        roster_dir=str(tmp_path / "roster"),
        output=OutputConfig(dir=str(tmp_path / "out")),
    )
    roster_dir = tmp_path / "roster"
    roster_dir.mkdir()
    _raw_roster_df().to_excel(roster_dir / "高一第二学期.xlsx", index=False)

    roster_df, _ = normalize_roster(config, "高一第二学期")
    assert len(roster_df) == 3
    norm_path = roster_dir / "高一第二学期_normalized.xlsx"
    assert norm_path.is_file()
    sheets = pd.ExcelFile(norm_path).sheet_names
    assert sheets == ["名单", "异常"]  # 异常并入规范化文件 sheet
    assert not (tmp_path / "out" / "quality" / "名单清洗异常_高一第二学期.csv").is_file()

    loaded, _ = load_roster(config, "高一第二学期")
    assert len(loaded) == 3
    norm_mtime = norm_path.stat().st_mtime

    time.sleep(0.05)
    future = time.time() + 10
    os.utime(roster_dir / "高一第二学期.xlsx", (future, future))
    load_roster(config, "高一第二学期")
    assert norm_path.stat().st_mtime > norm_mtime  # 过期后重新生成


def _score_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "student_id": [
                "250907010001",
                "250907010099",
                "250907010002",
                "250907010016",
            ],
            "name": ["张三", "", "李二", ""],
            "class_name": ["高一10班", "高一10班", "高一11班", "高一16班"],
            "total_score": [80.0, 90.0, 70.0, 60.0],
        }
    )


def test_verify_exam(tmp_path):
    roster_dir = tmp_path / "roster"
    roster_dir.mkdir()
    _raw_roster_df().to_excel(roster_dir / "高一第二学期.xlsx", index=False)
    config = AnalysisConfig(
        default_grade="高一",
        roster_dir=str(roster_dir),
        output=OutputConfig(dir=str(tmp_path / "out")),
    )
    exam = ExamConfig(name="测试", semester="高一第二学期", subject="地理")
    issues = verify_exam(exam, _score_df(), config)

    statuses = set(issues["状态"])
    assert "名单外" in statuses  # 250907010099
    assert "姓名不符" in statuses  # 张一 vs 张三
    assert "高一12班" not in set(issues["班级"])  # 王三 物化生，未选地理，过滤
    assert "高一16班" not in set(issues["班级"])  # 名单缺失班级，跳过
    out = tmp_path / "out" / "quality" / "名单核对_测试.csv"
    assert out.is_file()


def test_verify_exam_without_filter(tmp_path):
    roster_dir = tmp_path / "roster"
    roster_dir.mkdir()
    _raw_roster_df().to_excel(roster_dir / "高一第二学期.xlsx", index=False)
    config = AnalysisConfig(
        default_grade="高一",
        roster_dir=str(roster_dir),
        output=OutputConfig(dir=str(tmp_path / "out")),
    )
    exam = ExamConfig(
        name="测试",
        semester="高一第二学期",
        subject="地理",
        filter_by_selection=False,
    )
    issues = verify_exam(exam, _score_df(), config)
    assert "高一12班" in set(issues["班级"])  # 不过滤 → 全部班级核对
    assert "高一16班" not in set(issues["班级"])  # 名单缺失班级仍跳过


def test_selects_subject():
    assert _selects_subject("物化地", "地理") is True
    assert _selects_subject("政史地", "地理") is True
    assert _selects_subject("物化生", "地理") is False
    assert _selects_subject("政历地", "历史") is True  # 历 别名
    assert _selects_subject("政史地", "历史") is True  # 史 简称
    assert _selects_subject("物化生", "语文") is True  # 非选考科目不过滤
