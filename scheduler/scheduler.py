"""PoolGPU Scheduler - 核心调度逻辑"""

import sqlite3
import time
import requests
from pathlib import Path
from typing import Optional, List, Dict

from shared.config import (
    load_config, get_server_config, get_all_servers,
    get_worker_port, get_gpu_performance_level, get_code_dir
)
from shared.models import TaskStatus, GPUInfo, TaskAssignment


class Scheduler:
    def __init__(self, db_path: str = "poolgpu.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self.init_db()

    def _get_conn(self):
        return self._conn

    def init_db(self):
        c = self._get_conn().cursor()
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
        self._get_conn().commit()

    def submit_task(self, name: str, command: str, gpu_count: int) -> int:
        c = self._get_conn().cursor()
        c.execute(
            "INSERT INTO tasks (name, command, gpu_count) VALUES (?, ?, ?)",
            (name, command, gpu_count)
        )
        task_id = c.lastrowid
        self._get_conn().commit()
        return task_id

    def get_task(self, task_id: int) -> Optional[Dict]:
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = c.fetchone()
        if row:
            return dict(row)
        return None

    def get_pending_tasks(self) -> List[Dict]:
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM tasks WHERE status = 'pending' ORDER BY created_at")
        tasks = [dict(row) for row in c.fetchall()]
        return tasks

    def get_all_tasks(self) -> List[Dict]:
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        tasks = [dict(row) for row in c.fetchall()]
        return tasks

    def update_task_status(self, task_id: int, status: str, **kwargs):
        c = self._get_conn().cursor()
        updates = ["status = ?"]
        values = [status]
        for key, value in kwargs.items():
            updates.append(f"{key} = ?")
            values.append(value)
        values.append(task_id)
        c.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", values)
        self._get_conn().commit()

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

    def sync_all_workers(self) -> list:
        """同步代码到所有 Worker"""
        import time
        from shared.config import get_code_dir, get_worker_port

        config = load_config()
        code_dir = get_code_dir()
        worker_port = get_worker_port()
        master_host = config["master"]["host"]
        source = f"{master_host}:{code_dir}"

        results = []
        for server in config.get("servers", []):
            start_time = time.time()
            try:
                resp = requests.post(
                    f"http://{server['host']}:{worker_port}/api/sync",
                    json={"source": source},
                    timeout=310  # rsync timeout + buffer
                )
                if resp.ok:
                    data = resp.json()
                    results.append({
                        "server": server["name"],
                        "status": data.get("status", "unknown"),
                        "files_changed": data.get("files_changed", 0),
                        "duration": data.get("duration", 0)
                    })
                else:
                    results.append({
                        "server": server["name"],
                        "status": "failed",
                        "error": resp.text,
                        "duration": round(time.time() - start_time, 2)
                    })
            except Exception as e:
                results.append({
                    "server": server["name"],
                    "status": "failed",
                    "error": str(e),
                    "duration": round(time.time() - start_time, 2)
                })

        return results
