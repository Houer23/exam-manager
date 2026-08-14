"""格式适配器包。

每个原始成绩单格式对应一个适配器，
把原始文件解析为统一的规范表（科目总分表 + 小题明细表）。
"""

from .base import BaseAdapter
from .registry import get_adapter

__all__ = ["BaseAdapter", "get_adapter"]
