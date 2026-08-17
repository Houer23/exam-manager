"""插件公共 API：插件上下文、清单与钩子常量。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..adapters.base import BaseAdapter

#: 支持的生命周期钩子阶段
ON_RUN_START = "on_run_start"
ON_EXAM_PARSED = "on_exam_parsed"
ON_EXAM_FINISHED = "on_exam_finished"
ON_RUN_FINISHED = "on_run_finished"

#: 全部钩子阶段（各阶段回调关键字参数见 plugins/README.md）
HOOKS = (ON_RUN_START, ON_EXAM_PARSED, ON_EXAM_FINISHED, ON_RUN_FINISHED)


class PluginError(Exception):
    """插件加载/注册相关错误。"""


@dataclass
class PluginManifest:
    """插件清单（plugin.yaml）解析结果。"""

    name: str
    path: Path
    version: str = "0.1.0"
    description: str = ""
    enabled: bool = True
    priority: int = 10


class PluginContext:
    """插件入口 register(plugin_ctx) 中可用的注册句柄。"""

    def __init__(self, manifest: PluginManifest) -> None:
        self.manifest = manifest
        self._hooks: dict[str, list[tuple[str, Callable[..., Any]]]] = {
            stage: [] for stage in HOOKS
        }
        self._tasks: dict[str, tuple[str, Callable[..., Any], str]] = {}

    @property
    def name(self) -> str:
        """插件名（对应目录名 / plugin.yaml 的 name）。"""
        return self.manifest.name

    def register_adapter(self, adapter: BaseAdapter) -> None:
        """注册一个成绩单格式适配器。"""
        from ..adapters.registry import register

        register(adapter, source=self.name)

    def register_hook(self, stage: str, fn: Callable[..., Any]) -> None:
        """注册一个生命周期钩子回调。"""
        if stage not in self._hooks:
            raise PluginError(f"{self.name}: 未知钩子阶段 {stage!r}")
        self._hooks[stage].append((self.name, fn))

    def hooks(self, stage: str) -> list[tuple[str, Callable[..., Any]]]:
        """返回某阶段已注册的 (插件名, 回调) 列表（供加载器收集）。"""
        return list(self._hooks.get(stage, []))

    def register_task(
        self,
        task_name: str,
        fn: Callable[..., Any],
        description: str = "",
    ) -> None:
        """注册一个可独立调用的批处理任务（供 CLI task 子命令运行）。"""
        if not task_name or not task_name.isidentifier():
            raise PluginError(f"{self.name}: 任务名应为合法标识符，当前为 {task_name!r}")
        if not callable(fn):
            raise PluginError(f"{self.name}: 任务 {task_name!r} 的回调不可调用")
        self._tasks[task_name] = (self.name, fn, description)

    def tasks(self) -> dict[str, tuple[str, Callable[..., Any], str]]:
        """返回已注册任务 {任务名: (插件名, 回调, 描述)}（供加载器收集）。"""
        return dict(self._tasks)
