#!/bin/bash
# PoolGPU 更新脚本

set -e

INSTALL_DIR="$HOME/.local/share/poolgpu"
VENV_DIR="$INSTALL_DIR/venv"
REPO_DIR="$HOME/PoolGPU"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

echo "=== PoolGPU 更新 ==="
echo ""

# 1. 检查仓库是否存在
if [ ! -d "$REPO_DIR/.git" ]; then
    echo "错误: 未找到仓库 $REPO_DIR"
    echo "请先克隆仓库: git clone git@github.com:Taiowaz/PoolGPU.git ~/PoolGPU"
    exit 1
fi

# 2. 拉取最新代码
cd "$REPO_DIR"
git pull origin dev
info "代码已更新"

# 3. 重新安装
"$VENV_DIR/bin/pip" install -e . -q 2>/dev/null
info "依赖已更新"

echo ""
info "更新完成！"
echo ""
echo "如果遇到问题，可以重新安装："
echo "  bash install.sh"
