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

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    echo "请先安装: sudo apt install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
echo "Python 版本: $PYTHON_VERSION"

# 检查 python3-venv
if ! python3 -m venv --help &> /dev/null 2>&1; then
    echo "python3-venv 未安装，正在安装（需要 sudo 权限）..."
    sudo apt update -qq
    sudo apt install -y "python3${PYTHON_VERSION}-venv"
fi

# 创建虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo "创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

# 验证虚拟环境
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "错误: 虚拟环境创建失败"
    exit 1
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

# 安装依赖
echo "安装依赖..."
pip install --upgrade pip -q 2>/dev/null
pip install -e . -q 2>/dev/null

# 验证安装
if command -v poolgpu &> /dev/null; then
    echo "poolgpu 命令安装成功"
else
    echo "警告: poolgpu 命令未找到，尝试重新安装..."
    pip install -e . -q 2>/dev/null
fi

echo ""
echo "=== 部署完成 ==="
echo ""
echo "使用方法:"
echo "  1. 激活虚拟环境: source $VENV_DIR/bin/activate"
echo "  2. 启动服务:"
if [ "$ROLE" = "worker" ]; then
    echo "     poolgpu-worker $SERVER_NAME"
else
    echo "     poolgpu-master"
fi
echo "  3. 查看帮助: poolgpu --help"
