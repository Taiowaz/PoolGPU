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
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
        info "虚拟环境创建完成"
    fi
    
    "$VENV_DIR/bin/pip" install --upgrade pip -q 2>/dev/null
    
    # 从当前目录或 git 安装
    if [ -f "setup.py" ]; then
        "$VENV_DIR/bin/pip" install -e . -q
    else
        "$VENV_DIR/bin/pip" install git+https://github.com/Taiowaz/PoolGPU.git -q
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
    info "命令入口创建完成"
}

# 5. 检查 PATH
check_path() {
    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        warn "请将以下内容添加到 ~/.bashrc:"
        echo "export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
        echo "然后运行: source ~/.bashrc"
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
check_path

echo ""
info "安装完成！"
echo ""
echo "下一步："
echo "  1. 确保 ~/.local/bin 在 PATH 中"
echo "  2. 运行 'poolgpu init' 开始配置"
