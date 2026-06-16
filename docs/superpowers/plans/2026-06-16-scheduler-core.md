# 调度器核心逻辑实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 GPU 资源池调度系统的核心调度逻辑、Worker HTTP 服务、CLI 命令和 WebUI API 对接

**Architecture:** Master 通过 HTTP API 与各服务器上的 Worker 通信。任务提交时同步触发调度，按 GPU 性能优先策略分配资源。Worker 作为独立 HTTP 服务运行，定期向 Master 汇报任务进度。

**Tech Stack:** Python, Flask, Flask-SocketIO, SQLite, Click, PyYAML, nvidia-ml-py

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `shared/config.py` | 修改 | 新增 GPU 性能等级、Worker 端口等配置读取 |
| `shared/models.py` | 新建 | 共享数据模型（TaskStatus 枚举、GPUInfo 等） |
| `scheduler/scheduler.py` | 重写 | 核心调度逻辑：GPU 查询、分配、任务提交 |
| `scheduler/master_api.py` | 新建 | Master 端 HTTP API（供 Worker 回调汇报进度） |
| `worker/worker.py` | 重写 | Worker HTTP 服务：GPU 状态、任务执行、进度汇报 |
| `cli/main.py` | 修改 | 实现 submit/status 命令 |
| `webui/app.py` | 修改 | API 对接真实数据 |
| `tests/test_scheduler.py` | 扩展 | 调度逻辑单元测试 |
| `tests/test_worker.py` | 新建 | Worker API 测试 |
| `tests/test_master_api.py` | 新建 | Master 回调 API 测试 |

---

### Task 1: 共享数据模型

**Files:**
- Create: `shared/models.py`

- [ ] **Step 1: 创建 TaskStatus 枚举和 GPUInfo 数据类**

```python
# shared/models.py
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GPUInfo:
    index: int
    name: str
    memory_used: int
    memory_total: int
    utilization: int
    status: str  # "idle" | "busy" | "error"

    @property
    def is_idle(self) -> bool:
        return self.status == "idle"


@dataclass
class TaskAssignment:
    task_id: int
    server: str
    gpu_ids: list[int]
```

- [ ] **Step 2: Commit**

```bash
git add shared/models.py
git commit -m "feat: add shared data models (TaskStatus, GPUInfo, TaskAssignment)"
```

---

### Task 2: 扩展配置读取

**Files:**
- Modify: `shared/config.py`

- [ ] **Step 1: 在 config.yaml 中新增配置项**

```yaml
# config.yaml 新增（在文件末尾追加）
worker:
  port: 8090
  report_interval: 10

gpu_models:
  "5090": 3
  "4090D": 2
  "3090Ti": 1
```

- [ ] **Step 2: 在 shared/config.py 中新增配置读取函数**

在 `shared/config.py` 末尾添加：

```python
def get_worker_port() -> int:
    """获取 Worker HTTP 端口"""
    config = load_config()
    return config.get("worker", {}).get("port", 8090)


def get_report_interval() -> int:
    """获取 Worker 状态汇报间隔（秒）"""
    config = load_config()
    return config.get("worker", {}).get("report_interval", 10)


def get_gpu_performance等级(gpu_model: str) -> int:
    """获取 GPU 性能等级，未知型号返回 0"""
    config = load_config()
    return config.get("gpu_models", {}).get(gpu_model, 0)
```

修正：函数名不能有中文，改为：

```python
def get_gpu_performance_level(gpu_model: str) -> int:
    """获取 GPU 性能等级，未知型号返回 0"""
    config = load_config()
    return config.get("gpu_models", {}).get(gpu_model, 0)
```

- [ ] **Step 3: Commit**

```bash
git add shared/config.py config.yaml
git commit -m "feat: add GPU performance level and worker config readers"
```

---

### Task 3: Worker HTTP 服务

**Files:**
- Rewrite: `worker/worker.py`

- [ ] **Step 1: 重写 worker/worker.py 为 Flask HTTP 服务**

