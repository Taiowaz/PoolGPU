# tests/test_sync.py
import pytest
from unittest.mock import patch, MagicMock
from scheduler.scheduler import Scheduler
from shared.config import get_code_dir, get_sync_excludes


def test_get_code_dir():
    """测试获取代码目录配置"""
    code_dir = get_code_dir()
    assert isinstance(code_dir, str)
    assert len(code_dir) > 0


def test_get_sync_excludes():
    """测试获取排除规则"""
    excludes = get_sync_excludes()
    assert isinstance(excludes, list)
    assert "__pycache__/" in excludes
    assert ".git/" in excludes
    assert ".venv/" in excludes


@pytest.fixture
def scheduler():
    return Scheduler(":memory:")


@patch("scheduler.scheduler.load_config")
def test_sync_all_workers_no_servers(mock_load_config, scheduler):
    """测试无服务器时的同步"""
    mock_load_config.return_value = {"master": {"host": "127.0.0.1"}, "workers": []}
    results = scheduler.sync_all_workers()
    assert results == []


@patch("scheduler.scheduler.requests.post")
@patch("scheduler.scheduler.load_config")
def test_sync_all_workers_success(mock_load_config, mock_post, scheduler):
    """测试同步成功"""
    mock_load_config.return_value = {
        "master": {"host": "127.0.0.1"},
        "workers": [{"name": "test_server", "host": "127.0.0.1", "user": "test"}]
    }

    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        "status": "success",
        "files_changed": 5,
        "duration": 1.2
    }
    mock_post.return_value = mock_response

    results = scheduler.sync_all_workers()
    assert len(results) == 1
    assert results[0]["server"] == "test_server"
    assert results[0]["status"] == "success"


@patch("scheduler.scheduler.requests.post")
@patch("scheduler.scheduler.load_config")
def test_sync_all_workers_failure(mock_load_config, mock_post, scheduler):
    """测试同步失败"""
    mock_load_config.return_value = {
        "master": {"host": "127.0.0.1"},
        "workers": [{"name": "test_server", "host": "127.0.0.1", "user": "test"}]
    }

    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.text = "Connection refused"
    mock_post.return_value = mock_response

    results = scheduler.sync_all_workers()
    assert len(results) == 1
    assert results[0]["server"] == "test_server"
    assert results[0]["status"] == "failed"
