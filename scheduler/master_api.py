"""PoolGPU Master API - 供 Worker 回调汇报任务进度 + Web UI"""

from pathlib import Path
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO
from scheduler.scheduler import Scheduler
from shared.models import TaskStatus

template_dir = Path(__file__).parent.parent / "webui" / "templates"
app = Flask(__name__, template_folder=str(template_dir))
socketio = SocketIO(app)
scheduler: Scheduler = None


def init_master_api(db_path: str = "poolgpu.db"):
    global scheduler
    scheduler = Scheduler(db_path)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/tasks")
def get_tasks():
    return jsonify(scheduler.get_all_tasks())


@app.route("/api/gpu")
def get_gpu():
    all_gpus = scheduler.get_all_gpu_status()
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


@app.route("/api/notifications")
def get_notifications():
    return jsonify(scheduler.get_notifications())


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
        if result_dir and task.get("server"):
            collect_result = scheduler.collect_result(task_id, task["server"], result_dir)
            if collect_result.get("status") == "success":
                scheduler.update_task_status(task_id, result_path=collect_result.get("local_path", ""))
        message = f"任务 {task['name']} 已完成"
        scheduler.add_notification(task_id, task["name"], "completed", message)
        socketio.emit("notification", {
            "task_id": task_id, "task_name": task["name"],
            "status": "completed", "message": message
        })
    elif status == "failed":
        scheduler.update_task_status(
            task_id,
            TaskStatus.FAILED.value,
            progress=0,
            finished_at=__import__("datetime").datetime.now().isoformat(),
            error=stderr
        )
        message = f"任务 {task['name']} 失败: {stderr[:100]}"
        scheduler.add_notification(task_id, task["name"], "failed", message)
        socketio.emit("notification", {
            "task_id": task_id, "task_name": task["name"],
            "status": "failed", "message": message
        })
        scheduler.retry_task(task_id)
    else:
        scheduler.update_task_status(task_id, TaskStatus.RUNNING.value, progress=progress)

    return jsonify({"status": "ok"})


def run_master_api(host: str = "0.0.0.0", port: int = 8080):
    print(f"PoolGPU Master: http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
