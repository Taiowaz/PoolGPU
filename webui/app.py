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


@app.route("/api/notifications")
def get_notifications():
    notifications = scheduler.get_notifications()
    return jsonify(notifications)


def run_web(host="0.0.0.0", port=5000):
    socketio.run(app, host=host, port=port, debug=True)
