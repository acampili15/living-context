import json

from config import DEFAULTS, load_config


def test_load_config_defaults_when_no_override_file(tmp_path):
    config = load_config(tmp_path)
    assert config == DEFAULTS
    # Must be a copy, not the module-level dict itself.
    config["threshold_lines"] = 1
    assert DEFAULTS["threshold_lines"] != 1


def test_load_config_merges_overrides(tmp_path):
    override_dir = tmp_path / ".living-context"
    override_dir.mkdir()
    (override_dir / "config.json").write_text(json.dumps({
        "threshold_lines": 250,
        "auto_commit": True,
    }))
    config = load_config(tmp_path)
    assert config["threshold_lines"] == 250
    assert config["auto_commit"] is True
    # Untouched keys keep their defaults.
    assert config["doc_path"] == DEFAULTS["doc_path"]
    assert config["warn_ratio"] == DEFAULTS["warn_ratio"]


def test_load_config_ignores_unknown_keys(tmp_path):
    override_dir = tmp_path / ".living-context"
    override_dir.mkdir()
    (override_dir / "config.json").write_text(json.dumps({"not_a_real_key": 42}))
    config = load_config(tmp_path)
    assert "not_a_real_key" not in config
    assert config == DEFAULTS


def test_load_config_falls_back_on_malformed_json(tmp_path):
    override_dir = tmp_path / ".living-context"
    override_dir.mkdir()
    (override_dir / "config.json").write_text("{not valid json")
    config = load_config(tmp_path)
    assert config == DEFAULTS


def test_load_config_falls_back_when_override_is_a_directory(tmp_path):
    # config_path.is_file() should be False when it's a directory, so this
    # must fall back to defaults rather than raising on read_text().
    override_dir = tmp_path / ".living-context"
    override_dir.mkdir()
    (override_dir / "config.json").mkdir()
    config = load_config(tmp_path)
    assert config == DEFAULTS
