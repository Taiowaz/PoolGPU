# PoolGPU 测试流程文档

## 环境要求

- 主服务器（Master）：运行调度器和 Web UI
- Worker 服务器：运行任务执行服务
- 所有服务器需要在同一网络，能互相访问

## 部署步骤

### 1. 下载代码

在所有服务器上执行：

```bash
cd ~
git clone git@github.com:Taiowaz/PoolGPU.git
cd PoolGPU
git checkout dev
```

### 2. 创建环境

```bash
sudo apt install python3-venv -y
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. 配置 SSH 免密（Master → Worker）

在 Master 上：

```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
ssh-copy-id handb@<Worker IP>
```

### 4. 更新配置

编辑 `config.yaml`，配置正确的 IP 地址：

```yaml
master:
  host: <Master IP>
  port: 8080

servers:
  - name: "server1"
    host: "<Worker IP>"
    user: "<Worker 用户名>"
    gpus: <GPU 数量>
    gpu_model: "<GPU 型号>"
```

### 5. 启动服务

**Master：**

```bash
source .venv/bin/activate
nohup poolgpu-master > poolgpu.log 2>&1 &
```

**Worker：**

```bash
source .venv/bin/activate
nohup poolgpu-worker <server_name> > poolgpu.log 2>&1 &
```

## 测试流程

### 测试 1：检查 GPU 状态

```bash
poolgpu gpu
```

预期输出：
```
  server1 (5090×2): 🟢 空闲 🟢 空闲
```

### 测试 2：简单任务测试

```bash
poolgpu submit --gpu 1 --name "simple_test" -- echo hello
poolgpu status
```

预期输出：
```
任务已提交: ID=1, 名称=simple_test, GPU=1
任务已调度: 服务器=server1, GPU=[0]
```

### 测试 3：长时间任务测试

```bash
poolgpu submit --gpu 1 --name "long_test" -- bash test_long_task.sh
watch -n 1 poolgpu status
```

任务运行 30 秒，可以观察状态变化。

### 测试 4：GPU 状态验证

```bash
poolgpu submit --gpu 1 --name "gpu_test" -- nvidia-smi
poolgpu status
```

这会分配 1 张 GPU 并运行 `nvidia-smi`，验证 GPU 分配是否正常。

### 测试 5：多 GPU 任务

```bash
poolgpu submit --gpu 2 --name "multi_gpu_test" -- bash -c "echo GPU: \$CUDA_VISIBLE_DEVICES && nvidia-smi"
poolgpu status
```

### 测试 6：Web UI 查看

浏览器访问：`http://<Master IP>:8080`

检查：
- GPU 状态显示正确
- 任务列表显示任务
- 通知记录显示任务完成
- 实时更新正常

### 测试 7：代码同步

```bash
poolgpu sync
```

预期输出：
```
代码同步结果:
服务器        状态       变更文件     耗时
---------------------------------------------
server1       ✅ success      5    1.2s
```

### 测试 8：任务提交时自动同步

```bash
poolgpu submit --sync --gpu 1 --name "sync_test" -- echo hello
```

### 测试 9：环境同步

```bash
poolgpu env-sync
```

### 测试 10：后台运行验证

```bash
# 查看进程
pgrep -f poolgpu-master
pgrep -f poolgpu-worker

# 查看日志
tail -f poolgpu.log
```

## 常见问题

### 问题 1：无法获取 GPU 状态

**原因：** Worker 未运行或防火墙阻挡

**解决：**
```bash
# 检查 Worker 是否运行
pgrep -f poolgpu-worker

# 开放防火墙
sudo ufw allow 8090
```

### 问题 2：任务一直显示 running

**原因：** Worker 没有收到任务或执行失败

**解决：**
```bash
# 检查 Worker 日志
tail -20 ~/PoolGPU/poolgpu.log

# 手动测试 Worker API
curl -X POST http://<Worker IP>:8090/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_id": 1, "command": "echo hello", "gpu_ids": [0]}'
```

### 问题 3：Web UI 404

**原因：** Flask 模板路径问题

**解决：** 确保使用最新代码：
```bash
git pull
pip install -e .
kill $(pgrep -f poolgpu-master)
nohup poolgpu-master > poolgpu.log 2>&1 &
```

### 问题 4：SQLite 线程错误

**原因：** SQLite 连接跨线程使用

**解决：** 确保代码包含 `check_same_thread=False`

### 问题 5：端口被占用

**解决：**
```bash
# 查看占用端口的进程
lsof -i :8090

# 杀掉进程
kill $(lsof -t -i :8090)
```

### 问题 6：GPU 没有被使用

**说明：** `--gpu` 参数只是分配 GPU，任务本身需要是 CUDA 程序才能使用 GPU。

```bash
# 测试 GPU 分配（不实际使用 GPU）
poolgpu submit --gpu 1 --name "gpu_test" -- nvidia-smi

# 实际使用 GPU（需要安装 PyTorch）
poolgpu submit --gpu 1 --name "torch_test" -- python3 -c "import torch; print(torch.cuda.get_device_name(0))"
```

## 停止服务

```bash
# 停止 Master
kill $(pgrep -f poolgpu-master)

# 停止 Worker
kill $(pgrep -f poolgpu-worker)
```

## 查看日志

```bash
# 实时查看日志
tail -f poolgpu.log

# 查看最近 50 行
tail -50 poolgpu.log

# 查看错误日志
grep -i error poolgpu.log
```
