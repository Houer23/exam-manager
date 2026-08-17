# 插件系统

程序启动时会扫描 `plugins/` 目录加载插件。每个插件是一个独立子目录，包含：

- `plugin.yaml`：清单（元数据）
- `plugin.py`：入口，须提供 `register(plugin_ctx)` 函数

## 目录结构

```text
plugins/
└── my_format/
    ├── plugin.yaml
    └── plugin.py
```

## plugin.yaml

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `name` | 是 | 插件唯一名（默认取目录名），也用作白名单键 |
| `version` | 否 | 版本号，默认 `0.1.0` |
| `description` | 否 | 描述 |
| `enabled` | 否 | 是否启用，默认 `true` |
| `priority` | 否 | 加载顺序（升序），默认 `10`；影响格式自动识别时的探测顺序 |

## plugin.py

入口函数接收 `PluginContext`，可注册成绩单格式适配器与生命周期钩子：

```python
from grade_analyzer.adapters.base import BaseAdapter
from grade_analyzer.config import ExamConfig
from grade_analyzer.plugins import PluginContext


class MyAdapter(BaseAdapter):
    format_name = "my_format"

    @classmethod
    def detect(cls, df):
        return "我的表头" in {str(v) for v in df.iloc[0].tolist()}

    def parse(self, exam: ExamConfig):
        # 返回 (科目总分表, 小题明细表)，字段约定见 BaseAdapter.parse 文档
        raise NotImplementedError


def register(ctx: PluginContext) -> None:
    ctx.register_adapter(MyAdapter())
    ctx.register_hook("on_run_start", on_run_start)


def on_run_start(config):
    print(f"[插件示例] run 开始：{config.current_semester}")
```

插件也可注册可独立调用的批处理任务（`register_task`）：

```python
def register(ctx: PluginContext) -> None:
    ctx.register_task("my_task", run_my_task, description="我的批处理任务")


def run_my_task(config_path, plugin_config, input_dir, output_dir):
    # 由 CLI 以关键字参数调用：python -m grade_analyzer.cli task my_task ...
    return 0
```

## 任务（CLI）

```bash
python -m grade_analyzer.cli task <任务名> [--plugin-config 路径] [--input-dir 路径] [--output-dir 路径]
python -m grade_analyzer.cli task --list   # 列出全部已注册任务
```

- 任务回调以关键字参数接收 `config_path`、`plugin_config`、`input_dir`、`output_dir`；
- 未指定任务名或使用 `--list` 时列出已注册任务。

## 多模块插件

插件以 `grade_analyzer_plugins.<插件名>.plugin` 形式加载，插件内可用相对导入引用
兄弟模块（如 `from .analyze import run`）。插件名须为合法 Python 标识符。

## 生命周期钩子

| 阶段 | 回调关键字参数 |
| --- | --- |
| `on_run_start` | `config` |
| `on_exam_parsed` | `exam`, `score`, `questions`, `config` |
| `on_exam_finished` | `exam`, `score`, `questions` |
| `on_run_finished` | `config`, `events` |

## 启用方式

`config/config.yaml` 的 `plugins` 键：

- 留空/缺省：自动发现并加载全部 `enabled: true` 的插件；
- 列表（如 `plugins: [my_format]`）：白名单，只加载列出的插件；
- `[]`：禁用全部插件。

## 注意

- 插件代码在本地以完全权限执行，只应加载可信来源的插件。
- 新增格式后，`check` 的提示与 `exam add/update --format` 会自动列出已注册格式。
- 同名格式重复注册会报错并指出来源。
