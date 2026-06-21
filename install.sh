#!/bin/bash
# PoolGPU 一键安装脚本
# 用法: curl -fsSL https://raw.githubusercontent.com/Taiowaz/PoolGPU/dev/install.sh | bash

set -e

INSTALL_DIR="$HOME/.local/share/poolgpu"
BIN_DIR="$HOME/.local/bin"
VENV_DIR="$INSTALL_DIR/venv"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

info() { echo -e "${GREEN}✓${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; exit 1; }

echo "=== PoolGPU 安装 ==="
echo ""

# 1. 检查 Python
if ! command -v python3 &> /dev/null; then
    error "未找到 python3"
fi
info "Python $(python3 --version | cut -d' ' -f2)"

# 2. 创建 venv 并安装
mkdir -p "$INSTALL_DIR" "$BIN_DIR"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/pip" install --upgrade pip -q 2>/dev/null
"$VENV_DIR/bin/pip" install git+https://github.com/Taiowaz/PoolGPU.git@dev -q
info "PoolGPU 安装完成"

# 3. 创建命令入口
cat > "$BIN_DIR/poolgpu" << 'EOF'
#!/bin/bash
exec "$HOME/.local/share/poolgpu/venv/bin/poolgpu" "$@"
EOF
chmod +x "$BIN_DIR/poolgpu"

cat > "$BIN_DIR/poolgpu-worker" << 'EOF'
#!/bin/bash
exec "$HOME/.local/share/poolgpu/venv/bin/poolgpu-worker" "$@"
EOF
chmod +x "$BIN_DIR/poolgpu-worker"

info "命令已安装"

# 4. 配置 PATH
if ! grep -q '\.local/bin' ~/.bashrc 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    info "PATH 已配置"
fi

echo ""
info "安装完成！"
