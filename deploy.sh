#!/bin/bash
# PoolGPU 部署脚本
# 用法: bash deploy.sh [master|worker] [server_name]
#
# 功能:
#   - 自动安装系统依赖（需要 sudo 权限）
#   - 创建虚拟环境（不影响系统 Python）
#   - 安装 poolgpu 命令到虚拟环境
#   - 部署完成后可直接使用 poolgpu 命令

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

# 检查并安装 python3-venv（如果需要）
if [ ! -d "$VENV_DIR" ]; then
    if ! python3 -m venv --help &> /dev/null 2>&1; then
        echo "python3-venv 未安装，正在安装..."
        sudo apt update -qq
        sudo apt install -y python3${PYTHON_VERSION}-venv python3-pip
    fi

    echo "创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

# 安装依赖
echo "安装依赖..."
pip install --upgrade pip -q
pip install -e . -q

# 验证安装
if command -v poolgpu &> /dev/null; then
    echo "poolgpu 命令安装成功"
else
    echo "警告: poolgpu 命令未找到，尝试重新安装..."
    pip install -e . -q
fi

echo ""
echo "=== 部署完成 ==="
echo ""
echo "使用方法:"
echo "  1. 激活虚拟环境: source $VENV_DIR/bin/activate"
echo "  2. 启动服务:"
if [ "$ROLE" = "worker" ]; then
    echo "     poolgpu-worker $SERVER_NAME"
    echo "     或: python main.py worker --server $SERVER_NAME"
else
    echo "     poolgpu-master"
    echo "     或: python main.py master"
fi
echo ""
echo "  3. 查看帮助: poolgpu --help"
echo ""
echo "快速启动（无需每次 source）:"
if [ "$ROLE" = "worker" ]; then
    echo "  echo 'source $(pwd)/$VENV_DIR/bin/activate' >> ~/.bashrc"
else
    echo "  echo 'source $(pwd)/$VENV_DIR/bin/activate' >> ~/.bashrc"
fi
