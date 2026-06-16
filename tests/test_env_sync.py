# tests/test_env_sync.py
import pytest
from unittest.mock import patch, MagicMock
from scheduler.scheduler import Scheduler
from shared.config import get_env_name, get_env_pack_path


def test_get_env_name():
    """测试获取环境名配置"""
    env_name = get_env_name()
    assert isinstance(env_name, str)
    assert len(env_name) > 0


def test_get_env_pack_path():
    """测试获取打包路径配置"""
    pack_path = get_env_pack_path()
    assert isinstance(pack_path, str)
    assert pack_path.endswith(".tar.gz")


@pytest.fixture
def scheduler():
    return Scheduler(":memory:")


def test_env_sync_all_workers_no_servers(scheduler):
    """测试无服务器时的环境同步"""
    with patch("subprocess.run") as mock_run, \
         patch("scheduler.scheduler.load_config") as mock_config:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_config.return_value = {
            "master": {"host": "127.0.0.1"},
            "servers": [],
            "sync": {"env_name": "myenv", "env_pack_path": "/tmp/myenv.tar.gz"},
            "worker": {"port": 8090},
        }
        result = scheduler.env_sync_all_workers()
        assert result["pack_status"] == "success"
        assert result["workers"] == []


@patch("subprocess.run")
@patch("scheduler.scheduler.requests.post")
@patch("scheduler.scheduler.load_config")
def test_env_sync_all_workers_success(mock_config, mock_post, mock_run, scheduler):
    """测试环境同步成功"""
    # Mock conda-pack
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    # Mock Worker response
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        "status": "success",
        "duration": 5.0
    }
    mock_post.return_value = mock_response

    # Mock config with test server
    mock_config.return_value = {
        "master": {"host": "127.0.0.1"},
        "servers": [{"name": "test_server", "host": "127.0.0.1", "user": "test"}],
        "sync": {"env_name": "myenv", "env_pack_path": "/tmp/myenv.tar.gz"},
        "worker": {"port": 8090},
    }

    result = scheduler.env_sync_all_workers()
    assert result["pack_status"] == "success"
    assert len(result["workers"]) == 1
    assert result["workers"][0]["server"] == "test_server"
    assert result["workers"][0]["status"] == "success"


@patch("subprocess.run")
@patch("scheduler.scheduler.load_config")
def test_env_sync_pack_failure(mock_config, mock_run, scheduler):
    """测试打包失败"""
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="Environment not found"
    )
    mock_config.return_value = {
        "master": {"host": "127.0.0.1"},
        "servers": [],
        "sync": {"env_name": "myenv", "env_pack_path": "/tmp/myenv.tar.gz"},
        "worker": {"port": 8090},
    }

    result = scheduler.env_sync_all_workers()
    assert result["pack_status"] == "failed"
    assert "Environment not found" in result["pack_error"]
