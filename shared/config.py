"""PoolGPU Shared - 共享工具和配置"""

import yaml
from pathlib import Path
from typing import Dict, Optional

USER_CONFIG_DIR = Path.home() / ".local/share/poolgpu/config"
USER_CONFIG_FILE = USER_CONFIG_DIR / "config.yaml"
PROJECT_CONFIG_FILE = Path(__file__).parent.parent / "config.yaml"

DEFAULT_CONFIG = {
    "master": {"host": "127.0.0.1", "port": 8080, "web_port": 5000},
    "worker": {"port": 8090, "report_interval": 10},
    "gpu_models": {"3090Ti": 1, "4090D": 2, "5090": 3},
    "results": {"dir": "/tmp/poolgpu/results"},
    "sync": {"code_dir": ".", "env_name": "myenv", "env_pack_path": "/tmp/myenv.tar.gz"},
    "servers": [],
    "retry": {"delay_seconds": 5, "max_attempts": 3},
}

def get_config_path(level: str = "user") -> Path:
    if level == "user":
        return USER_CONFIG_FILE
    elif level == "project":
        return PROJECT_CONFIG_FILE
    else:
        raise ValueError(f"Unknown config level: {level}")

def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def load_config(merge_project: bool = True) -> Dict:
    config = DEFAULT_CONFIG.copy()

    if USER_CONFIG_FILE.exists():
        with open(USER_CONFIG_FILE) as f:
            user_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, user_config)

    if merge_project and PROJECT_CONFIG_FILE.exists():
        with open(PROJECT_CONFIG_FILE) as f:
            project_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, project_config)

    return config

def get_server_config(server_name: str) -> Optional[Dict]:
    """获取服务器配置"""
    config = load_config()
    for server in config.get("servers", []):
        if server["name"] == server_name:
            return server
    return None

def get_all_servers() -> list:
    """获取所有服务器配置"""
    config = load_config()
    return config.get("servers", [])


def get_worker_port() -> int:
    """获取 Worker HTTP 端口"""
    config = load_config()
    return config.get("worker", {}).get("port", 8090)


def get_report_interval() -> int:
    """获取 Worker 状态汇报间隔（秒）"""
    config = load_config()
    return config.get("worker", {}).get("report_interval", 10)


def get_gpu_performance_level(gpu_model: str) -> int:
    """获取 GPU 性能等级，未知型号返回 0"""
    config = load_config()
    return config.get("gpu_models", {}).get(gpu_model, 0)


def get_code_dir() -> str:
    """获取主服务器代码目录"""
    config = load_config()
    return config.get("sync", {}).get("code_dir", "/home/albin/code")


def get_sync_excludes() -> list:
    """获取 rsync 排除规则"""
    return [
        "__pycache__/",
        ".git/",
        ".venv/",
        "*.pyc",
        "*.pyo",
        ".pytest_cache/",
    ]


def get_env_name() -> str:
    """获取 conda 环境名"""
    config = load_config()
    return config.get("sync", {}).get("env_name", "myenv")


def get_env_pack_path() -> str:
    """获取环境打包文件路径"""
    config = load_config()
    return config.get("sync", {}).get("env_pack_path", "/tmp/myenv.tar.gz")


def get_results_dir() -> str:
    """获取结果存储目录"""
    config = load_config()
    return config.get("results", {}).get("dir", "/home/albin/poolgpu/results")
