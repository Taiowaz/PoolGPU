# 通知系统功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现通知系统，任务完成/失败时通过 WebSocket 推送通知到浏览器，并在 Web UI 上显示通知历史记录

**Architecture:** Master 通过 SocketIO 推送通知到浏览器。通知记录持久化到 SQLite 数据库。浏览器端监听 SocketIO 事件显示 Toast 通知，并加载通知历史记录。

**Tech Stack:** Python, Flask-SocketIO, SQLite, JavaScript

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `scheduler/scheduler.py` | 修改 | 新增通知相关方法 |
| `scheduler/master_api.py` | 修改 | 任务完成/失败时发送通知 |
| `webui/app.py` | 修改 | 初始化 SocketIO，新增通知 API |
| `webui/templates/index.html` | 修改 | 监听 SocketIO 事件，显示通知 |
| `tests/test_notification.py` | 新建 | 通知系统测试 |

---

### Task 1: Scheduler 通知方法

**Files:**
- Modify: `scheduler/scheduler.py`

- [ ] **Step 1: 在 scheduler/scheduler.py 中新增通知相关方法**

在 `Scheduler` 类的 `__init__` 方法中添加通知表初始化：

```python
def init_db(self):
    conn = sqlite3.connect(self.db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            command TEXT NOT NULL,
            gpu_count INTEGER NOT NULL,
            server TEXT,
            gpu_ids TEXT,
            status TEXT DEFAULT 'pending',
            progress REAL DEFAULT 0,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            result_path TEXT,
            error TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            task_name TEXT,
            status TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
```

在 `Scheduler` 类末尾添加：

```python
def add_notification(self, task_id: int, task_name: str, status: str, message: str):
    """添加通知"""
    conn = sqlite3.connect(self.db_path)
    c = conn.cursor()
    c.execute(
        "INSERT INTO notifications (task_id, task_name, status, message) VALUES (?, ?, ?, ?)",
        (task_id, task_name, status, message)
    )
    conn.commit()
    conn.close()

def get_notifications(self, limit: int = 50) -> list:
    """获取通知记录"""
    conn = sqlite3.connect(self.db_path)
    c = conn.cursor()
    c.execute(
        "SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    columns = [desc[0] for desc in c.description]
    notifications = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return notifications
```

- [ ] **Step 2: Commit**

```bash
git add scheduler/scheduler.py
git commit -m "feat: add notification methods and table to Scheduler"
```

---

### Task 2: Master API 发送通知

**Files:**
- Modify: `scheduler/master_api.py`

- [ ] **Step 1: 修改 scheduler/master_api.py 添加 SocketIO 和通知逻辑**

在文件顶部添加 SocketIO 初始化：

```python
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app)
scheduler: Scheduler = None
```

修改 `task_progress` 函数，在任务完成/失败时发送通知：

```python
@app.route("/api/tasks/<int:task_id>/progress", methods=["POST"])
def task_progress(task_id):
    data = request.json
    status = data.get("status")
    progress = data.get("progress", 0)
    stdout = data.get("stdout", "")
    stderr = data.get("stderr", "")
    result_dir = data.get("result_dir")

    task = scheduler.get_task(task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404

    if status == "completed":
        scheduler.update_task_status(
            task_id,
            TaskStatus.COMPLETED.value,
            progress=100,
            finished_at=__import__("datetime").datetime.now().isoformat(),
            result_path=stdout
        )
        # 自动收集结果
        if result_dir and task.get("server"):
            collect_result = scheduler.collect_result(
                task_id,
                task["server"],
                result_dir
            )
            if collect_result.get("status") == "success":
                scheduler.update_task_status(
                    task_id,
                    result_path=collect_result.get("local_path", "")
                )
        # 发送通知
        message = f"任务 {task['name']} 已完成"
        scheduler.add_notification(task_id, task["name"], "completed", message)
        socketio.emit("notification", {
            "task_id": task_id,
            "task_name": task["name"],
            "status": "completed",
            "message": message
        })
    elif status == "failed":
        scheduler.update_task_status(
            task_id,
            TaskStatus.FAILED.value,
            progress=0,
            finished_at=__import__("datetime").datetime.now().isoformat(),
            error=stderr
        )
        # 发送通知
        message = f"任务 {task['name']} 失败: {stderr[:100]}"
        scheduler.add_notification(task_id, task["name"], "failed", message)
        socketio.emit("notification", {
            "task_id": task_id,
            "task_name": task["name"],
            "status": "failed",
            "message": message
        })
        # 自动重试
        scheduler.retry_task(task_id)
    else:
        scheduler.update_task_status(
            task_id,
            TaskStatus.RUNNING.value,
            progress=progress
        )

    return jsonify({"status": "ok"})
```

修改 `run_master_api` 函数：

