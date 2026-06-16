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
