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
    click.echo("环境同步功能将在后续迭代中实现")


if __name__ == "__main__":
    cli()
