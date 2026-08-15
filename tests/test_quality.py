"""质量落盘的单元测试。"""

import pandas as pd

from grade_analyzer.config import AnalysisConfig, OutputConfig
from grade_analyzer.quality import write_check_reports, write_quality_excel


def test_write_quality_excel_multi_sheet(tmp_path):
    config = AnalysisConfig(output=OutputConfig(dir=str(tmp_path / "out")))
    sheets = {
        "期中": pd.DataFrame(
            {"考试名称": ["期中"], "考号": ["1"], "问题类型": ["超满分"], "说明": ["x"]}
        ),
        "期末": pd.DataFrame(
            columns=["考试名称", "考号", "问题类型", "说明"]
        ),
    }
    path = write_quality_excel(config, sheets)
    assert path is not None
    assert set(pd.ExcelFile(path).sheet_names) == {"期中", "期末"}


def test_write_check_reports(tmp_path):
    config = AnalysisConfig(output=OutputConfig(dir=str(tmp_path / "out")))
    checks = {
        "期中": [("文件", "PASS", "ok"), ("格式", "FAIL", "未知")],
        "期末": [("文件", "PASS", "ok")],
    }
    paths = write_check_reports(config, checks)
    assert len(paths) == 3  # 两场 + 汇总
    summary = pd.read_csv(
        tmp_path / "out" / "quality" / "check_汇总.csv", encoding="utf-8-sig"
    )
    assert summary.loc[summary["考试名称"] == "期中", "FAIL数"].iloc[0] == 1


def test_write_quality_excel_locked(tmp_path, capsys, monkeypatch):
    from grade_analyzer import quality as quality_mod

    def _boom(*args, **kwargs):
        raise PermissionError("locked")

    monkeypatch.setattr(quality_mod, "write_excel_report", _boom)
    config = AnalysisConfig(output=OutputConfig(dir=str(tmp_path / "out")))
    result = write_quality_excel(config, {"期中": pd.DataFrame({"考号": ["1"]})})
    assert result is None
    assert "写入失败" in capsys.readouterr().out
