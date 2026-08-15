"""运行信息落盘（run-info）。

每次 run 自动生成带时间戳的运行目录：
  output/run-info/<时间戳>/{配置快照.yaml, 考试列表.csv, 运行日志.txt}
并在 output/run-info/latest/ 保留最近一次的固定副本。
"""

from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from .config import AnalysisConfig
from .outputs import type_dir


def config_snapshot(config: AnalysisConfig) -> dict:
    """生成本次运行的配置快照（全局配置 + 考试条目 + 班级/学科配置）。"""
    return {
        "全局配置": {
            "当前学期": config.current_semester,
            "当前场次": config.current_exam,
            "默认学校": config.default_school,
            "默认年级": config.default_grade,
            "及格线得分率": config.pass_ratio,
            "优秀线得分率": config.excellent_ratio,
            "分数段上界": config.score_bands,
            "缺考策略": config.absent_strategy,
            "规范表目录": config.parsed_dir,
            "名单目录": config.roster_dir,
            "输出目录": config.output.dir,
            "科目满分默认": {
                subject: {
                    "满分": d.full_score,
                    "客观满分": d.objective_full_score,
                    "主观满分": d.subjective_full_score,
                }
                for subject, d in config.subject_defaults.items()
            },
        },
        "考试条目": [
            {
                "名称": e.name,
                "学期": e.semester,
                "考试类型": e.type,
                "格式": e.format,
                "科目": e.subject,
                "日期": e.date,
                "总分满分": e.full_score,
                "客观满分": e.objective_full_score,
                "主观满分": e.subjective_full_score,
                "默认年级": e.default_grade,
                "按选课过滤": e.filter_by_selection,
                "文件夹": e.folder,
                "文件": e.file,
            }
            for e in config.exams
        ],
        "班级配置": {
            f"{semester}|{cls}": {"level": info.level, "course": info.course}
            for (semester, cls), info in config.class_infos.items()
        },
        "学科配置": {
            f"{semester}|{subject}": {
                "教师数": tm.teacher_count,
                "教师": tm.teacher_names,
                "班级分配": tm.class_teachers,
            }
            for (semester, subject), tm in config.teacher_maps.items()
        },
    }


def exam_list_df(config: AnalysisConfig) -> pd.DataFrame:
    """生成考试列表（参与本次运行的考试条目）。"""
    rows = [
        {
            "考试名称": e.name,
            "学期": e.semester,
            "考试类型": e.type,
            "格式": e.format,
            "科目": e.subject,
            "日期": e.date,
            "总分满分": e.full_score,
            "客观满分": e.objective_full_score,
            "主观满分": e.subjective_full_score,
            "按选课过滤": e.filter_by_selection,
            "成绩文件": e.full_path,
        }
        for e in config.exams
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "考试名称", "学期", "考试类型", "格式", "科目", "日期",
            "总分满分", "客观满分", "主观满分", "按选课过滤", "成绩文件",
        ],
    )


def write_run_info(
    config: AnalysisConfig, events: list[tuple[str, str, str]]
) -> Path:
    """写入配置快照、考试列表、运行日志，返回运行目录。"""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = type_dir(config.output, "run-info")
    run_dir = base / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "配置快照.yaml").write_text(
        yaml.safe_dump(config_snapshot(config), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    exam_list_df(config).to_csv(
        run_dir / "考试列表.csv", index=False, encoding="utf-8-sig"
    )
    lines = [f"[{t}] {stage} {msg}" for t, stage, msg in events]
    (run_dir / "运行日志.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    latest = base / "latest"
    if latest.exists():
        shutil.rmtree(latest)
    shutil.copytree(run_dir, latest)
    return run_dir
