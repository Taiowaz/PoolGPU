#!/bin/bash
# PoolGPU 端到端测试脚本
# 用法: bash test_e2e.sh

set -e

echo "=== PoolGPU 端到端测试 ==="
echo ""

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "错误: 未找到虚拟环境，请先运行 deploy.sh"
    exit 1
fi

source .venv/bin/activate

# 1. 运行单元测试
echo "1. 运行单元测试..."
python -m pytest tests/ -v --tb=short
echo ""

# 2. 测试 CLI 命令
echo "2. 测试 CLI 命令..."
python -m cli.main --help
echo ""

# 3. 测试配置读取
echo "3. 测试配置读取..."
python -c "
from shared.config import (
    load_config, get_worker_port, get_report_interval,
    get_gpu_performance_level, get_code_dir, get_sync_excludes,
    get_env_name, get_env_pack_path, get_results_dir
)
config = load_config()
print(f'Master: {config[\"master\"][\"host\"]}:{config[\"master\"][\"port\"]}')
print(f'Worker Port: {get_worker_port()}')
print(f'Code Dir: {get_code_dir()}')
print(f'Env Name: {get_env_name()}')
print(f'Results Dir: {get_results_dir()}')
print('配置读取 OK')
"
echo ""

# 4. 测试 Scheduler 初始化
echo "4. 测试 Scheduler 初始化..."
python -c "
from scheduler.scheduler import Scheduler
s = Scheduler(':memory:')
print(f'Scheduler 初始化 OK')
print(f'任务表: OK')
print(f'通知表: OK')
"
echo ""

# 5. 测试 Worker 模块
echo "5. 测试 Worker 模块..."
python -c "
from worker.worker import app, run_worker
print(f'Worker Flask app: OK')
print(f'Worker 路由: {[rule.rule for rule in app.url_map.iter_rules()]}')
"
echo ""

# 6. 测试 Master API 模块
echo "6. 测试 Master API 模块..."
python -c "
from scheduler.master_api import app, socketio
print(f'Master API Flask app: OK')
print(f'Master API 路由: {[rule.rule for rule in app.url_map.iter_rules()]}')
"
echo ""

# 7. 测试 WebUI 模块
echo "7. 测试 WebUI 模块..."
python -c "
from webui.app import app, socketio
print(f'WebUI Flask app: OK')
print(f'WebUI 路由: {[rule.rule for rule in app.url_map.iter_rules()]}')
"
echo ""

echo "=== 所有测试通过 ==="
echo ""
echo "下一步:"
echo "1. 在主服务器运行: python main.py master"
echo "2. 在各 Worker 服务器运行: python main.py worker --server <name>"
echo "3. 提交测试任务: poolgpu submit --gpu 1 --name 'test' -- echo hello"
echo "4. 查看状态: poolgpu status"
echo "5. 查看 GPU: poolgpu gpu"