```python
"""PoolGPU Worker - 服务器端 Worker HTTP 服务"""

import subprocess
import threading
import time
import requests
from flask import Flask, request, jsonify
from typing import Dict, List

from shared.config import get_worker_port, get_report_interval, get_all_servers, load_config

app = Flask(__name__)

# 全局任务进程存储
running_tasks: Dict[int, subprocess.Popen] = {}
server_name: str = ""


def init_worker(name: str):
    global server_name
    server_name = name


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "server": server_name})


@app.route("/api/gpu")
def get_gpu_status():
    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        gpus = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split(", ")
                util = int(parts[4])
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "memory_used": int(parts[2]),
                    "memory_total": int(parts[3]),
                    "utilization": util,
                    "status": "busy" if util > 0 else "idle"
                })
        return jsonify(gpus)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks", methods=["POST"])
def submit_task():
    data = request.json
    task_id = data["task_id"]
    command = data["command"]
    gpu_ids = data["gpu_ids"]

    env = {"CUDA_VISIBLE_DEVICES": ",".join(map(str, gpu_ids))}
    process = subprocess.Popen(
        command, shell=True, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    running_tasks[task_id] = process

    # 启动后台汇报线程
    report_interval = get_report_interval()
    thread = threading.Thread(
        target=report_progress,
        args=(task_id, process, report_interval),
        daemon=True
    )
    thread.start()

    return jsonify({"status": "accepted"})


@app.route("/api/tasks/<int:task_id>/status")
def task_status(task_id):
    process = running_tasks.get(task_id)
    if process is None:
        return jsonify({"status": "unknown"}), 404

    poll = process.poll()
    if poll is None:
        return jsonify({"status": "running", "progress": 0})
    else:
        stdout, stderr = process.communicate()
        return jsonify({
            "status": "completed" if poll == 0 else "failed",
            "returncode": poll,
            "stdout": stdout.decode(),
            "stderr": stderr.decode()
        })


@app.route("/api/tasks/<int:task_id>/cancel", methods=["POST"])
def cancel_task(task_id):
    process = running_tasks.get(task_id)
    if process and process.poll() is None:
        process.terminate()
        process.wait(timeout=5)
    return jsonify({"status": "cancelled"})


def report_progress(task_id: int, process: subprocess.Popen, interval: int):
    """后台线程：定期向 Master 汇报任务进度"""
    config = load_config()
    master_host = config["master"]["host"]
    master_port = config["master"]["port"]
    master_url = f"http://{master_host}:{master_port}/api/tasks/{task_id}/progress"

    while process.poll() is None:
        try:
            requests.post(master_url, json={
                "status": "running",
                "progress": 0
            }, timeout=5)
        except Exception:
            pass
        time.sleep(interval)

    # 任务结束，汇报最终状态
    stdout, stderr = process.communicate()
    try:
        requests.post(master_url, json={
            "status": "completed" if process.returncode == 0 else "failed",
            "progress": 100 if process.returncode == 0 else 0,
            "stdout": stdout.decode(),
            "stderr": stderr.decode()
        }, timeout=5)
    except Exception:
        pass

    # 清理
    running_tasks.pop(task_id, None)


def run_worker(server_name_arg: str):
    init_worker(server_name_arg)
    port = get_worker_port()
    print(f"Worker [{server_name_arg}] running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
```

- [ ] **Step 2: Commit**

```bash
git add worker/worker.py
git commit -m "feat: implement Worker HTTP service with GPU status and task execution"
```

---

### Task 4: 调度器核心逻辑

**Files:**
- Rewrite: `scheduler/scheduler.py`

- [ ] **Step 1: 重写 scheduler/scheduler.py**

