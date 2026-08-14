"""适配器注册表：数据格式 -> 适配器实例。"""

from __future__ import annotations

import pandas as pd

from .base import BaseAdapter
from .joint import JointAdapter
from .weekly import WeeklyAdapter

_REGISTRY: dict[str, BaseAdapter] = {}


def register(adapter: BaseAdapter) -> None:
    """注册一个适配器。"""
    _REGISTRY[adapter.format_name] = adapter


def get_adapter(format_name: str) -> BaseAdapter:
    """按数据格式返回适配器，未注册时报错。"""
    if format_name not in _REGISTRY:
        raise ValueError(f"未注册的数据格式: {format_name}")
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