```python
def run_master_api(host: str = "0.0.0.0", port: int = 8080):
    print(f"Master API running on port {port}")
    socketio.run(app, host=host, port=port, debug=False)
```

- [ ] **Step 2: Commit**

```bash
git add scheduler/master_api.py
git commit -m "feat: add SocketIO notification on task completion/failure"
```

---

### Task 3: WebUI 通知 API

**Files:**
- Modify: `webui/app.py`

- [ ] **Step 1: 修改 webui/app.py 添加通知 API**

在文件顶部添加 SocketIO：

```python
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app)
scheduler = Scheduler()
```

添加通知 API：

```python
@app.route("/api/notifications")
def get_notifications():
    notifications = scheduler.get_notifications()
    return jsonify(notifications)
```

修改 `run_web` 函数：

```python
def run_web(host="0.0.0.0", port=5000):
    socketio.run(app, host=host, port=port, debug=True)
```

- [ ] **Step 2: Commit**

```bash
git add webui/app.py
git commit -m "feat: add notifications API endpoint"
```

---

### Task 4: 前端通知显示

**Files:**
- Modify: `webui/templates/index.html`

- [ ] **Step 1: 在 webui/templates/index.html 中添加通知功能**

在 `<style>` 中添加通知样式：

```css
.toast { position: fixed; top: 20px; right: 20px; padding: 15px 20px; border-radius: 6px; color: white; z-index: 1000; animation: slideIn 0.3s ease; }
.toast.success { background: #4CAF50; }
.toast.error { background: #f44336; }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
.notification-item { padding: 10px; border-bottom: 1px solid #eee; font-size: 14px; }
.notification-item.success { border-left: 3px solid #4CAF50; }
.notification-item.error { border-left: 3px solid #f44336; }
```

在 `<div class="section">` 末尾（任务队列之后）添加通知记录区域：

```html
<div class="section">
    <h2>通知记录</h2>
    <div id="notification-list">
        <!-- 动态加载 -->
    </div>
</div>
```

在 `<script>` 中添加通知逻辑：

```javascript
// SocketIO 通知
const socket = io();

socket.on('notification', function(data) {
    // 显示 Toast
    const toast = document.createElement('div');
    toast.className = `toast ${data.status}`;
    toast.textContent = data.message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);

    // 追加到通知列表
    const list = document.getElementById('notification-list');
    const item = document.createElement('div');
    item.className = `notification-item ${data.status}`;
    item.innerHTML = `<strong>${data.task_name}</strong> - ${data.message}`;
    list.insertBefore(item, list.firstChild);
});

// 加载通知记录
async function loadNotifications() {
    const res = await fetch('/api/notifications');
    const data = await res.json();
    const list = document.getElementById('notification-list');
    list.innerHTML = data.map(n => `
        <div class="notification-item ${n.status}">
            <strong>${n.task_name}</strong> - ${n.message}
            <small style="float:right;color:#999">${n.created_at}</small>
        </div>
    `).join('');
}

loadNotifications();
```

- [ ] **Step 2: Commit**

```bash
git add webui/templates/index.html
git commit -m "feat: add notification UI with toast and history"
```

---

### Task 5: 测试

**Files:**
- Create: `tests/test_notification.py`

- [ ] **Step 1: 创建通知系统测试**

```python
# tests/test_notification.py
import pytest
from scheduler.scheduler import Scheduler
from shared.models import TaskStatus


@pytest.fixture
def scheduler():
    return Scheduler(":memory:")


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
    scheduler.add_notification(1, "task_1", "completed", "任务1完成")
    scheduler.add_notification(2, "task_2", "failed", "任务2失败")
    notifications = scheduler.get_notifications()
    assert notifications[0]["task_name"] == "task_2"
    assert notifications[1]["task_name"] == "task_1"
```

- [ ] **Step 2: 运行测试**

Run: `cd /home/albin/PoolGPU && .venv/bin/python -m pytest tests/test_notification.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_notification.py
git commit -m "test: add notification system tests"
```

---

### Task 6: 端到端验证

- [ ] **Step 1: 验证所有模块可导入**

```bash
cd /home/albin/PoolGPU && .venv/bin/python -c "from scheduler.scheduler import Scheduler; print('scheduler OK')"
cd /home/albin/PoolGPU && .venv/bin/python -c "from scheduler.master_api import init_master_api; print('master_api OK')"
cd /home/albin/PoolGPU && .venv/bin/python -c "from webui.app import app; print('webui OK')"
```

- [ ] **Step 2: 运行所有测试**

```bash
cd /home/albin/PoolGPU && .venv/bin/python -m pytest tests/ -v
```

- [ ] **Step 3: Commit 最终状态**

```bash
git add -A
git commit -m "feat: notification system complete - end-to-end verified"
```
