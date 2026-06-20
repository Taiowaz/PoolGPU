# PoolGPU 配置简化设计

## 目标

简化 PoolGPU 的部署和配置流程，实现开箱即用的体验。

## 核心设计决策

- **分层架构**：安装、配置、发现、启动分离为独立命令
- **用户级安装**：不需要 sudo，不影响其他用户
- **自动发现 + 智能向导**：端口扫描发现 Worker，向导只问必要问题
- **一键安装脚本**：自动处理 Python 检查、venv 创建、PATH 配置

## 命令结构

```
poolgpu
├── install.sh          # 一键安装脚本（独立于 Python 包）
├── poolgpu init        # 智能配置向导
├── poolgpu discover    # 自动发现 Worker
├── poolgpu start       # 启动服务
│   ├── poolgpu start master
│   └── poolgpu start worker [name]
├── poolgpu stop        # 停止服务
├── poolgpu submit      # 提交任务
├── poolgpu status      # 查看状态
├── poolgpu gpu         # 查看 GPU
├── poolgpu sync        # 同步代码
├── poolgpu env-sync    # 同步环境
└── poolgpu config      # 配置管理
    ├── poolgpu config edit
    └── poolgpu config show
```

## 安装脚本 (install.sh)

```bash
#!/bin/bash
# PoolGPU 一键安装脚本
# 用法: curl -fsSL https://raw.githubusercontent.com/Taiowaz/PoolGPU/main/install.sh | bash

set -e

INSTALL_DIR="$HOME/.local/share/poolgpu"
BIN_DIR="$HOME/.local/bin"
VENV_DIR="$INSTALL_DIR/venv"

# 1. 检查 Python 3.8+
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo "错误: 未找到 python3"
        exit 1
    fi
    version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if [[ "$(echo "$version < 3.8" | bc)" == "1" ]]; then
        echo "错误: 需要 Python 3.8+，当前版本 $version"
        exit 1
    fi
}

# 2. 创建目录结构
setup_dirs() {
    mkdir -p "$INSTALL_DIR" "$BIN_DIR"
}

# 3. 创建 venv 并安装
install_poolgpu() {
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install poolgpu  # 或从 git 安装
}

# 4. 创建 wrapper 脚本
create_wrapper() {
    cat > "$BIN_DIR/poolgpu" << 'EOF'
#!/bin/bash
exec "$HOME/.local/share/poolgpu/venv/bin/poolgpu" "$@"
EOF
    chmod +x "$BIN_DIR/poolgpu"
}

# 5. 检查 PATH
check_path() {
    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        echo ""
        echo "请将以下内容添加到 ~/.bashrc:"
        echo "export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
        echo "然后运行: source ~/.bashrc"
    fi
}

# 主流程
check_python
setup_dirs
install_poolgpu
create_wrapper
check_path

echo ""
echo "✅ 安装完成！"
echo "运行 'poolgpu init' 开始配置"
```

## 安装后目录结构

```
~/.local/share/poolgpu/
├── venv/                    # Python 虚拟环境
├── config/
│   └── config.yaml          # 用户级配置（init 后生成）
└── pids/                    # 进程 PID 文件（start --daemon 后生成）

~/.local/bin/
└── poolgpu                  # 命令入口（wrapper 脚本）
```

## poolgpu init 智能向导

```bash
$ poolgpu init

🔍 检测本机信息...
  - IP: 10.61.16.33
  - GPU: NVIDIA GeForce RTX 4090 D × 2
  - SSH: 已配置免密登录到 3 台服务器

? 你的角色是？ (Master/Worker)
> Master

? 确认 Master IP 为 10.61.16.33？ (Y/n)
> Y

? 是否自动扫描局域网发现 Worker？ (Y/n)
> Y

🔍 扫描中... 发现 2 台 Worker
  - 10.62.193.36 (5090 × 2) - server1
  - 10.62.193.37 (5090 × 2) - server2

? 确认添加这些 Worker？ (Y/n)
> Y

? 任务结果保存目录？ (/home/handb/poolgpu/results)
> Y

✅ 配置已保存到 ~/.local/share/poolgpu/config/config.yaml
```

### 自动检测能力

- **本机 IP**：通过 socket 获取
- **GPU 信息**：调用 `nvidia-smi --query-gpu=name,count --format=csv,noheader`
- **SSH 免密**：尝试 SSH 连接本机，检测是否需要密码输入
- **Worker 发现**：扫描局域网 8090 端口，调用 `/api/health` 验证

