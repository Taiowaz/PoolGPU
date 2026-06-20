#!/bin/bash
# PoolGPU 卸载脚本

set -e

INSTALL_DIR="$HOME/.local/share/poolgpu"
BIN_DIR="$HOME/.local/bin"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

info() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${RED}✗${NC} $1"; }

echo "=== PoolGPU 卸载 ==="
echo ""

# 1. 停止运行中的服务
if [ -d "$INSTALL_DIR/pids" ]; then
    for pidfile in "$INSTALL_DIR/pids"/*.pid; do
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null && info "已停止进程 $pid" || true
            fi
            rm -f "$pidfile"
        fi
    done
fi

# 2. 删除命令入口
if [ -f "$BIN_DIR/poolgpu" ]; then
    rm -f "$BIN_DIR/poolgpu"
    info "已删除命令入口"
fi

# 3. 删除安装目录
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    info "已删除 $INSTALL_DIR"
fi

# 4. 清理 PATH
if grep -q '$HOME/.local/bin' ~/.bashrc 2>/dev/null; then
    sed -i '/$HOME\/.local\/bin/d' ~/.bashrc
    info "已从 ~/.bashrc 移除 PATH 配置"
fi

echo ""
info "卸载完成！"
