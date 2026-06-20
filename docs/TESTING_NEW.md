# PoolGPU 测试流程

## 前置条件

- Python 3.8+
- SSH 免密登录（Master → Worker）
- 所有机器在同一局域网

## 一、安装

### Master 节点

```bash
curl -fsSL https://raw.githubusercontent.com/Taiowaz/PoolGPU/dev/install.sh | bash
source ~/.bashrc
poolgpu init
poolgpu start master --daemon
```

### Worker 节点

```bash
curl -fsSL https://raw.githubusercontent.com/Taiowaz/PoolGPU/dev/install.sh | bash
source ~/.bashrc
poolgpu init
poolgpu start worker server1 --daemon
```

## 二、验证测试

```bash
# 查看 GPU 状态
poolgpu gpu

# 提交测试任务
poolgpu submit --gpu 1 --name "test" -- echo hello

# 查看任务状态
poolgpu status

# 查看 Web UI
# 浏览器打开 http://<Master IP>:5000
```

## 三、更新

```bash
curl -fsSL https://raw.githubusercontent.com/Taiowaz/PoolGPU/dev/update.sh | bash
```

## 四、卸载

```bash
curl -fsSL https://raw.githubusercontent.com/Taiowaz/PoolGPU/dev/uninstall.sh | bash
source ~/.bashrc
```

## 故障排查

### 命令找不到

```bash
source ~/.bashrc
```

### GPU 状态获取失败

```bash
# 检查 nvidia-smi
nvidia-smi

# 检查 Worker 是否运行
curl http://<Worker IP>:8090/api/health
```

### 任务失败

```bash
# 查看日志
tail -f ~/.local/share/poolgpu/pids/master.log
tail -f ~/.local/share/poolgpu/pids/worker-server1.log
```
