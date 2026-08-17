"""适配器注册表：数据格式 -> 适配器实例。"""

from __future__ import annotations

import pandas as pd

from .base import BaseAdapter
from .joint import JointAdapter
from .weekly import WeeklyAdapter

_REGISTRY: dict[str, BaseAdapter] = {}
_SOURCES: dict[str, str] = {}


def register(adapter: BaseAdapter, source: str = "builtin") -> None:
    """注册一个适配器；同名格式重复注册时报错。"""
    name = adapter.format_name
    if not name:
        raise ValueError("适配器 format_name 不能为空")
    if name in _REGISTRY:
        raise ValueError(f"数据格式 {name!r} 已由 {_SOURCES[name]} 注册")
    _REGISTRY[name] = adapter
    _SOURCES[name] = source


def unregister(format_name: str) -> None:
    """注销一个已注册的格式（供测试/插件失败回滚使用）。"""
    _REGISTRY.pop(format_name, None)
    _SOURCES.pop(format_name, None)


def known_formats() -> list[str]:
    """返回已注册的全部格式名（按注册顺序）。"""
    return list(_REGISTRY)


def known_format_hint() -> str:
    """返回用于提示文案的格式列表，如 weekly/joint。"""
    return "/".join(known_formats())


def get_adapter(format_name: str) -> BaseAdapter:
    """按数据格式返回适配器，未注册时给出已注册格式列表。"""
    if format_name not in _REGISTRY:
        raise ValueError(
            f"未注册的数据格式: {format_name}（已注册: {known_format_hint()}）"
        )
    return _REGISTRY[format_name]


def auto_detect_format(df: pd.DataFrame) -> str | None:
    """按表头特征自动识别数据格式；无法识别返回 None。

    按注册顺序调用各适配器 detect()，返回首个命中的 format_name。
    """
    for adapter in _REGISTRY.values():
        if adapter.detect(df):
            return adapter.format_name
    return None


# 注册内置适配器
register(WeeklyAdapter())
register(JointAdapter())
