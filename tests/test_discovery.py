from unittest.mock import patch, MagicMock
from shared.discovery import discover_workers, get_local_subnet, check_worker_health


def test_get_local_subnet():
    subnet = get_local_subnet()
    assert "/" in subnet


def test_check_worker_health_success():
    with patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"status": "ok", "gpus": 2}

        result = check_worker_health("192.168.1.100", 8090)
        assert result is not None
        assert result["gpus"] == 2


def test_check_worker_health_failure():
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("Connection refused")

        result = check_worker_health("192.168.1.100", 8090)
        assert result is None


def test_discover_workers():
    with patch('shared.discovery.check_worker_health') as mock_check:
        mock_check.side_effect = lambda h, p, t: {"host": h, "gpus": 2} if h.endswith("100") else None

        workers = discover_workers("192.168.1.0/24", timeout=0.1)
        assert len(workers) == 1
        assert workers[0]["host"] == "192.168.1.100"
