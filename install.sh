#!/bin/bash
# PoolGPU 一键安装脚本
# 用法: curl -fsSL https://raw.githubusercontent.com/Taiowaz/PoolGPU/dev/install.sh | bash

set -e

INSTALL_DIR="$HOME/.local/share/poolgpu"
BIN_DIR="$HOME/.local/bin"
VENV_DIR="$INSTALL_DIR/venv"
CONFIG_DIR="$INSTALL_DIR/config"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; exit 1; }

# 1. 检查 Python
check_python() {
    if ! command -v python3 &> /dev/null; then
        error "未找到 python3，请先安装 Python 3.8+"
    fi
    
    version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    major=$(echo $version | cut -d. -f1)
    minor=$(echo $version | cut -d. -f2)
    
    if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 8 ]); then
        error "需要 Python 3.8+，当前版本 $version"
    fi
    
    info "Python $version"
}

# 2. 创建目录
setup_dirs() {
    mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$CONFIG_DIR"
    info "目录创建完成"
}

# 3. 创建 venv 并安装
install_poolgpu() {
    # 如果 venv 已存在但有问题，重建
    if [ -d "$VENV_DIR" ] && ! "$VENV_DIR/bin/pip" --version &>/dev/null; then
        rm -rf "$VENV_DIR"
    fi
    
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
        info "虚拟环境创建完成"
    fi
    
    "$VENV_DIR/bin/pip" install --upgrade pip -q 2>/dev/null
    
    # 安装依赖
    "$VENV_DIR/bin/pip" install requests flask flask-socketio paramiko psutil click pyyaml -q
    
    # 从 git 安装 poolgpu
    "$VENV_DIR/bin/pip" install git+https://github.com/Taiowaz/PoolGPU.git@dev -q
    
    # 验证安装
    if ! "$VENV_DIR/bin/poolgpu" --help &>/dev/null; then
        error "安装失败，请检查网络连接"
    fi
    
    info "PoolGPU 安装完成"
}

# 4. 创建 wrapper 脚本
create_wrapper() {
    cat > "$BIN_DIR/poolgpu" << 'EOF'
#!/bin/bash
exec "$HOME/.local/share/poolgpu/venv/bin/poolgpu" "$@"
EOF
    chmod +x "$BIN_DIR/poolgpu"
    
    cat > "$BIN_DIR/poolgpu-master" << 'EOF'
#!/bin/bash
exec "$HOME/.local/share/poolgpu/venv/bin/poolgpu-master" "$@"
EOF
    chmod +x "$BIN_DIR/poolgpu-master"
    
    cat > "$BIN_DIR/poolgpu-worker" << 'EOF'
#!/bin/bash
exec "$HOME/.local/share/poolgpu/venv/bin/poolgpu-worker" "$@"
EOF
    chmod +x "$BIN_DIR/poolgpu-worker"
    
    info "命令入口创建完成"
}

# 5. 配置 PATH
setup_path() {
    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        if ! grep -q '\.local/bin' ~/.bashrc 2>/dev/null; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
            info "已添加 PATH 到 ~/.bashrc"
        fi
    else
        info "PATH 配置正确"
    fi
}

# 主流程
echo "=== PoolGPU 一键安装 ==="
echo ""
check_python
setup_dirs
install_poolgpu
create_wrapper
setup_path

echo ""
info "安装完成！"
echo "运行 'source ~/.bashrc && poolgpu init' 开始配置"
