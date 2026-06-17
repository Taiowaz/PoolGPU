# PoolGPU 快速部署指南

## 前置条件

- Python 3.8+
- SSH 免密登录（Master → Worker）
- nvidia-smi（Worker 服务器）
- conda（如果使用环境同步）

## 部署步骤

### 1. 主服务器（Master）

```bash
# 克隆代码
git clone git@github.com:Taiowaz/PoolGPU.git
cd PoolGPU

# 运行部署脚本
bash deploy.sh master

# 启动 Master
source .venv/bin/activate
python main.py master
```

### 2. Worker 服务器

```bash
# 克隆代码
git clone git@github.com:Taiowaz/PoolGPU.git
cd PoolGPU

# 运行部署脚本
bash deploy.sh worker server1

# 启动 Worker
source .venv/bin/activate
python main.py worker --server server1
```

### 3. 配置 SSH 免密登录

在 Master 服务器上：

```bash
# 生成 SSH 密钥（如果没有）
ssh-keygen -t ed25519

# 复制公钥到各 Worker
ssh-copy-id albin@192.168.1.101
ssh-copy-id albin@192.168.1.102
ssh-copy-id albin@192.168.1.103
ssh-copy-id albin@192.168.1.104
ssh-copy-id albin@192.168.1.105
```

### 4. 配置 config.yaml

编辑 `config.yaml`，配置服务器信息：

```yaml
master:
  host: "192.168.1.100"  # Master 服务器 IP
  port: 8080
  web_port: 5000

servers:
  - name: "server1"
    host: "192.168.1.101"
    user: "albin"
    gpus: 2
    gpu_model: "4090D"
  # ... 其他服务器
```

## 测试

### 1. 运行端到端测试

```bash
bash test_e2e.sh
```

### 2. 提交测试任务

```bash
# 提交简单任务
poolgpu submit --gpu 1 --name "test_task" -- bash test_task.sh

# 查看状态
poolgpu status

# 查看 GPU
poolgpu gpu
```

### 3. 测试代码同步

```bash
# 同步代码到所有 Worker
poolgpu sync

# 提交任务时自动同步
poolgpu submit --sync --gpu 1 --name "train" -- bash train.sh
```

### 4. 测试环境同步

```bash
# 同步环境到所有 Worker
poolgpu env-sync
```

### 5. 测试 Web UI

浏览器打开: http://192.168.1.100:5000

## 使用 systemd 服务（可选）

### Master 服务

```bash
sudo cp poolgpu-master.service /etc/systemd/system/
sudo systemctl enable poolgpu-master
sudo systemctl start poolgpu-master
```

### Worker 服务

```bash
sudo cp poolgpu-worker@.service /etc/systemd/system/
sudo systemctl enable poolgpu-worker@server1
sudo systemctl start poolgpu-worker@server1
```

## 常见问题

### Worker 无法连接 Master

检查：
1. Master 是否已启动
2. 防火墙是否开放 8080 端口
3. config.yaml 中 Master IP 是否正确

### GPU 状态获取失败

检查：
1. nvidia-smi 是否可用
2. NVIDIA 驱动是否安装

### 代码同步失败

检查：
1. SSH 免密登录是否配置
2. rsync 是否安装
3. 代码目录权限
