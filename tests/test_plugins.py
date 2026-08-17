"""插件加载器与注册机制测试。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from grade_analyzer.adapters.registry import (
    get_adapter,
    known_format_hint,
    known_formats,
    unregister,
)
from grade_analyzer.plugins import (
    ON_EXAM_PARSED,
    ON_RUN_START,
    PluginError,
    PluginManager,
    load_plugins,
)

ADAPTER_CODE = '''
import pandas as pd
from grade_analyzer.adapters.base import BaseAdapter
from grade_analyzer.config import ExamConfig


class TestFmtAdapter(BaseAdapter):
    format_name = "test_fmt"

    @classmethod
    def detect(cls, df: pd.DataFrame) -> bool:
        return "测试表头" in {str(v) for v in df.iloc[0].tolist()}

    def parse(self, exam: ExamConfig):
        return pd.DataFrame(), pd.DataFrame()


def register(ctx):
    ctx.register_adapter(TestFmtAdapter())
'''

HOOK_CODE = '''
def register(ctx):
    ctx.register_hook("on_run_start", on_start)
    ctx.register_hook("on_exam_parsed", on_parsed)


def on_start(config):
    with open(r"{path}", "a", encoding="utf-8") as fh:
        fh.write("start\\n")


def on_parsed(exam, score, questions, config):
    with open(r"{path}", "a", encoding="utf-8") as fh:
        fh.write("parsed\\n")
'''

TASK_CODE = '''
def register(ctx):
    ctx.register_task("my_task", run_task_impl, description="测试任务")


def run_task_impl(config_path=None, plugin_config=None, input_dir=None, output_dir=None):
    with open(r"{path}", "a", encoding="utf-8") as fh:
        fh.write(f"{{config_path}}|{{plugin_config}}|{{input_dir}}|{{output_dir}}\\n")
    return 7
'''


def _write_plugin(root: Path, name: str, manifest: str, code: str) -> Path:
    plugin_dir = root / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.yaml").write_text(manifest, encoding="utf-8")
    (plugin_dir / "plugin.py").write_text(code, encoding="utf-8")
    return plugin_dir


def _manager(tmp_path: Path, plugins_dir: Path, config_path: Path) -> PluginManager:
    return PluginManager(config_path=str(config_path), plugins_dir=str(plugins_dir))


def test_builtin_formats_present():
    formats = known_formats()
    assert "weekly" in formats
    assert "joint" in formats
    assert "weekly" in known_format_hint()


def test_manager_loads_adapter_plugin(tmp_path):
    _write_plugin(
        tmp_path,
        "test_fmt_plugin",
        "name: test_fmt_plugin\nversion: 0.2.0\ndescription: 测试\npriority: 5\n",
        ADAPTER_CODE,
    )
    manager = _manager(tmp_path, tmp_path, tmp_path / "missing.yaml")
    manifests = manager.load()
    assert [m.name for m in manifests] == ["test_fmt_plugin"]
    assert manifests[0].version == "0.2.0"
    try:
        adapter = get_adapter("test_fmt")
        assert adapter.format_name == "test_fmt"
        df = pd.DataFrame([["测试表头", "x"], ["v1", "v2"]])
        assert adapter.detect(df)
    finally:
        unregister("test_fmt")


def test_manager_load_is_idempotent(tmp_path):
    _write_plugin(tmp_path, "plug", "name: plug\n", ADAPTER_CODE)
    manager = _manager(tmp_path, tmp_path, tmp_path / "missing.yaml")
    assert manager.load() == manager.load()
    try:
        assert len(known_formats()) >= 1
    finally:
        unregister("test_fmt")


def test_disabled_plugin_skipped(tmp_path):
    _write_plugin(tmp_path, "off_plugin", "name: off_plugin\nenabled: false\n", ADAPTER_CODE)
    manager = _manager(tmp_path, tmp_path, tmp_path / "missing.yaml")
    assert manager.load() == []
    assert "test_fmt" not in known_formats()


def test_duplicate_format_rejected(tmp_path):
    _write_plugin(tmp_path, "dup_a", "name: dup_a\n", ADAPTER_CODE)
    _write_plugin(tmp_path, "dup_b", "name: dup_b\n", ADAPTER_CODE)
    manager = _manager(tmp_path, tmp_path, tmp_path / "missing.yaml")
    with pytest.raises(ValueError, match="已由"):
        manager.load()
    try:
        assert "test_fmt" in known_formats()
    finally:
        unregister("test_fmt")


def test_missing_register_rejected(tmp_path):
    _write_plugin(tmp_path, "bad", "name: bad\n", "# 无 register 入口\n")
    manager = _manager(tmp_path, tmp_path, tmp_path / "missing.yaml")
    with pytest.raises(PluginError, match="register"):
        manager.load()


def test_unknown_manifest_field_rejected(tmp_path):
    _write_plugin(tmp_path, "bad", "name: bad\nfoo: 1\n", "# 无 register 入口\n")
    manager = _manager(tmp_path, tmp_path, tmp_path / "missing.yaml")
    with pytest.raises(PluginError, match="未知字段"):
        manager.load()


def test_allowlist_limits_plugins(tmp_path):
    _write_plugin(tmp_path, "plugin_a", "name: plugin_a\n", ADAPTER_CODE)
    _write_plugin(
        tmp_path,
        "plugin_b",
        "name: plugin_b\n",
        ADAPTER_CODE.replace('"test_fmt"', '"test_fmt_b"'),
    )
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("plugins: [plugin_a]\n", encoding="utf-8")
    manager = _manager(tmp_path, tmp_path, cfg)
    assert [m.name for m in manager.load()] == ["plugin_a"]
    try:
        assert "test_fmt" in known_formats()
        assert "test_fmt_b" not in known_formats()
    finally:
        unregister("test_fmt")


def test_empty_allowlist_disables_all(tmp_path):
    _write_plugin(tmp_path, "plugin_a", "name: plugin_a\n", ADAPTER_CODE)
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("plugins: []\n", encoding="utf-8")
    manager = _manager(tmp_path, tmp_path, cfg)
    assert manager.load() == []
    assert "test_fmt" not in known_formats()


def test_invalid_plugins_config_rejected(tmp_path):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("plugins: hello\n", encoding="utf-8")
    manager = _manager(tmp_path, tmp_path, cfg)
    with pytest.raises(PluginError, match="plugins"):
        manager.load()


def test_hooks_fire_in_order(tmp_path):
    log_file = tmp_path / "hooks.log"
    _write_plugin(
        tmp_path,
        "hook_plugin",
        "name: hook_plugin\n",
        HOOK_CODE.format(path=log_file),
    )
    manager = _manager(tmp_path, tmp_path, tmp_path / "missing.yaml")
    manager.load()
    manager.fire(ON_RUN_START, config=object())
    manager.fire(ON_EXAM_PARSED, exam=object(), score=object(), questions=object(), config=object())
    assert log_file.read_text(encoding="utf-8").splitlines() == ["start", "parsed"]


def test_load_config_parses_plugins_key(tmp_path):
    exams_dir = tmp_path / "exams"
    exams_dir.mkdir()
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"subjects: [语文, 数学]\nplugins: [my_format]\nexams_dir: '{exams_dir}'\n",
        encoding="utf-8",
    )
    from grade_analyzer.config import load_config

    loaded = load_config(str(cfg))
    assert loaded.plugins == ["my_format"]


def test_load_plugins_default_manager_no_plugins_dir():
    # 仓库 plugins/ 目录含 objective_analyze 插件，默认加载且可重复调用
    from grade_analyzer.plugins.loader import list_tasks

    loaded = load_plugins()
    assert any(m.name == "objective_analyze" for m in loaded)
    assert load_plugins() == loaded
    task_names = [name for name, _plugin, _desc in list_tasks()]
    assert "objective_analyze" in task_names


def test_manager_registers_and_runs_task(tmp_path):
    log = tmp_path / "task.log"
    _write_plugin(tmp_path, "task_plugin", "name: task_plugin\n", TASK_CODE.format(path=log))
    manager = _manager(tmp_path, tmp_path, tmp_path / "missing.yaml")
    manager.load()
    assert ("my_task", "task_plugin", "测试任务") in manager.list_tasks()
    result = manager.run_task(
        "my_task",
        config_path="c1",
        plugin_config="p1",
        input_dir="i1",
        output_dir="o1",
    )
    assert result == 7
    assert log.read_text(encoding="utf-8").strip() == "c1|p1|i1|o1"


def test_unknown_task_rejected(tmp_path):
    _write_plugin(tmp_path, "task_plugin", "name: task_plugin\n", TASK_CODE.format(path=tmp_path / "t.log"))
    manager = _manager(tmp_path, tmp_path, tmp_path / "missing.yaml")
    manager.load()
    with pytest.raises(ValueError, match="未注册的任务"):
        manager.run_task("nope")


def test_duplicate_task_rejected(tmp_path):
    _write_plugin(tmp_path, "ta", "name: ta\n", TASK_CODE.format(path=tmp_path / "a.log"))
    _write_plugin(tmp_path, "tb", "name: tb\n", TASK_CODE.format(path=tmp_path / "b.log"))
    manager = _manager(tmp_path, tmp_path, tmp_path / "missing.yaml")
    with pytest.raises(PluginError, match="已由"):
        manager.load()
