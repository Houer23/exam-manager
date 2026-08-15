"""模板生成脚本的单元测试。"""

import pytest

from template_tools import TEMPLATE_TYPES, generate_type, scan


def test_generate_type_creates_template_and_config(tmp_path):
    written = generate_type("charts", root=tmp_path)
    tpl = tmp_path / "config/charts/_template.yaml"
    cfg = tmp_path / "config/charts/config.yaml"
    assert tpl.is_file() and cfg.is_file()
    assert tpl.read_text(encoding="utf-8") == TEMPLATE_TYPES["charts"]["default"]
    assert cfg.read_text(encoding="utf-8") == TEMPLATE_TYPES["charts"]["default"]
    assert len(written) == 2


def test_generate_type_does_not_overwrite_existing_config(tmp_path):
    cfg = tmp_path / "config/results/config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("自定义: 1\n", encoding="utf-8")
    generate_type("results", root=tmp_path)
    assert cfg.read_text(encoding="utf-8") == "自定义: 1\n"  # 保留用户配置
    tpl = tmp_path / "config/results/_template.yaml"
    assert tpl.read_text(encoding="utf-8") == TEMPLATE_TYPES["results"]["default"]


def test_scan_existence_generates_missing(tmp_path):
    results = scan(mode="existence", root=tmp_path)
    assert results["charts"] == "generated"
    assert (tmp_path / "config/charts/_template.yaml").is_file()
    results2 = scan(mode="existence", root=tmp_path)
    assert results2["charts"] == "ok"


def test_scan_diff_regenerates_changed_template(tmp_path):
    generate_type("charts", root=tmp_path)
    tpl = tmp_path / "config/charts/_template.yaml"
    tpl.write_text("changed\n", encoding="utf-8")
    res = scan(mode="existence", root=tmp_path)
    assert res["charts"] == "ok"  # 存在性模式不覆盖
    res = scan(mode="diff", root=tmp_path)
    assert res["charts"] == "generated"
    assert tpl.read_text(encoding="utf-8") == TEMPLATE_TYPES["charts"]["default"]


def test_scan_prompt_only(tmp_path):
    results = scan(mode="existence", prompt=True, root=tmp_path)
    assert results["charts"] == "prompted"
    assert not (tmp_path / "config/charts/_template.yaml").exists()


def test_unknown_type_raises():
    with pytest.raises(ValueError, match="未知模板类型"):
        generate_type("nope")


def test_generate_global_creates_config_only(tmp_path):
    written = generate_type("global", root=tmp_path)
    cfg = tmp_path / "config/config.yaml"
    assert cfg.is_file()
    assert cfg.read_text(encoding="utf-8") == TEMPLATE_TYPES["global"]["default"]
    assert len(written) == 1


def test_generate_global_does_not_overwrite_existing(tmp_path):
    cfg = tmp_path / "config/config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("自定义: 1\n", encoding="utf-8")
    written = generate_type("global", root=tmp_path)
    assert written == []
    assert cfg.read_text(encoding="utf-8") == "自定义: 1\n"


def test_scan_global_existence_generates_missing(tmp_path):
    res = scan(mode="existence", types=["global"], root=tmp_path)
    assert res["global"] == "generated"
    assert (tmp_path / "config/config.yaml").is_file()
    res2 = scan(mode="existence", types=["global"], root=tmp_path)
    assert res2["global"] == "ok"


def test_scan_diff_does_not_touch_global(tmp_path):
    generate_type("global", root=tmp_path)
    cfg = tmp_path / "config/config.yaml"
    cfg.write_text("自定义: 1\n", encoding="utf-8")
    res = scan(mode="diff", types=["global"], root=tmp_path)
    assert res["global"] == "ok"
    assert cfg.read_text(encoding="utf-8") == "自定义: 1\n"
