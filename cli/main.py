"""PoolGPU CLI - 命令行工具"""

import copy
import os
import signal
import subprocess
from pathlib import Path

import click
import json
from scheduler.scheduler import Scheduler
from shared.config import load_config, get_config_path, USER_CONFIG_DIR, DEFAULT_CONFIG
from shared.discovery import discover_workers, get_local_ip, get_local_subnet

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

    # 先同步代码（如果指定了 --sync）
    if sync:
        click.echo("正在同步代码...")
        results = scheduler.sync_all_workers()
        failed = [r for r in results if r["status"] != "success"]
        if failed:
            click.echo(f"同步失败: {', '.join(r['server'] for r in failed)}")
            return
        click.echo("代码同步完成")

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
    results = scheduler.sync_all_workers()

    if not results:
        click.echo("没有配置 Worker 服务器")
        return

    click.echo("代码同步结果:")
    click.echo(f"{'服务器':<12} {'状态':<10} {'变更文件':<10} {'耗时':<8}")
    click.echo("-" * 45)

    for r in results:
        status_icon = "✅" if r["status"] == "success" else "❌"
        click.echo(
            f"{r['server']:<12} {status_icon} {r['status']:<8} "
            f"{r.get('files_changed', '-'):>6}    {r.get('duration', '-')}s"
        )


@cli.command()
def env_sync():
    """同步环境到所有服务器"""
    result = scheduler.env_sync_all_workers()

    # 显示打包结果
    if result["pack_status"] != "success":
        click.echo(f"环境打包失败: {result.get('pack_error', 'unknown error')}")
        return

    click.echo(f"环境打包完成 (耗时: {result['pack_duration']}s)")

    # 显示 Worker 同步结果
    workers = result.get("workers", [])
    if not workers:
        click.echo("没有配置 Worker 服务器")
        return

    click.echo("环境同步结果:")
    click.echo(f"{'服务器':<12} {'状态':<10} {'耗时':<8}")
    click.echo("-" * 35)

    for w in workers:
        status_icon = "✅" if w["status"] == "success" else "❌"
        click.echo(
            f"{w['server']:<12} {status_icon} {w['status']:<8} "
            f"{w.get('duration', '-')}s"
        )


PID_DIR = Path.home() / ".local/share/poolgpu/pids"


