# tests/test_result_collection.py
import pytest
from unittest.mock import patch, MagicMock
from scheduler.scheduler import Scheduler
from shared.config import get_results_dir


def test_get_results_dir():
    """测试获取结果目录配置"""
    results_dir = get_results_dir()
    assert isinstance(results_dir, str)
    assert len(results_dir) > 0


@pytest.fixture
def scheduler():
    return Scheduler(":memory:")


@patch("scheduler.scheduler.requests.post")
def test_collect_result_success(mock_post, scheduler):
    """测试结果收集成功"""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        "status": "success",
        "files_count": 10,
        "duration": 2.5
    }
    mock_post.return_value = mock_response

    import yaml
    from pathlib import Path
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    original_servers = config.get("servers", [])
    config["servers"] = [{"name": "test_server", "host": "127.0.0.1", "user": "test"}]

    with open(config_path, "w") as f:
        yaml.dump(config, f)

    try:
        result = scheduler.collect_result(1, "test_server", "/tmp/results")
        assert result["status"] == "success"
        assert result["files_count"] == 10
    finally:
        config["servers"] = original_servers
        with open(config_path, "w") as f:
            yaml.dump(config, f)


@patch("scheduler.scheduler.requests.post")
def test_collect_result_server_not_found(mock_post, scheduler):
    """测试服务器不存在"""
    result = scheduler.collect_result(1, "nonexistent_server", "/tmp/results")
    assert result["status"] == "failed"
    assert "not found" in result["error"]
