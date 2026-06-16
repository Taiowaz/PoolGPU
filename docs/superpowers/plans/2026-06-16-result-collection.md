# 结果收集功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现结果收集功能，任务完成后自动将 Worker 上的结果目录推送到 Master

**Architecture:** Worker 推送方案——Worker 任务完成后主动把结果 rsync 推送到 Master。Master 收到任务完成通知时自动触发结果收集。

**Tech Stack:** Python, rsync, subprocess, Flask

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `shared/config.py` | 修改 | 新增结果目录配置读取 |
| `worker/worker.py` | 修改 | 新增 `/api/collect-result` 接口，修改进度汇报 |
| `scheduler/master_api.py` | 修改 | 收到完成通知时触发结果收集 |
| `scheduler/scheduler.py` | 修改 | 新增 `collect_result()` 方法 |
| `tests/test_result_collection.py` | 新建 | 结果收集测试 |

---

### Task 1: 结果目录配置读取

**Files:**
- Modify: `shared/config.py`

- [ ] **Step 1: 在 shared/config.py 中新增结果目录配置读取函数**

在 `shared/config.py` 末尾添加：

```python
def get_results_dir() -> str:
    """获取结果存储目录"""
    config = load_config()
    return config.get("results", {}).get("dir", "/home/albin/poolgpu/results")
```

- [ ] **Step 2: Commit**

```bash
git add shared/config.py
git commit -m "feat: add results dir config reader"
```

---

### Task 2: Worker 结果推送接口

**Files:**
- Modify: `worker/worker.py`

- [ ] **Step 1: 在 worker/worker.py 中新增 /api/collect-result 接口**

在 `worker/worker.py` 的 `sync_env` 函数之后添加：

```python
@app.route("/api/collect-result", methods=["POST"])
def collect_result():
    data = request.json
    task_id = data.get("task_id")
    result_dir = data.get("result_dir")
    target_host = data.get("target_host")

    if not task_id or not result_dir or not target_host:
        return jsonify({"error": "task_id, result_dir, and target_host are required"}), 400

    import subprocess
    import time
    import os

    if not os.path.exists(result_dir):
        return jsonify({
            "status": "failed",
            "error": f"Result directory not found: {result_dir}",
            "duration": 0
        }), 404

    target_path = f"{target_host}:/home/albin/poolgpu/results/task_{task_id}/"

    start_time = time.time()
    try:
        cmd = ["rsync", "-avz", f"{result_dir}/", target_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        duration = round(time.time() - start_time, 2)

        if result.returncode == 0:
            # 统计文件数
            files_count = len([
                l for l in result.stdout.split("\n")
                if l and not l.startswith("sending") and not l.startswith("sent")
            ])
            return jsonify({
                "status": "success",
                "files_count": files_count,
                "duration": duration
            })
        else:
            return jsonify({
                "status": "failed",
                "error": result.stderr,
                "duration": duration
            }), 500
    except subprocess.TimeoutExpired:
        return jsonify({
            "status": "failed",
            "error": "rsync timeout (300s)",
            "duration": 300
        }), 500
    except Exception as e:
        return jsonify({
            "status": "failed",
            "error": str(e),
            "duration": round(time.time() - start_time, 2)
        }), 500
```

- [ ] **Step 2: Commit**

```bash
git add worker/worker.py
git commit -m "feat: add /api/collect-result endpoint to Worker"
```

---

### Task 3: Scheduler 结果收集方法

**Files:**
- Modify: `scheduler/scheduler.py`

- [ ] **Step 1: 在 scheduler/scheduler.py 中新增 collect_result() 方法**

在 `Scheduler` 类的 `env_sync_all_workers` 方法之后添加：

```python
def collect_result(self, task_id: int, server_name: str, result_dir: str) -> dict:
    """从 Worker 收集任务结果"""
    import time
    from shared.config import get_worker_port, get_results_dir

    config = load_config()
    worker_port = get_worker_port()
    results_dir = get_results_dir()
    master_host = config["master"]["host"]

    # 找到服务器配置
    server_config = None
    for server in config.get("servers", []):
        if server["name"] == server_name:
            server_config = server
            break

    if server_config is None:
        return {"status": "failed", "error": f"Server {server_name} not found"}

    target_host = f"{master_host}:{results_dir}"

    start_time = time.time()
    try:
        resp = requests.post(
            f"http://{server_config['host']}:{worker_port}/api/collect-result",
            json={
                "task_id": task_id,
                "result_dir": result_dir,
                "target_host": target_host
            },
            timeout=310
        )
        if resp.ok:
            data = resp.json()
            return {
                "status": data.get("status", "unknown"),
                "files_count": data.get("files_count", 0),
                "duration": data.get("duration", 0),
                "local_path": f"{results_dir}/task_{task_id}"
            }
        else:
            return {
                "status": "failed",
                "error": resp.text,
                "duration": round(time.time() - start_time, 2)
            }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "duration": round(time.time() - start_time, 2)
        }
```

- [ ] **Step 2: Commit**

```bash
git add scheduler/scheduler.py
git commit -m "feat: add collect_result() method to Scheduler"
```

---

### Task 4: Master API 触发结果收集

**Files:**
- Modify: `scheduler/master_api.py`

- [ ] **Step 1: 修改 scheduler/master_api.py 的 task_progress 函数**

找到 `task_progress` 函数中处理 `completed` 状态的部分，修改为：

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
```

- [ ] **Step 2: Commit**

```bash
git add scheduler/master_api.py
git commit -m "feat: auto-collect results when task completes"
```

---

### Task 5: 测试

**Files:**
- Create: `tests/test_result_collection.py`

- [ ] **Step 1: 创建结果收集测试**

```python
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
```

- [ ] **Step 2: 运行测试**

Run: `cd /home/albin/PoolGPU && .venv/bin/python -m pytest tests/test_result_collection.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_result_collection.py
git commit -m "test: add result collection functionality tests"
```

---

### Task 6: 端到端验证

- [ ] **Step 1: 验证所有模块可导入**

```bash
cd /home/albin/PoolGPU && .venv/bin/python -c "from shared.config import get_results_dir; print('config OK')"
cd /home/albin/PoolGPU && .venv/bin/python -c "from scheduler.scheduler import Scheduler; print('scheduler OK')"
cd /home/albin/PoolGPU && .venv/bin/python -c "from scheduler.master_api import init_master_api; print('master_api OK')"
```

- [ ] **Step 2: 运行所有测试**

```bash
cd /home/albin/PoolGPU && .venv/bin/python -m pytest tests/ -v
```

- [ ] **Step 3: Commit 最终状态**

```bash
git add -A
git commit -m "feat: result collection feature complete - end-to-end verified"
```