## poolgpu discover 自动发现

```bash
$ poolgpu discover

🔍 扫描局域网 10.61.16.0/24...
  - 10.61.16.33:8090 ✅ Worker (5090 × 2) - server1
  - 10.61.16.34:8090 ✅ Worker (5090 × 2) - server2
  - 10.61.16.35:8090 ❌ 连接超时

? 将发现的 Worker 添加到配置？ (Y/n)
> Y

✅ 已添加 2 台 Worker 到配置
```

### 实现逻辑

1. 获取本机 IP 和子网掩码，计算网段
2. 并发扫描 8090 端口（超时 1s）
3. 对开放端口调用 `GET /api/health` 验证是否为 PoolGPU Worker
4. 获取 GPU 信息用于展示
5. 交互式确认后写入配置

### 更新模式

```bash
$ poolgpu discover --update
# 重新扫描，与现有配置对比，提示新增/移除的 Worker
```

## poolgpu start 启动服务

```bash
# Master 节点
$ poolgpu start master
🚀 PoolGPU Master 启动中...
  - API: http://10.61.16.33:8080
  - Web UI: http://10.61.16.33:5000
  - 已发现 2 台 Worker

# Worker 节点
$ poolgpu start worker server1
🚀 PoolGPU Worker [server1] 启动中...
  - API: http://10.62.193.36:8090
  - GPU: 5090 × 2
  - 上报间隔: 10s

# 后台运行
$ poolgpu start master --daemon
$ poolgpu start worker server1 --daemon

# 停止
$ poolgpu stop master
$ poolgpu stop worker server1
```

### 进程管理

- 默认前台运行（方便调试）
- `--daemon` 后台运行，PID 写入 `~/.local/share/poolgpu/pids/`
- `poolgpu stop` 通过 PID 文件停止进程
- 不依赖 systemd，用户级进程管理

## 配置文件结构

```yaml
# ~/.local/share/poolgpu/config/config.yaml（用户级，主配置）
master:
  host: 10.61.16.33
  port: 8080
  web_port: 5000

servers:
  - name: server1
    host: 10.62.193.36
    user: handb
    gpus: 2
    gpu_model: '5090'
  - name: server2
    host: 10.62.193.37
    user: handb
    gpus: 2
    gpu_model: '5090'

results:
  dir: /home/handb/poolgpu/results

sync:
  code_dir: /home/handb/PoolGPU
  env_name: myenv
  env_pack_path: /tmp/myenv.tar.gz

gpu_models:
  '3090Ti': 1
  '4090D': 2
  '5090': 3
```

### 配置优先级

```
项目目录/config.yaml > ~/.local/share/poolgpu/config/config.yaml > 内置默认值
```

### 配置管理命令

```bash
poolgpu config show          # 显示当前生效的配置
poolgpu config edit          # 编辑项目级配置
poolgpu config set key value # 设置配置项
```

## 部署流程对比

### 之前

```bash
# 每台机器都要
git clone git@github.com:Taiowaz/PoolGPU.git
cd PoolGPU
bash deploy.sh master  # 或 worker
source .venv/bin/activate
python main.py master
# 手动编辑 config.yaml
# 手动配置 SSH 免密
```

### 之后

```bash
# 安装（每台机器执行一次）
curl -fsSL https://raw.githubusercontent.com/Taiowaz/PoolGPU/main/install.sh | bash
source ~/.bashrc

# Master 配置
poolgpu init
poolgpu start master

# Worker 配置
poolgpu init
poolgpu start worker server1
```

## 实现要点

1. **config 模块重构**：支持多级配置合并（用户级 + 项目级 + 默认值）
2. **discover 命令**：基于 socket 并发扫描 + HTTP 健康检查
3. **init 向导**：使用 click + 内置检测逻辑
4. **start/stop 命令**：基于 PID 文件的进程管理
5. **install.sh**：独立脚本，不依赖 Python 包

## 测试策略

1. 单元测试：配置合并逻辑、IP 计算、端口扫描
2. 集成测试：init 向导流程、discover 发现、start/stop 生命周期
3. 端到端测试：完整安装 → 配置 → 启动 → 提交任务

## 实现分期

建议分 3 期实现：

**P0（核心）**：config 模块重构 + install.sh + poolgpu init
**P1（发现）**：poolgpu discover + poolgpu start/stop
**P2（完善）**：poolgpu config 命令 + 向导优化 + 测试覆盖
