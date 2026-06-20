# Config Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify PoolGPU deployment with one-click install, smart wizard, and auto-discovery

**Architecture:** Layered command structure (install → init → discover → start) with user-level config at `~/.local/share/poolgpu/config/config.yaml`

**Tech Stack:** Python 3.8+, click, socket, HTTP (requests), PyYAML

## Global Constraints

- Python 3.8+ required
- User-level installation (no sudo)
- Config priority: project/config.yaml > ~/.local/share/poolgpu/config/config.yaml > defaults
- Port 8090 for Worker API, 8080 for Master API, 5000 for Web UI

---

## File Structure

```
poolgpu/
├── shared/
│   ├── config.py          # MODIFY: add multi-level config loading
│   └── discovery.py       # CREATE: network discovery logic
├── cli/
│   └── main.py            # MODIFY: add init, discover, start, stop commands
├── scheduler/
│   └── master_api.py      # MODIFY: use new config loading
├── worker/
│   └── worker.py          # MODIFY: use new config loading
├── install.sh             # CREATE: one-click install script
└── tests/
    └── test_config.py     # CREATE: config tests
```

---

### Task 1: Multi-level Config Loading

**Files:**
- Modify: `shared/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `load_config(merge_project=True) -> dict`, `get_config_path(level="user") -> Path`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import os
import tempfile
from pathlib import Path
from shared.config import load_config, get_config_path, USER_CONFIG_DIR

def test_user_config_path():
    path = get_config_path("user")
    assert path == Path.home() / ".local/share/poolgpu/config/config.yaml"

def test_project_config_path():
    path = get_config_path("project")
    assert path.name == "config.yaml"

def test_load_config_returns_dict():
    config = load_config(merge_project=False)
    assert isinstance(config, dict)
    assert "master" in config

def test_config_merge_priority():
    # Create temp user config with override
    with tempfile.TemporaryDirectory() as tmpdir:
        user_config = Path(tmpdir) / "config.yaml"
        user_config.write_text("master:\n  port: 9999\n")
        
        # Mock USER_CONFIG_DIR
        import shared.config
        original = shared.config.USER_CONFIG_DIR
        shared.config.USER_CONFIG_DIR = Path(tmpdir)
        
        config = load_config(merge_project=False)
        assert config["master"]["port"] == 9999
        
        shared.config.USER_CONFIG_DIR = original
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/handb/PoolGPU && python -m pytest tests/test_config.py -v`
Expected: FAIL with ImportError or AssertionError

- [ ] **Step 3: Write minimal implementation**

```python
# shared/config.py - add these constants and functions at the top
from pathlib import Path
import yaml
from typing import Dict, Optional

USER_CONFIG_DIR = Path.home() / ".local/share/poolgpu/config"
USER_CONFIG_FILE = USER_CONFIG_DIR / "config.yaml"
PROJECT_CONFIG_FILE = Path(__file__).parent.parent / "config.yaml"

DEFAULT_CONFIG = {
    "master": {"host": "127.0.0.1", "port": 8080, "web_port": 5000},
    "worker": {"port": 8090, "report_interval": 10},
    "gpu_models": {"3090Ti": 1, "4090D": 2, "5090": 3},
    "results": {"dir": "/tmp/poolgpu/results"},
    "sync": {"code_dir": ".", "env_name": "myenv", "env_pack_path": "/tmp/myenv.tar.gz"},
    "servers": [],
    "retry": {"delay_seconds": 5, "max_attempts": 3},
}

def get_config_path(level: str = "user") -> Path:
    """Get config file path for specified level."""
    if level == "user":
        return USER_CONFIG_FILE
    elif level == "project":
        return PROJECT_CONFIG_FILE
    else:
        raise ValueError(f"Unknown config level: {level}")

def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def load_config(merge_project: bool = True) -> Dict:
    """Load config with priority: project > user > defaults."""
    config = DEFAULT_CONFIG.copy()
    
    # Load user config if exists
    if USER_CONFIG_FILE.exists():
        with open(USER_CONFIG_FILE) as f:
            user_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, user_config)
    
    # Load project config if exists and merge_project is True
    if merge_project and PROJECT_CONFIG_FILE.exists():
        with open(PROJECT_CONFIG_FILE) as f:
            project_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, project_config)
    
    return config
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/handb/PoolGPU && python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/config.py tests/test_config.py
git commit -m "feat: add multi-level config loading with merge priority"
```

