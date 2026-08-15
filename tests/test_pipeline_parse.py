"""parse 流程的集成测试。"""

import pandas as pd
import yaml

from grade_analyzer.config import load_config
from grade_analyzer.pipeline import parse_exams


def _setup(tmp_path, parsed_dir, out_dir=None, roster_dir=None):
    exams_dir = tmp_path / "exams"
    (exams_dir / "高一第二学期").mkdir(parents=True)
    (exams_dir / "高一第二学期" / "周测.yaml").write_text(
        "name: 周测\n"
        "format: weekly\n"
        "folder: data/input/测试样例\n"
        "file: 【教学班报告--高一下地理限时练一】所有班级学生小题得分明细.xlsx\n"
        "subject: 地理\n"
        "full_score: 100\n"
        "objective_full_score: 85\n"
        "subjective_full_score: 15\n",
        encoding="utf-8",
    )
    cfg = tmp_path / "config.yaml"
    data = {
        "subjects": ["语文", "数学", "外语", "物理", "化学", "生物", "政治", "历史", "地理", "技术"],
        "exams_dir": str(exams_dir),
        "parsed_dir": str(parsed_dir),
        "default_school": "青田中学",
        "output": {"dir": str(out_dir or tmp_path / "out"), "excel_name": "成绩分析汇总.xlsx"},
    }
    if roster_dir:
        data["roster_dir"] = str(roster_dir)
    cfg.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return str(cfg)


def test_run_pipeline_verify_roster(tmp_path, capsys):
    from grade_analyzer.pipeline import run_pipeline

    parsed = tmp_path / "parsed"
    out = tmp_path / "out"
    roster_dir = tmp_path / "roster"
    roster_dir.mkdir()
    pd.DataFrame(
        {
            "姓名": ["柯一"],
            "考号": ["250907010858"],
            "性别": ["男"],
            "七选三": ["物化地"],
            "班级": ["高一年级13班"],
        }
    ).to_excel(roster_dir / "高一第二学期.xlsx", index=False)

    cfg_path = _setup(tmp_path, parsed, out, str(roster_dir))
    run_pipeline(cfg_path, verify_roster=True)
    out_text = capsys.readouterr().out
    assert "[名单核对]" in out_text
    assert (out / "quality" / "名单核对_高一下周测.csv").is_file()


def test_parse_exams_writes_and_reuses(tmp_path, capsys):
    parsed = tmp_path / "parsed"
    cfg_path = _setup(tmp_path, parsed, tmp_path / "out")

    parse_exams(cfg_path)
    out1 = capsys.readouterr().out
    assert "[完成]" in out1
    assert "高一下周测" in out1

    score_path = parsed / "高一第二学期" / "高一下周测" / "score_summary.csv"
    question_path = parsed / "高一第二学期" / "高一下周测" / "question_detail.csv"
    assert score_path.is_file()
    assert question_path.is_file()
    score_df = pd.read_csv(score_path, encoding="utf-8-sig")
    assert len(score_df) > 400
    assert (score_df["school"] == "青田中学").all()
    assert (score_df["grade"] == "高一").all()
    assert (score_df["class_name"] == "高一13班").any()
    assert {"班次", "校次"} <= set(score_df.columns)
    assert score_df["班次"].dropna().min() == 1.0
    assert {"单选分", "多选分", "单选满分", "多选满分"} <= set(score_df.columns)
    assert {"class_level", "course", "teacher"} <= set(score_df.columns)
    assert "exam_date" in score_df.columns
    assert set(score_df["class_level"].dropna().unique()) <= {"A", "B"}
    assert score_df["单选满分"].iloc[0] == 60.0  # 周测：3 × 20
    assert score_df["多选满分"].iloc[0] == 25.0  # 周测：5 × 5
    assert len(score_df) * 29 == len(
        pd.read_csv(question_path, encoding="utf-8-sig")
    )
    q_df = pd.read_csv(question_path, encoding="utf-8-sig")
    type_counts = q_df["question_type"].value_counts().to_dict()
    assert type_counts.get("单选") == len(score_df) * 20
    assert type_counts.get("多选") == len(score_df) * 5
    assert type_counts.get("主观") == len(score_df) * 4

    parse_exams(cfg_path)
    assert "[复用]" in capsys.readouterr().out

    parse_exams(cfg_path, reparse=True)
    assert "[复用]" not in capsys.readouterr().out


def test_run_pipeline_writes_report_and_statistics(tmp_path, capsys):
    import openpyxl
    from grade_analyzer.pipeline import run_pipeline

    parsed = tmp_path / "parsed"
    out = tmp_path / "out"
    cfg_path = _setup(tmp_path, parsed, out)

    run_pipeline(cfg_path)
    out_text = capsys.readouterr().out
    assert "[统计]" in out_text
    assert "[报告]" in out_text

    report = out / "reports" / "高一第二学期" / "成绩分析汇总.xlsx"
    assert report.is_file()
    stat = out / "statistics" / "高一第二学期" / "高一下周测.xlsx"
    assert stat.is_file()
    sheets = pd.read_excel(stat, sheet_name=None)
    assert set(sheets) == {"科目统计", "分数段分布", "个人排名", "班级对比", "教师对比"}
    assert (out / "merged" / "merged_long.csv").is_file()
    summary = parsed / "高一第二学期" / "高一下周测" / "高一下周测_柯_班级成绩汇总.xlsx"
    assert summary.is_file()

    wb = openpyxl.load_workbook(stat)
    ws = wb["科目统计"]
    header = {cell.value: cell.column for cell in ws[1] if cell.value}
    assert ws.cell(row=2, column=header["平均分"]).number_format == "0.0"
    assert ws.cell(row=2, column=header["及格率"]).number_format == "0.00%"
