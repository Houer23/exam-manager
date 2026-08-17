"""插件发现与加载。

扫描 plugins/ 目录，每个子目录视为一个插件：
- plugin.yaml：清单（name/version/description/enabled/priority）
- plugin.py：入口，须提供 register(plugin_ctx) 函数

加载策略（config/config.yaml 的 plugins 键）：
- 缺省 / null：自动发现并加载全部 enabled: true 的插件
- 列表：只加载列表中出现的插件（白名单）
- []：禁用全部插件
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Callable

import yaml

from .api import HOOKS, PluginContext, PluginError, PluginManifest

_DEFAULT_PLUGINS_DIR = "plugins"
_MANIFEST_KEYS = {"name", "version", "description", "enabled", "priority"}
_FALSE_STRINGS = {"", "false", "0", "no", "否"}


class PluginManager:
    """插件管理器：负责发现、加载与钩子分发。"""

    def __init__(
        self,
        config_path: str = "config/config.yaml",
        plugins_dir: str = _DEFAULT_PLUGINS_DIR,
    ) -> None:
        self.config_path = config_path
        self.plugins_dir = Path(plugins_dir)
        self._loaded = False
        self._manifests: list[PluginManifest] = []
        self._hooks: dict[str, list[tuple[str, Callable[..., Any]]]] = {
            stage: [] for stage in HOOKS
        }
        self._tasks: dict[str, tuple[str, Callable[..., Any], str]] = {}

    def load(self) -> list[PluginManifest]:
        """加载插件（幂等），返回已加载插件的清单列表。"""
        if self._loaded:
            return list(self._manifests)
        self._loaded = True
        allowlist = self._read_allowlist()
        for manifest in self._discover():
            if not manifest.enabled:
                continue
            if allowlist is not None and manifest.name not in allowlist:
                continue
            ctx = self._import_plugin(manifest)
            for stage in HOOKS:
                for source, fn in ctx.hooks(stage):
                    self._hooks[stage].append((source, fn))
            for task_name, (source, fn, description) in ctx.tasks().items():
                if task_name in self._tasks:
                    raise PluginError(
                        f"任务 {task_name!r} 已由 {self._tasks[task_name][0]} 注册"
                    )
                self._tasks[task_name] = (source, fn, description)
            self._manifests.append(manifest)
            print(f"[插件] 已加载 {manifest.name} v{manifest.version}")
        return list(self._manifests)

    def fire(self, stage: str, **payload: Any) -> None:
        """触发指定阶段的钩子（未加载插件时为空操作）。"""
        for _source, fn in self._hooks.get(stage, []):
            fn(**payload)

    def list_tasks(self) -> list[tuple[str, str, str]]:
        """返回已注册任务 [(任务名, 插件名, 描述)]，按任务名排序。"""
        return sorted(
            (name, source, description)
            for name, (source, _fn, description) in self._tasks.items()
        )

    def run_task(self, name: str, **kwargs: Any) -> Any:
        """运行指定任务，回调以关键字参数接收调用参数。"""
        if name not in self._tasks:
            registered = ", ".join(sorted(self._tasks))
            raise ValueError(f"未注册的任务: {name}（已注册: {registered}）")
        return self._tasks[name][1](**kwargs)

    def _read_allowlist(self) -> list[str] | None:
        """读取 config 的 plugins 键；文件缺失/未配置时返回 None（自动发现）。"""
        cfg_path = Path(self.config_path)
        if not cfg_path.is_file():
            return None
        with open(cfg_path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        if not isinstance(raw, dict) or "plugins" not in raw:
            return None
        value = raw["plugins"]
        if value is None:
            return None
        if not isinstance(value, list):
            raise PluginError(f"{cfg_path}: plugins 应为列表或留空")
        return [str(v) for v in value]

    def _discover(self) -> list[PluginManifest]:
        """扫描插件目录，返回按 (priority, name) 排序的清单。"""
        root = self.plugins_dir
        if not root.is_dir():
            return []
        manifests: list[PluginManifest] = []
        for d in sorted(root.iterdir()):
            if not d.is_dir() or d.name.startswith((".", "_")):
                continue
            yaml_path = d / "plugin.yaml"
            entry = d / "plugin.py"
            if not yaml_path.is_file() or not entry.is_file():
                continue
            with open(yaml_path, encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
            if not isinstance(raw, dict):
                raise PluginError(f"{yaml_path}: 插件清单应为映射")
            unknown = set(raw) - _MANIFEST_KEYS
            if unknown:
                raise PluginError(f"{yaml_path}: 未知字段 {sorted(unknown)}")
            name = str(raw.get("name") or d.name)
            if not name or name.startswith((".", "_")) or not name.isidentifier():
                raise PluginError(f"{yaml_path}: name 无效: {name!r}")
            version = str(raw.get("version") or "0.1.0")
            description = str(raw.get("description") or "")
            raw_enabled = raw.get("enabled", True)
            if isinstance(raw_enabled, str):
                enabled = raw_enabled.strip().lower() not in _FALSE_STRINGS
            else:
                enabled = bool(raw_enabled)
            try:
                priority = int(raw.get("priority", 10))
            except (TypeError, ValueError):
                raise PluginError(f"{yaml_path}: priority 应为整数")
            manifests.append(
                PluginManifest(
                    name=name,
                    path=d,
                    version=version,
                    description=description,
                    enabled=enabled,
                    priority=priority,
                )
            )
        return sorted(manifests, key=lambda m: (m.priority, m.name))

    @staticmethod
    def _import_plugin(manifest: PluginManifest) -> PluginContext:
        """把插件目录作为包导入，并调用其 register(plugin_ctx)。

        插件以 grade_analyzer_plugins.<插件名>.plugin 形式加载，
        插件内可用相对导入引用兄弟模块（如 from .analyze import run）。
        """
        entry = manifest.path / "plugin.py"
        root_name = "grade_analyzer_plugins"
        root = sys.modules.get(root_name)
        if root is None:
            root = types.ModuleType(root_name)
            root.__path__ = []
            sys.modules[root_name] = root

        pkg_name = f"{root_name}.{manifest.name}"
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(manifest.path)]
        sys.modules[pkg_name] = pkg

        module_name = f"{pkg_name}.plugin"
        spec = importlib.util.spec_from_file_location(module_name, entry)
        if spec is None or spec.loader is None:
            raise PluginError(f"{entry}: 无法创建插件模块")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        register_fn = getattr(module, "register", None)
        if not callable(register_fn):
            raise PluginError(f"{entry}: 缺少 register(plugin_ctx) 入口函数")
        ctx = PluginContext(manifest)
        register_fn(ctx)
        return ctx


_default_manager: PluginManager | None = None


def load_plugins(
    config_path: str = "config/config.yaml",
    plugins_dir: str = _DEFAULT_PLUGINS_DIR,
) -> list[PluginManifest]:
    """加载默认管理器中的插件（幂等），供 CLI 启动时调用。"""
    global _default_manager
    if _default_manager is None:
        _default_manager = PluginManager(
            config_path=config_path, plugins_dir=plugins_dir
        )
    return _default_manager.load()


def fire_hook(stage: str, **payload: Any) -> None:
    """触发默认管理器中注册的钩子（未初始化时为空操作）。"""
    if _default_manager is not None:
        _default_manager.fire(stage, **payload)


def list_tasks() -> list[tuple[str, str, str]]:
    """返回默认管理器中已注册的任务列表 [(任务名, 插件名, 描述)]。"""
    if _default_manager is None:
        return []
    return _default_manager.list_tasks()


def run_task(
    name: str,
    config_path: str = "config/config.yaml",
    plugin_config: str | None = None,
    input_dir: str | None = None,
    output_dir: str | None = None,
) -> Any:
    """运行默认管理器中的指定任务。"""
    global _default_manager
    if _default_manager is None:
        _default_manager = PluginManager(config_path=config_path)
        _default_manager.load()
    return _default_manager.run_task(
        name,
        config_path=config_path,
        plugin_config=plugin_config,
        input_dir=input_dir,
        output_dir=output_dir,
    )
