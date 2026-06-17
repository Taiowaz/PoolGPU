"""PoolGPU 主启动入口"""

import sys
import argparse
from shared.config import load_config
from scheduler.scheduler import Scheduler
from scheduler.master_api import init_master_api, run_master_api
from worker.worker import run_worker


def master_main():
    """poolgpu-master 命令入口"""
    config = load_config()
    init_master_api()
    master_host = config["master"]["host"]
    master_port = config["master"]["port"]
    web_port = config["master"]["web_port"]
    print(f"Master API: http://{master_host}:{master_port}")
    print(f"Web UI: http://{master_host}:{web_port}")
    run_master_api(master_host, master_port)


def worker_main():
    """poolgpu-worker 命令入口"""
    parser = argparse.ArgumentParser(description="PoolGPU Worker")
    parser.add_argument("server", help="服务器名称")
    args = parser.parse_args()
    run_worker(args.server)


def main():
    parser = argparse.ArgumentParser(description="PoolGPU - GPU 资源池调度系统")
    parser.add_argument("role", choices=["master", "worker"], help="启动角色")
    parser.add_argument("--server", help="Worker 服务器名称（仅 worker 角色需要）")

    args = parser.parse_args()
    config = load_config()

    if args.role == "master":
        master_main()
    elif args.role == "worker":
        if not args.server:
            print("错误: worker 角色需要 --server 参数")
            sys.exit(1)
        worker_main()


if __name__ == "__main__":
    main()
