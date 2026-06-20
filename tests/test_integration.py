import tempfile
from pathlib import Path

import yaml

import shared.config
from shared.config import load_config


def test_full_config_lifecycle():
    """Test config creation, loading, and merging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original = shared.config.USER_CONFIG_DIR
        shared.config.USER_CONFIG_DIR = Path(tmpdir)
        shared.config.USER_CONFIG_FILE = Path(tmpdir) / "config.yaml"

        user_config = {
            "master": {"host": "10.0.0.1", "port": 9999},
            "servers": [
                {"name": "server1", "host": "10.0.0.2", "user": "test", "gpus": 2, "gpu_model": "4090"}
            ],
        }

        with open(shared.config.USER_CONFIG_FILE, "w") as f:
            yaml.dump(user_config, f)

        config = load_config(merge_project=False)

        assert config["master"]["host"] == "10.0.0.1"
        assert config["master"]["port"] == 9999
        assert config["worker"]["port"] == 8090
        assert len(config["servers"]) == 1
        assert config["servers"][0]["name"] == "server1"

        shared.config.USER_CONFIG_DIR = original
        shared.config.USER_CONFIG_FILE = original / "config.yaml"