@cli.command()
def init():
    """智能配置向导"""
    import yaml

    click.echo("🔍 检测本机信息...")

    local_ip = get_local_ip()
    subnet = get_local_subnet()
    click.echo(f"  - IP: {local_ip}")

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,count", "--format=csv,noheader"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            gpu_info = result.stdout.strip().split("\n")[0]
            click.echo(f"  - GPU: {gpu_info}")
        else:
            click.echo("  - GPU: 未检测到")
    except FileNotFoundError:
        click.echo("  - GPU: nvidia-smi 不可用")

    click.echo("")

    role = click.prompt("你的角色是", type=click.Choice(["master", "worker"]), default="master")
    master_host = click.prompt("Master IP", default=local_ip)

    servers = []
    if role == "master":
        auto_discover = click.confirm("是否自动扫描局域网发现 Worker", default=True)

        if auto_discover:
            click.echo("🔍 扫描中...")
            workers = discover_workers(subnet)

            if workers:
                click.echo(f"  发现 {len(workers)} 台 Worker:")
                for w in workers:
                    gpu_info = w.get("gpu", [{}])
                    model = gpu_info[0].get("gpu_model", "unknown") if gpu_info else "unknown"
                    count = len(gpu_info) if gpu_info else 0
                    name = click.prompt(
                        f"  - {w['host']} ({model} × {count}) 的名称",
                        default=f"server{len(servers)+1}"
                    )
                    servers.append({
                        "name": name,
                        "host": w["host"],
                        "user": click.prompt(f"  - {name} 的用户名", default=os.getenv("USER")),
                        "gpus": count,
                        "gpu_model": model
                    })
            else:
                click.echo("  未发现 Worker，可以稍后运行 'poolgpu discover' 添加")

    config = copy.deepcopy(DEFAULT_CONFIG)
    config["master"]["host"] = master_host

    if role == "worker":
        worker_name = click.prompt("Worker 名称", default="worker1")
        config["worker"]["name"] = worker_name

    if servers:
        config["servers"] = servers

    results_dir = click.prompt("任务结果保存目录", default=config["results"]["dir"])
    config["results"]["dir"] = results_dir

    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_file = get_config_path("user")

    with open(config_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    click.echo("")
    click.echo(f"✅ 配置已保存到 {config_file}")


@cli.command()
@click.option("--subnet", help="指定扫描网段 (如 192.168.1.0/24)")
def discover(subnet):
    """自动发现 Worker"""
    if subnet is None:
        subnet = get_local_subnet()

    click.echo(f"🔍 扫描 {subnet}...")

    workers = discover_workers(subnet)

    if not workers:
        click.echo("未发现 Worker")
        return

    click.echo(f"发现 {len(workers)} 台 Worker:")
    for w in workers:
        gpu_info = w.get("gpu", [{}])
        model = gpu_info[0].get("gpu_model", "unknown") if gpu_info else "unknown"
        count = len(gpu_info) if gpu_info else 0
        click.echo(f"  - {w['host']} ({model} × {count})")

    if click.confirm("将发现的 Worker 添加到配置"):
        config = load_config(merge_project=False)

        existing_hosts = {s["host"] for s in config.get("servers", [])}
        new_workers = [w for w in workers if w["host"] not in existing_hosts]

        for w in new_workers:
            gpu_info = w.get("gpu", [{}])
            model = gpu_info[0].get("gpu_model", "unknown") if gpu_info else "unknown"
            count = len(gpu_info) if gpu_info else 0
            name = click.prompt(
                f"  - {w['host']} 的名称",
                default=f"server{len(config.get('servers', []))+1}"
            )

            config.setdefault("servers", []).append({
                "name": name,
                "host": w["host"],
                "user": click.prompt(f"  - {name} 的用户名", default=os.getenv("USER")),
                "gpus": count,
                "gpu_model": model
            })

        import yaml
        config_file = get_config_path("user")
        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        click.echo(f"✅ 已添加 {len(new_workers)} 台 Worker 到配置")


@cli.group()
def start():
    """启动服务"""
    PID_DIR.mkdir(parents=True, exist_ok=True)


@start.command()
@click.option("--daemon", is_flag=True, help="后台运行")
def master(daemon):
    """启动 Master"""
    config = load_config()
    host = config["master"]["host"]
    port = config["master"]["port"]
    web_port = config["master"]["web_port"]

    click.echo(f"🚀 PoolGPU Master 启动中...")
    click.echo(f"  - API: http://{host}:{port}")
    click.echo(f"  - Web UI: http://{host}:{web_port}")

    cmd = ["poolgpu-master"]

    if daemon:
        pid_file = PID_DIR / "master.pid"
        log_handle = open(PID_DIR / "master.log", "w")
        proc = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        log_handle.close()
        pid_file.write_text(str(proc.pid))
        click.echo(f"  - PID: {proc.pid}")
        click.echo(f"  - 日志: {PID_DIR / 'master.log'}")
    else:
        os.execvp(cmd[0], cmd)


@start.command()
@click.argument("name")
@click.option("--daemon", is_flag=True, help="后台运行")
def worker(name, daemon):
    """启动 Worker"""
    config = load_config()

    server = None
    for s in config.get("servers", []):
        if s["name"] == name:
            server = s
            break

    if not server:
        click.echo(f"错误: 未找到 Worker '{name}'")
        return

    click.echo(f"🚀 PoolGPU Worker [{name}] 启动中...")
    click.echo(f"  - API: http://{server['host']}:{config['worker']['port']}")
    click.echo(f"  - GPU: {server.get('gpu_model', 'unknown')} × {server.get('gpus', 0)}")

    cmd = ["poolgpu-worker", name]

    if daemon:
        pid_file = PID_DIR / f"worker-{name}.pid"
        log_handle = open(PID_DIR / f"worker-{name}.log", "w")
        proc = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        log_handle.close()
        pid_file.write_text(str(proc.pid))
        click.echo(f"  - PID: {proc.pid}")
        click.echo(f"  - 日志: {PID_DIR / f'worker-{name}.log'}")
    else:
        os.execvp(cmd[0], cmd)


@cli.command()
@click.argument("role", type=click.Choice(["master", "worker"]))
@click.argument("name", required=False)
def stop(role, name):
    """停止服务"""
    if role == "master":
        pid_file = PID_DIR / "master.pid"
    else:
        if not name:
            click.echo("错误: 请指定 Worker 名称")
            return
        pid_file = PID_DIR / f"worker-{name}.pid"

    if not pid_file.exists():
        click.echo(f"错误: 未找到 {role} 进程")
        return

    pid = int(pid_file.read_text().strip())

    try:
        os.kill(pid, signal.SIGTERM)
        click.echo(f"✅ 已停止 {role} 进程 (PID: {pid})")
        pid_file.unlink()
    except ProcessLookupError:
        click.echo(f"警告: 进程 {pid} 不存在")
        pid_file.unlink()
    except Exception as e:
        click.echo(f"错误: {e}")


if __name__ == "__main__":
    cli()