```python
"""PoolGPU Scheduler - 核心调度逻辑"""

import sqlite3
import time
import requests
from pathlib import Path
from typing import Optional, List, Dict

from shared.config import (
    load_config, get_server_config, get_all_servers,
    get_worker_port, get_gpu_performance_level
)
from shared.models import TaskStatus, GPUInfo, TaskAssignment


class Scheduler:
    def __init__(self, db_path: str = "poolgpu.db"):
        self.db_path = db_path
        self.init_db()

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
        conn.commit()
        conn.close()

    def submit_task(self, name: str, command: str, gpu_count: int) -> int:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO tasks (name, command, gpu_count) VALUES (?, ?, ?)",
            (name, command, gpu_count)
        )
        task_id = c.lastrowid
        conn.commit()
        conn.close()
        return task_id

    def get_task(self, task_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        columns = [desc[0] for desc in c.description]
        row = c.fetchone()
        conn.close()
        if row:
            return dict(zip(columns, row))
        return None

    def get_pending_tasks(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM tasks WHERE status = 'pending' ORDER BY created_at")
        columns = [desc[0] for desc in c.description]
        tasks = [dict(zip(columns, row)) for row in c.fetchall()]
        conn.close()
        return tasks

    def get_all_tasks(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        columns = [desc[0] for desc in c.description]
        tasks = [dict(zip(columns, row)) for row in c.fetchall()]
        conn.close()
        return tasks

    def update_task_status(self, task_id: int, status: str, **kwargs):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        updates = ["status = ?"]
        values = [status]
        for key, value in kwargs.items():
            updates.append(f"{key} = ?")
            values.append(value)
        values.append(task_id)
        c.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        conn.close()

    def get_all_gpu_status(self) -> List[Dict]:
        """查询所有 Worker 的 GPU 状态"""
        config = load_config()
        worker_port = get_worker_port()
        all_gpus = []

        for server in config.get("servers", []):
            try:
                resp = requests.get(
                    f"http://{server['host']}:{worker_port}/api/gpu",
                    timeout=5
                )
                if resp.ok:
                    gpus = resp.json()
                    for gpu in gpus:
                        gpu["server"] = server["name"]
                        gpu["server_host"] = server["host"]
                        gpu["gpu_model"] = server.get("gpu_model", "unknown")
                    all_gpus.extend(gpus)
            except Exception:
                pass

        return all_gpus

    def allocate_gpus(self, gpu_count: int) -> Optional[TaskAssignment]:
        """按性能优先策略分配 GPU"""
        all_gpus = self.get_all_gpu_status()

        # 筛选空闲 GPU
        idle_gpus = [g for g in all_gpus if g.get("status") == "idle"]
        if len(idle_gpus) < gpu_count:
            return None

        # 按性能等级降序排列
        idle_gpus.sort(
            key=lambda g: get_gpu_performance_level(g.get("gpu_model", "")),
            reverse=True
        )

        # 取前 gpu_count 个
        allocated = idle_gpus[:gpu_count]

        # 按服务器分组
        server_gpus: Dict[str, List[int]] = {}
        for gpu in allocated:
            server = gpu["server"]
            if server not in server_gpus:
                server_gpus[server] = []
            server_gpus[server].append(gpu["index"])

        # 选择 GPU 最多的服务器（同服务器优先）
        best_server = max(server_gpus, key=lambda s: len(server_gpus[s]))

        return TaskAssignment(
            task_id=0,  # 稍后设置
            server=best_server,
            gpu_ids=server_gpus[best_server]
        )

    def schedule_next(self) -> Optional[Dict]:
        """调度下一个待处理任务"""
        pending = self.get_pending_tasks()
        if not pending:
            return None

        task = pending[0]
        assignment = self.allocate_gpus(task["gpu_count"])

        if assignment is None:
            return None

        assignment.task_id = task["id"]

        # 提交任务到 Worker
        config = load_config()
        worker_port = get_worker_port()
        server_config = get_server_config(assignment.server)

        if server_config is None:
            return None

        try:
            resp = requests.post(
                f"http://{server_config['host']}:{worker_port}/api/tasks",
                json={
                    "task_id": task["id"],
                    "command": task["command"],
                    "gpu_ids": assignment.gpu_ids
                },
                timeout=10
            )
            if resp.ok:
                self.update_task_status(
                    task["id"],
                    TaskStatus.RUNNING.value,
                    server=assignment.server,
                    gpu_ids=",".join(map(str, assignment.gpu_ids))
                )
                return self.get_task(task["id"])
        except Exception:
            pass

        return None

    def retry_task(self, task_id: int) -> bool:
        """重试失败的任务"""
        task = self.get_task(task_id)
        if not task:
            return False

        if task["retry_count"] >= task["max_retries"]:
            return False

        self.update_task_status(
            task_id,
            TaskStatus.PENDING.value,
            retry_count=task["retry_count"] + 1,
            error=None
        )
        return True

    def cancel_task(self, task_id: int) -> bool:
        """取消任务"""
        task = self.get_task(task_id)
        if not task:
            return False

        if task["status"] == TaskStatus.RUNNING.value:
            # 通知 Worker 取消
            config = load_config()
            worker_port = get_worker_port()
            server_config = get_server_config(task["server"])
            if server_config:
                try:
                    requests.post(
                        f"http://{server_config['host']}:{worker_port}/api/tasks/{task_id}/cancel",
                        timeout=5
                    )
                except Exception:
                    pass

        self.update_task_status(task_id, TaskStatus.CANCELLED.value)
        return True
```

