"""PoolGPU Shared - 共享工具和配置"""

import yaml
from pathlib import Path
from typing import Dict, Optional

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

def load_config() -> Dict:
    """加载配置"""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

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
