# tests/test_scheduler.py
import pytest
from scheduler.scheduler import Scheduler
from shared.models import TaskStatus


@pytest.fixture
def scheduler():
    return Scheduler(":memory:")


def test_scheduler_init():
    scheduler = Scheduler(":memory:")
    assert scheduler is not None


def test_submit_task(scheduler):
    task_id = scheduler.submit_task("test_task", "echo hello", 1)
    assert task_id > 0


def test_get_pending_tasks(scheduler):
    scheduler.submit_task("test_task", "echo hello", 1)
    pending = scheduler.get_pending_tasks()
    assert len(pending) == 1
    assert pending[0]["name"] == "test_task"


def test_get_task(scheduler):
    task_id = scheduler.submit_task("test_task", "echo hello", 1)
    task = scheduler.get_task(task_id)
    assert task is not None
    assert task["name"] == "test_task"
    assert task["status"] == TaskStatus.PENDING.value


def test_get_all_tasks(scheduler):
    scheduler.submit_task("task1", "echo 1", 1)
    scheduler.submit_task("task2", "echo 2", 2)
    tasks = scheduler.get_all_tasks()
    assert len(tasks) == 2


def test_update_task_status(scheduler):
    task_id = scheduler.submit_task("test_task", "echo hello", 1)
    scheduler.update_task_status(task_id, TaskStatus.RUNNING.value, server="server1")
    task = scheduler.get_task(task_id)
    assert task["status"] == TaskStatus.RUNNING.value
    assert task["server"] == "server1"


def test_cancel_task(scheduler):
    task_id = scheduler.submit_task("test_task", "echo hello", 1)
    result = scheduler.cancel_task(task_id)
    assert result is True
    task = scheduler.get_task(task_id)
    assert task["status"] == TaskStatus.CANCELLED.value


def test_retry_task(scheduler):
    task_id = scheduler.submit_task("test_task", "echo hello", 1)
    scheduler.update_task_status(task_id, TaskStatus.FAILED.value, error="test error")
    result = scheduler.retry_task(task_id)
    assert result is True
    task = scheduler.get_task(task_id)
    assert task["status"] == TaskStatus.PENDING.value
    assert task["retry_count"] == 1


def test_retry_exceeds_max(scheduler):
    task_id = scheduler.submit_task("test_task", "echo hello", 1)
    scheduler.update_task_status(task_id, TaskStatus.FAILED.value, retry_count=3, max_retries=3)
    result = scheduler.retry_task(task_id)
    assert result is False