---

### Task 2: Create install.sh

**Files:**
- Create: `install.sh`

**Interfaces:**
- Produces: Executable install script at project root

- [ ] **Step 1: Create the install script**

```bash
#!/bin/bash
# PoolGPU 一键安装脚本
# 用法: curl -fsSL https://raw.githubusercontent.com/Taiowaz/PoolGPU/main/install.sh | bash

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
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x /home/handb/PoolGPU/install.sh`
Expected: File becomes executable

- [ ] **Step 3: Commit**

```bash
git add install.sh
git commit -m "feat: add one-click install script"
```

---

### Task 3: Add Discovery Module

**Files:**
- Create: `shared/discovery.py`
- Create: `tests/test_discovery.py`

**Interfaces:**
- Produces: `discover_workers(subnet: str, timeout: float = 1.0) -> list[dict]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_discovery.py
from unittest.mock import patch, MagicMock
from shared.discovery import discover_workers, get_local_subnet, check_worker_health

def test_get_local_subnet():
    subnet = get_local_subnet()
    assert "/" in subnet  # Should be like "192.168.1.0/24"

def test_check_worker_health_success():
    with patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"status": "ok", "gpus": 2}
        
        result = check_worker_health("192.168.1.100", 8090)
        assert result is not None
        assert result["gpus"] == 2

def test_check_worker_health_failure():
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("Connection refused")
        
        result = check_worker_health("192.168.1.100", 8090)
        assert result is None

def test_discover_workers():
    with patch('shared.discovery.check_worker_health') as mock_check:
        mock_check.side_effect = lambda h, p: {"host": h, "gpus": 2} if h.endswith("100") else None
        
        workers = discover_workers("192.168.1.0/24", timeout=0.1)
        assert len(workers) == 1
        assert workers[0]["host"] == "192.168.1.100"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/handb/PoolGPU && python -m pytest tests/test_discovery.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

```python
# shared/discovery.py
import socket
import ipaddress
import concurrent.futures
import requests
from typing import List, Dict, Optional

WORKER_PORT = 8090
WORKER_API_HEALTH = "/api/health"
WORKER_API_GPU = "/api/gpu"

def get_local_subnet() -> str:
    """Get local machine's subnet in CIDR notation."""
    # Connect to external address to find local IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    finally:
        s.close()
    
    # Assume /24 subnet
    ip = ipaddress.ip_address(local_ip)
    network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
    return str(network)

