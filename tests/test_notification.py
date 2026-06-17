# tests/test_notification.py
import pytest
from scheduler.scheduler import Scheduler
from shared.models import TaskStatus


@pytest.fixture
def scheduler(tmp_path):
    db_path = str(tmp_path / "test.db")
    return Scheduler(db_path)


def test_add_notification(scheduler):
    """测试添加通知"""
    scheduler.add_notification(1, "test_task", "completed", "任务完成")
    notifications = scheduler.get_notifications()
    assert len(notifications) == 1
    assert notifications[0]["task_name"] == "test_task"
    assert notifications[0]["status"] == "completed"


def test_get_notifications_limit(scheduler):
    """测试获取通知限制"""
    for i in range(10):
        scheduler.add_notification(i, f"task_{i}", "completed", f"任务 {i} 完成")
    notifications = scheduler.get_notifications(limit=5)
    assert len(notifications) == 5


def test_notifications_ordered_by_time(scheduler):
    """测试通知按时间排序"""
    import time
    scheduler.add_notification(1, "task_1", "completed", "任务1完成")
    time.sleep(1.1)
    scheduler.add_notification(2, "task_2", "failed", "任务2失败")
    notifications = scheduler.get_notifications()
    assert notifications[0]["task_name"] == "task_2"
    assert notifications[1]["task_name"] == "task_1"
