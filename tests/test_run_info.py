"""run-info 运行信息落盘的单元测试。"""

import yaml

from grade_analyzer.config import AnalysisConfig, ExamConfig, OutputConfig
from grade_analyzer.run_info import config_snapshot, exam_list_df, write_run_info


def test_config_snapshot_and_exam_list():
    config = AnalysisConfig(
        current_semester="高一第二学期",
        default_school="示例一中",
        exams=[ExamConfig(name="测试", semester="高一第二学期", subject="地理")],
    )
    snapshot = config_snapshot(config)
    assert snapshot["全局配置"]["当前学期"] == "高一第二学期"
    assert snapshot["考试条目"][0]["科目"] == "地理"
    df = exam_list_df(config)
    assert df["考试名称"].tolist() == ["测试"]
    assert "按选课过滤" in df.columns


def test_write_run_info(tmp_path):
    config = AnalysisConfig(output=OutputConfig(dir=str(tmp_path / "out")))
    events = [("12:00:00", "启动", "run 开始"), ("12:00:01", "完成", "总耗时 1.0s")]
    run_dir = write_run_info(config, events)
    assert run_dir.name.startswith("20")
    assert (run_dir / "配置快照.yaml").is_file()
    assert (run_dir / "考试列表.csv").is_file()
    assert (run_dir / "运行日志.txt").is_file()
    snapshot = yaml.safe_load((run_dir / "配置快照.yaml").read_text(encoding="utf-8"))
    assert "全局配置" in snapshot
    latest = tmp_path / "out" / "run-info" / "latest"
    assert (latest / "运行日志.txt").is_file()
