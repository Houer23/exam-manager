"""学生成绩单处理与分析工具。

输入长表成绩单，输出 Excel 多 sheet 汇总报告，
支持单场统计与多场次趋势分析。
"""

import warnings

# 忽略 openpyxl 读取无默认样式工作簿时的提示（数据文件常见，属预期情况）
warnings.filterwarnings(
    "ignore",
    message=r"Workbook contains no default style.*",
    category=UserWarning,
    module=r"openpyxl\.styles\.stylesheet",
)

__version__ = "0.1.0"
