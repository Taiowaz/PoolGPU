#!/bin/bash
# PoolGPU 部署脚本
# 用法: bash deploy.sh [master|worker] [server_name]

set -e

ROLE=${1:-"master"}
SERVER_NAME=${2:-"server1"}

echo "=== PoolGPU 部署 ==="
echo "角色: $ROLE"
echo "服务器: $SERVER_NAME"

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv .venv
fi

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
echo "安装依赖..."
pip install -e . -q

if [ "$ROLE" = "worker" ]; then
    echo ""
    echo "=== Worker 部署完成 ==="
    echo "启动命令:"
    echo "  source .venv/bin/activate"
    echo "  python main.py worker --server $SERVER_NAME"
    echo ""
    echo "或者使用 systemd 服务:"
    echo "  sudo cp poolgpu-worker.service /etc/systemd/system/"
    echo "  sudo systemctl enable poolgpu-worker"
    echo "  sudo systemctl start poolgpu-worker"
else
    echo ""
    echo "=== Master 部署完成 ==="
    echo "启动命令:"
    echo "  source .venv/bin/activate"
    echo "  python main.py master"
    echo ""
    echo "或者使用 systemd 服务:"
    echo "  sudo cp poolgpu-master.service /etc/systemd/system/"
    echo "  sudo systemctl enable poolgpu-master"
    echo "  sudo systemctl start poolgpu-master"
fi
