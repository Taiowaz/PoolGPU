"""PoolGPU Master API - 供 Worker 回调汇报任务进度"""

from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from scheduler.scheduler import Scheduler
from shared.models import TaskStatus

app = Flask(__name__)
socketio = SocketIO(app)
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


def run_master_api(host: str = "0.0.0.0", port: int = 8080):
    print(f"Master API running on port {port}")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
