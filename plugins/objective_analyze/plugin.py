"""客观题得分明细汇总与得分率距平分析插件。"""

from __future__ import annotations

from grade_analyzer.plugins import PluginContext

from .analyze import run


def register(ctx: PluginContext) -> None:
    """注册批处理任务 objective_analyze。"""
    ctx.register_task(
        "objective_analyze",
        run,
        description="客观题得分明细汇总与得分率距平分析",
    )
