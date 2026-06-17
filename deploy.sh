#!/bin/bash
# PoolGPU 部署脚本
# 用法: bash deploy.sh [master|worker] [server_name]

set -e

ROLE=${1:-"master"}
SERVER_NAME=${2:-"server1"}
VENV_DIR=".venv"

echo "=== PoolGPU 部署 ==="
echo "角色: $ROLE"
echo "服务器: $SERVER_NAME"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

echo "Python: $(python3 --version)"

# 尝试创建 venv，如果失败则安装依赖
if [ ! -d "$VENV_DIR" ]; then
    echo "创建虚拟环境..."
    if ! python3 -m venv "$VENV_DIR" 2>/dev/null; then
        echo "venv 创建失败，尝试安装 python3-venv..."
        sudo apt update -qq 2>/dev/null
        sudo apt install -y python3-venv python3-pip
        python3 -m venv "$VENV_DIR"
    fi
fi

# 验证 venv
if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "错误: 虚拟环境创建失败"
    echo "尝试手动运行: python3 -m venv .venv"
    exit 1
fi

echo "虚拟环境: OK"

# 安装
echo "安装 PoolGPU..."
"$VENV_DIR/bin/pip" install --upgrade pip -q 2>/dev/null || true
"$VENV_DIR/bin/pip" install -e . -q 2>/dev/null

# 验证
if "$VENV_DIR/bin/poolgpu" --help &> /dev/null; then
    echo "poolgpu 命令: OK"
else
    echo "警告: poolgpu 命令未安装成功"
fi

echo ""
echo "=== 部署完成 ==="
echo ""
echo "启动方式:"
if [ "$ROLE" = "worker" ]; then
    echo "  source $VENV_DIR/bin/activate && poolgpu-worker $SERVER_NAME"
else
    echo "  source $VENV_DIR/bin/activate && poolgpu-master"
fi
