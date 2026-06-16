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
