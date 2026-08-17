"""插件系统：从 plugins/ 目录加载适配器与生命周期钩子。"""

from .api import (
    HOOKS,
    ON_EXAM_FINISHED,
    ON_EXAM_PARSED,
    ON_RUN_FINISHED,
    ON_RUN_START,
    PluginContext,
    PluginError,
    PluginManifest,
)
from .loader import PluginManager, fire_hook, load_plugins

__all__ = [
    "HOOKS",
    "ON_RUN_START",
    "ON_EXAM_PARSED",
    "ON_EXAM_FINISHED",
    "ON_RUN_FINISHED",
    "PluginContext",
    "PluginError",
    "PluginManifest",
    "PluginManager",
    "fire_hook",
    "load_plugins",
]