- [ ] **Step 2: Commit**

```bash
git add scheduler/scheduler.py
git commit -m "feat: implement core scheduler with GPU allocation and task dispatch"
```

---

### Task 5: Master 回调 API

**Files:**
- Create: `scheduler/master_api.py`

- [ ] **Step 1: 创建 Master HTTP API（供 Worker 回调）**

```python
"""PoolGPU Master API - 供 Worker 回调汇报任务进度"""

from flask import Flask, request, jsonify
from scheduler.scheduler import Scheduler
from shared.models import TaskStatus

app = Flask(__name__)
scheduler: Scheduler = None


def init_master_api(db_path: str = "poolgpu.db"):
    global scheduler
    scheduler = Scheduler(db_path)


@app.route("/api/tasks/<int:task_id>/progress", methods=["POST"])
def task_progress(task_id):
    data = request.json
    status = data.get("status")
    progress = data.get("progress", 0)
    stdout = data.get("stdout", "")
    stderr = data.get("stderr", "")

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
    elif status == "failed":
        scheduler.update_task_status(
            task_id,
            TaskStatus.FAILED.value,
            progress=0,
            finished_at=__import__("datetime").datetime.now().isoformat(),
            error=stderr
        )
        # 自动重试
        scheduler.retry_task(task_id)
    else:
        scheduler.update_task_status(
            task_id,
            TaskStatus.RUNNING.value,
            progress=progress
        )

    return jsonify({"status": "ok"})


def run_master_api(host: str = "0.0.0.0", port: int = 8080):
    print(f"Master API running on port {port}")
    app.run(host=host, port=port, debug=False)
```

- [ ] **Step 2: Commit**

```bash
git add scheduler/master_api.py
git commit -m "feat: add Master callback API for Worker progress reporting"
```

---

### Task 6: CLI 命令实现

**Files:**
- Modify: `cli/main.py`

- [ ] **Step 1: 重写 cli/main.py**

```python
"""PoolGPU CLI - 命令行工具"""

import click
import json
from scheduler.scheduler import Scheduler
from shared.config import load_config

scheduler = Scheduler()


@click.group()
def cli():
    """PoolGPU - GPU 资源池调度系统"""
    pass


@cli.command()
@click.option("--gpu", required=True, type=int, help="需要的 GPU 数量")
@click.option("--name", required=True, help="任务名称")
@click.option("--sync", is_flag=True, help="运行前自动同步代码")
@click.argument("command", nargs=-1)
def submit(gpu, name, sync, command):
    """提交任务"""
    if not command:
        click.echo("错误: 请提供执行命令", err=True)
        return

    cmd_str = " ".join(command)
    task_id = scheduler.submit_task(name, cmd_str, gpu)
    click.echo(f"任务已提交: ID={task_id}, 名称={name}, GPU={gpu}")

    # 触发调度
    result = scheduler.schedule_next()
    if result:
        click.echo(f"任务已调度: 服务器={result['server']}, GPU={result['gpu_ids']}")
    else:
        click.echo("等待可用 GPU...")


@cli.command()
def status():
    """查看任务状态"""
    tasks = scheduler.get_all_tasks()
    if not tasks:
        click.echo("暂无任务")
        return

    click.echo(f"{'ID':<5} {'名称':<15} {'GPU':<5} {'状态':<12} {'进度':<8} {'服务器':<10}")
    click.echo("-" * 60)
    for t in tasks:
        click.echo(
            f"{t['id']:<5} {t['name']:<15} {t['gpu_count']:<5} "
            f"{t['status']:<12} {t['progress']:<8.0f} {t['server'] or '-':<10}"
        )


@cli.command()
def gpu():
    """查看 GPU 使用率"""
    gpus = scheduler.get_all_gpu_status()
    if not gpus:
        click.echo("无法获取 GPU 状态（Worker 可能未运行）")
        return

    # 按服务器分组
    servers = {}
    for g in gpus:
        server = g.get("server", "unknown")
        if server not in servers:
            servers[server] = []
        servers[server].append(g)

    for server, gpu_list in servers.items():
        model = gpu_list[0].get("gpu_model", "?")
        statuses = []
        for g in sorted(gpu_list, key=lambda x: x["index"]):
            icon = "🟢 空闲" if g["status"] == "idle" else "🟡 运行"
            if g["status"] == "error":
                icon = "🔴 故障"
            statuses.append(icon)
        click.echo(f"  {server} ({model}×{len(gpu_list)}): {' '.join(statuses)}")


@cli.command()
def sync():
    """同步代码到所有服务器"""
    click.echo("代码同步功能将在后续迭代中实现")


@cli.command()
def env_sync():
    """同步环境到所有服务器"""
    click.echo("环境同步功能将在后续迭代中实现")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Commit**

```bash
git add cli/main.py
git commit -m "feat: implement CLI submit and status commands"
```

---

### Task 7: WebUI API 对接

**Files:**
- Modify: `webui/app.py`

- [ ] **Step 1: 重写 webui/app.py 对接真实数据**

```python
"""PoolGPU Web UI - Web 界面"""

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from scheduler.scheduler import Scheduler

