import os
import tempfile
from pathlib import Path
from shared.config import load_config, get_config_path, USER_CONFIG_DIR

def test_user_config_path():
    path = get_config_path("user")
    assert path == Path.home() / ".local/share/poolgpu/config/config.yaml"

def test_project_config_path():
    path = get_config_path("project")
    assert path.name == "config.yaml"

def test_load_config_returns_dict():
    config = load_config(merge_project=False)
    assert isinstance(config, dict)
    assert "master" in config

def test_config_merge_priority():
    with tempfile.TemporaryDirectory() as tmpdir:
        user_config = Path(tmpdir) / "config.yaml"
        user_config.write_text("master:\n  port: 9999\n")

        import shared.config
        orig_dir = shared.config.USER_CONFIG_DIR
        orig_file = shared.config.USER_CONFIG_FILE
        shared.config.USER_CONFIG_DIR = Path(tmpdir)
        shared.config.USER_CONFIG_FILE = user_config

        config = load_config(merge_project=False)
        assert config["master"]["port"] == 9999

        shared.config.USER_CONFIG_DIR = orig_dir
        shared.config.USER_CONFIG_FILE = orig_file