def check_worker_health(host: str, port: int = WORKER_PORT, timeout: float = 1.0) -> Optional[Dict]:
    """Check if a host is running a PoolGPU Worker."""
    try:
        response = requests.get(
            f"http://{host}:{port}{WORKER_API_HEALTH}",
            timeout=timeout
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

def check_worker_gpu(host: str, port: int = WORKER_PORT, timeout: float = 1.0) -> Optional[Dict]:
    """Get GPU info from a worker."""
    try:
        response = requests.get(
            f"http://{host}:{port}{WORKER_API_GPU}",
            timeout=timeout
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

def _scan_host(args):
    """Scan a single host (for thread pool)."""
    host, port, timeout = args
    health = check_worker_health(host, port, timeout)
    if health:
        gpu_info = check_worker_gpu(host, port, timeout)
        return {
            "host": host,
            "port": port,
            "health": health,
            "gpu": gpu_info
        }
    return None

def discover_workers(subnet: str = None, port: int = WORKER_PORT, timeout: float = 1.0) -> List[Dict]:
    """Discover PoolGPU workers on the network."""
    if subnet is None:
        subnet = get_local_subnet()
    
    network = ipaddress.ip_network(subnet, strict=False)
    
    # Prepare scan targets
    targets = [(str(ip), port, timeout) for ip in network.hosts()]
    
    # Concurrent scan
    workers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        results = executor.map(_scan_host, targets)
        for result in results:
            if result:
                workers.append(result)
    
    return workers
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/handb/PoolGPU && python -m pytest tests/test_discovery.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/discovery.py tests/test_discovery.py
git commit -m "feat: add network discovery module for worker detection"
```

---

### Task 4: Add CLI Commands (init, discover, start, stop)

**Files:**
- Modify: `cli/main.py`

**Interfaces:**
- Consumes: `load_config()`, `discover_workers()`, `get_config_path()`

- [ ] **Step 1: Add init command**

```python
# cli/main.py - add at the top
import os
import signal
import subprocess
from pathlib import Path
from shared.config import load_config, get_config_path, USER_CONFIG_DIR, _deep_merge, DEFAULT_CONFIG
from shared.discovery import discover_workers, get_local_subnet

# Add after existing commands

@cli.command()
def init():
    """智能配置向导"""
    import yaml
    
    click.echo("🔍 检测本机信息...")
    
    # Detect IP
    subnet = get_local_subnet()
    local_ip = str(list(ipaddress.ip_network(subnet).hosts())[0]) if subnet else "127.0.0.1"
    click.echo(f"  - IP: {local_ip}")
    
    # Detect GPU
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,count", "--format=csv,noheader"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            gpu_info = result.stdout.strip().split("\n")[0]
            click.echo(f"  - GPU: {gpu_info}")
        else:
            click.echo("  - GPU: 未检测到")
    except FileNotFoundError:
        click.echo("  - GPU: nvidia-smi 不可用")
    
    click.echo("")
    
    # Role selection
    role = click.prompt("你的角色是", type=click.Choice(["master", "worker"]), default="master")
    
    # Master IP
    master_host = click.prompt("Master IP", default=local_ip)
    
    # Auto discover
    if role == "master":
        auto_discover = click.confirm("是否自动扫描局域网发现 Worker", default=True)
        
        servers = []
        if auto_discover:
            click.echo("🔍 扫描中...")
            subnet = get_local_subnet()
            workers = discover_workers(subnet)
            
            if workers:
                click.echo(f"  发现 {len(workers)} 台 Worker:")
                for w in workers:
                    gpu_info = w.get("gpu", [{}])
                    model = gpu_info[0].get("gpu_model", "unknown") if gpu_info else "unknown"
                    count = len(gpu_info) if gpu_info else 0
                    name = click.prompt(f"  - {w['host']} ({model} × {count}) 的名称", default=f"server{len(servers)+1}")
                    servers.append({
                        "name": name,
                        "host": w["host"],
                        "user": click.prompt(f"  - {name} 的用户名", default=os.getenv("USER")),
                        "gpus": count,
                        "gpu_model": model
                    })
            else:
                click.echo("  未发现 Worker，可以稍后运行 'poolgpu discover' 添加")
    
    # Build config
    config = DEFAULT_CONFIG.copy()
    config["master"]["host"] = master_host
    
    if role == "worker":
        worker_name = click.prompt("Worker 名称", default="worker1")
        config["worker"]["name"] = worker_name
    
    if servers:
        config["servers"] = servers
    
    # Results dir
    results_dir = click.prompt("任务结果保存目录", default=config["results"]["dir"])
    config["results"]["dir"] = results_dir
    
    # Save config
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_file = get_config_path("user")
    
    with open(config_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    click.echo("")
    click.echo(f"✅ 配置已保存到 {config_file}")
```

- [ ] **Step 2: Add discover command**

```python
# cli/main.py - add after init command

@cli.command()
@click.option("--update", is_flag=True, help="更新现有配置")
@click.option("--subnet", help="指定扫描网段 (如 192.168.1.0/24)")
def discover(update, subnet):
    """自动发现 Worker"""
    from shared.discovery import discover_workers, get_local_subnet
    
    if subnet is None:
        subnet = get_local_subnet()
    
    click.echo(f"🔍 扫描 {subnet}...")
    
    workers = discover_workers(subnet)
    
    if not workers:
        click.echo("未发现 Worker")
        return
    
    click.echo(f"发现 {len(workers)} 台 Worker:")
    for w in workers:
        gpu_info = w.get("gpu", [{}])
        model = gpu_info[0].get("gpu_model", "unknown") if gpu_info else "unknown"
        count = len(gpu_info) if gpu_info else 0
        click.echo(f"  - {w['host']} ({model} × {count})")
    
    if click.confirm("将发现的 Worker 添加到配置"):
        config = load_config(merge_project=False)
        
        existing_hosts = {s["host"] for s in config.get("servers", [])}
        new_workers = [w for w in workers if w["host"] not in existing_hosts]
        
        for w in new_workers:
            gpu_info = w.get("gpu", [{}])
            model = gpu_info[0].get("gpu_model", "unknown") if gpu_info else "unknown"
            count = len(gpu_info) if gpu_info else 0
            name = click.prompt(f"  - {w['host']} 的名称", default=f"server{len(config.get('servers', []))+1}")
            
            config.setdefault("servers", []).append({
                "name": name,
                "host": w["host"],
                "user": click.prompt(f"  - {name} 的用户名", default=os.getenv("USER")),
                "gpus": count,
                "gpu_model": model
            })
        
        import yaml
        config_file = get_config_path("user")
        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        click.echo(f"✅ 已添加 {len(new_workers)} 台 Worker 到配置")
```

- [ ] **Step 3: Add start/stop commands**

```python
# cli/main.py - add after discover command

PID_DIR = Path.home() / ".local/share/poolgpu/pids"

@cli.group()
def start():
    """启动服务"""
    PID_DIR.mkdir(parents=True, exist_ok=True)

@start.command()
@click.option("--daemon", is_flag=True, help="后台运行")
def master(daemon):
    """启动 Master"""
    config = load_config()
    host = config["master"]["host"]
    port = config["master"]["port"]
    web_port = config["master"]["web_port"]
    
    click.echo(f"🚀 PoolGPU Master 启动中...")
    click.echo(f"  - API: http://{host}:{port}")
    click.echo(f"  - Web UI: http://{host}:{web_port}")
    
    cmd = ["poolgpu-master"]
    
    if daemon:
        pid_file = PID_DIR / "master.pid"
        proc = subprocess.Popen(
            cmd,
            stdout=open(PID_DIR / "master.log", "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        pid_file.write_text(str(proc.pid))
        click.echo(f"  - PID: {proc.pid}")
        click.echo(f"  - 日志: {PID_DIR / 'master.log'}")
    else:
        os.execvp(cmd[0], cmd)

@start.command()
@click.argument("name")
@click.option("--daemon", is_flag=True, help="后台运行")
def worker(name, daemon):
    """启动 Worker"""
    config = load_config()
    
    server = None
    for s in config.get("servers", []):
        if s["name"] == name:
            server = s
            break
    
    if not server:
        click.echo(f"错误: 未找到 Worker '{name}'")
        return
    
    click.echo(f"🚀 PoolGPU Worker [{name}] 启动中...")
    click.echo(f"  - API: http://{server['host']}:{config['worker']['port']}")
    click.echo(f"  - GPU: {server.get('gpu_model', 'unknown')} × {server.get('gpus', 0)}")
    
    cmd = ["poolgpu-worker", name]
    
    if daemon:
        pid_file = PID_DIR / f"worker-{name}.pid"
        proc = subprocess.Popen(
            cmd,
            stdout=open(PID_DIR / f"worker-{name}.log", "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        pid_file.write_text(str(proc.pid))
        click.echo(f"  - PID: {proc.pid}")
        click.echo(f"  - 日志: {PID_DIR / f'worker-{name}.log'}")
    else:
        os.execvp(cmd[0], cmd)

@cli.command()
@click.argument("role", type=click.Choice(["master", "worker"]))
@click.argument("name", required=False)
def stop(role, name):
    """停止服务"""
    if role == "master":
        pid_file = PID_DIR / "master.pid"
    else:
        if not name:
            click.echo("错误: 请指定 Worker 名称")
            return
        pid_file = PID_DIR / f"worker-{name}.pid"
    
    if not pid_file.exists():
        click.echo(f"错误: 未找到 {role} 进程")
        return
    
    pid = int(pid_file.read_text().strip())
    
    try:
        os.kill(pid, signal.SIGTERM)
        click.echo(f"✅ 已停止 {role} 进程 (PID: {pid})")
        pid_file.unlink()
    except ProcessLookupError:
        click.echo(f"警告: 进程 {pid} 不存在")
        pid_file.unlink()
    except Exception as e:
        click.echo(f"错误: {e}")
```

- [ ] **Step 4: Test commands manually**

Run: `cd /home/handb/PoolGPU && python -m cli.main --help`
Expected: Shows all commands including init, discover, start, stop

- [ ] **Step 5: Commit**

```bash
git add cli/main.py
git commit -m "feat: add init, discover, start, stop CLI commands"
```

---

### Task 5: Update Existing Commands to Use New Config

**Files:**
- Modify: `scheduler/master_api.py`
- Modify: `worker/worker.py`

**Interfaces:**
- Consumes: `load_config()` from shared/config.py

- [ ] **Step 1: Update scheduler/master_api.py**

```python
# scheduler/master_api.py - find the config loading line and replace
# Old:
# config = yaml.safe_load(open("config.yaml"))
# New:
from shared.config import load_config
config = load_config()
```

- [ ] **Step 2: Update worker/worker.py**

```python
# worker/worker.py - find the config loading line and replace
# Old:
# config = yaml.safe_load(open("config.yaml"))
# New:
from shared.config import load_config
config = load_config()
```

- [ ] **Step 3: Run existing tests to verify no regression**

Run: `cd /home/handb/PoolGPU && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add scheduler/master_api.py worker/worker.py
git commit -m "refactor: use multi-level config loading in scheduler and worker"
```

---

### Task 6: Integration Test

**Files:**
- Create: `tests/test_integration.py`

**Interfaces:**
- Tests end-to-end: install → init → discover → start

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
import tempfile
from pathlib import Path
from shared.config import load_config, USER_CONFIG_DIR, _deep_merge, DEFAULT_CONFIG

def test_full_config_lifecycle():
    """Test config creation, loading, and merging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock user config dir
        import shared.config
        original = shared.config.USER_CONFIG_DIR
        shared.config.USER_CONFIG_DIR = Path(tmpdir)
        shared.config.USER_CONFIG_FILE = Path(tmpdir) / "config.yaml"
        
        # Create user config
        user_config = {
            "master": {"host": "10.0.0.1", "port": 9999},
            "servers": [
                {"name": "server1", "host": "10.0.0.2", "user": "test", "gpus": 2, "gpu_model": "4090"}
            ]
        }
        
        import yaml
        with open(shared.config.USER_CONFIG_FILE, "w") as f:
            yaml.dump(user_config, f)
        
        # Load and verify merge
        config = load_config(merge_project=False)
        
        assert config["master"]["host"] == "10.0.0.1"
        assert config["master"]["port"] == 9999
        assert config["worker"]["port"] == 8090  # From defaults
        assert len(config["servers"]) == 1
        assert config["servers"][0]["name"] == "server1"
        
        # Restore
        shared.config.USER_CONFIG_DIR = original
```

- [ ] **Step 2: Run integration test**

Run: `cd /home/handb/PoolGPU && python -m pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test for config lifecycle"
```

---

## Implementation Order

1. **Task 1** (Config) → 2. **Task 2** (install.sh) → 3. **Task 3** (Discovery) → 4. **Task 4** (CLI) → 5. **Task 5** (Update existing) → 6. **Task 6** (Integration test)

## Verification

After all tasks, run:
```bash
cd /home/handb/PoolGPU
python -m pytest tests/ -v
bash install.sh
poolgpu init
poolgpu discover
```