app = Flask(__name__)
socketio = SocketIO(app)
scheduler = Scheduler()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/tasks")
def get_tasks():
    tasks = scheduler.get_all_tasks()
    return jsonify(tasks)


@app.route("/api/gpu")
def get_gpu():
    all_gpus = scheduler.get_all_gpu_status()

    # 按服务器分组
    servers = {}
    for g in all_gpus:
        server = g.get("server", "unknown")
        if server not in servers:
            servers[server] = {"server": server, "model": g.get("gpu_model", "?"), "gpus": []}
        servers[server]["gpus"].append({
            "id": g["index"],
            "status": g["status"],
            "memory_used": g.get("memory_used", 0),
            "memory_total": g.get("memory_total", 0),
            "utilization": g.get("utilization", 0)
        })

    return jsonify(list(servers.values()))


def run_web(host="0.0.0.0", port=5000):
    socketio.run(app, host=host, port=port, debug=True)
```

- [ ] **Step 2: Commit**

```bash
git add webui/app.py
git commit -m "feat: connect WebUI APIs to real scheduler data"
```

---

### Task 8: 启动入口

**Files:**
- Create: `main.py`

- [ ] **Step 1: 创建主启动入口**

```python
"""PoolGPU 主启动入口"""

import sys
import argparse
from shared.config import load_config
from scheduler.scheduler import Scheduler
from scheduler.master_api import init_master_api, run_master_api
from worker.worker import run_worker


def main():
    parser = argparse.ArgumentParser(description="PoolGPU - GPU 资源池调度系统")
    parser.add_argument("role", choices=["master", "worker"], help="启动角色")
    parser.add_argument("--server", help="Worker 服务器名称（仅 worker 角色需要）")

    args = parser.parse_args()
    config = load_config()

    if args.role == "master":
        init_master_api()
        master_host = config["master"]["host"]
        master_port = config["master"]["port"]
        web_port = config["master"]["web_port"]
        print(f"Master API: http://{master_host}:{master_port}")
        print(f"Web UI: http://{master_host}:{web_port}")
        run_master_api(master_host, master_port)

    elif args.role == "worker":
        if not args.server:
            print("错误: worker 角色需要 --server 参数")
            sys.exit(1)
        run_worker(args.server)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: add main entry point for master/worker roles"
```

---

### Task 9: 测试

**Files:**
- Modify: `tests/test_scheduler.py`
- Create: `tests/test_worker.py`

- [ ] **Step 1: 扩展调度器测试**

```python
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
```

- [ ] **Step 2: 运行测试**

Run: `cd /home/albin/PoolGPU && python -m pytest tests/test_scheduler.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_scheduler.py
git commit -m "test: expand scheduler unit tests"
```

---

### Task 10: 端到端验证

- [ ] **Step 1: 在主服务器启动 Master**

Run: `python main.py master`

- [ ] **Step 2: 在另一终端启动 Worker（模拟）**

Run: `python main.py worker --server server1`

- [ ] **Step 3: 提交任务测试**

Run: `poolgpu submit --gpu 1 --name "test" -- echo hello`

- [ ] **Step 4: 查看任务状态**

Run: `poolgpu status`

- [ ] **Step 5: 查看 GPU 状态**

Run: `poolgpu gpu`

- [ ] **Step 6: Commit 最终状态**

```bash
git add -A
git commit -m "feat: scheduler core logic complete - end-to-end verified"
```
