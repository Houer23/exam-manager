"""配置模板同步脚本的单元测试。"""

from pathlib import Path

from sync_templates import sync_pairs


def test_sync_pairs(tmp_path):
    src = tmp_path / "config.yaml"
    src.write_text("personal:\n  scope:\n    mode: all\n", encoding="utf-8")
    dst = tmp_path / "_template.yaml"
    pairs = [("config.yaml", "_template.yaml")]
    done = sync_pairs(pairs, root=tmp_path)
    assert done == ["_template.yaml"]
    assert dst.read_text(encoding="utf-8") == src.read_text(encoding="utf-8")


def test_sync_pairs_missing_source(tmp_path, capsys):
    done = sync_pairs([("不存在.yaml", "_template.yaml")], root=tmp_path)
    assert done == []
    assert "跳过" in capsys.readouterr().out
