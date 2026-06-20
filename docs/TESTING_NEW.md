# PoolGPU 新版测试流程

## 环境要求

- Python 3.8+
- SSH 免密登录（Master → Worker）
- nvidia-smi（Worker 服务器）
- 同一局域网

## 一、单元测试

### 1.1 运行所有测试

```bash
cd /home/handb/PoolGPU
python -m pytest tests/ -v
```

预期输出：
```
tests/test_config.py::test_user_config_path PASSED
tests/test_config.py::test_project_config_path PASSED
tests/test_config.py::test_load_config_returns_dict PASSED
tests/test_config.py::test_config_merge_priority PASSED
tests/test_discovery.py::test_get_local_subnet PASSED
tests/test_discovery.py::test_check_worker_health_success PASSED
tests/test_discovery.py::test_check_worker_health_failure PASSED
tests/test_discovery.py::test_discover_workers PASSED
tests/test_integration.py::test_full_config_lifecycle PASSED
...
=================== X passed in X.XXs ===================
```

### 1.2 单独运行配置测试

```bash
python -m pytest tests/test_config.py -v
```

### 1.3 单独运行发现模块测试

```bash
python -m pytest tests/test_discovery.py -v
```

### 1.4 单独运行集成测试

```bash
python -m pytest tests/test_integration.py -v
```

---

## 二、安装测试

### 2.1 测试安装脚本

```bash
cd /home/handb/PoolGPU
bash install.sh
```

预期输出：
```
=== PoolGPU 一键安装 ===

✓ Python 3.x.x
✓ 目录创建完成
✓ 虚拟环境创建完成
✓ PoolGPU 安装完成
✓ 命令入口创建完成
✓ PATH 配置正确

✅ 安装完成！

下一步：
  1. 确保 ~/.local/bin 在 PATH 中
  2. 运行 'poolgpu init' 开始配置
```

### 2.2 验证安装

```bash
# 检查命令是否可用
poolgpu --help

# 检查版本
poolgpu --version
```

---

## 三、配置测试

### 3.1 测试 init 向导（交互式）

```bash
poolgpu init
```

测试要点：
- [ ] 自动检测本机 IP
- [ ] 自动检测 GPU 信息
- [ ] 提示选择角色（Master/Worker）
- [ ] Master 模式下自动扫描 Worker
- [ ] 配置保存到 `~/.local/share/poolgpu/config/config.yaml`

### 3.2 手动测试配置文件

```bash
# 查看生成的配置
cat ~/.local/share/poolgpu/config/config.yaml

# 验证配置内容
poolgpu config show
```

### 3.3 测试配置优先级

```bash
# 创建项目级配置
cat > config.yaml << 'EOF'
master:
  port: 9999
EOF

# 验证项目级配置覆盖用户级
poolgpu config show | grep port
# 应显示 9999

# 清理
rm config.yaml
```

---

## 四、发现测试

### 4.1 测试网络发现

```bash
poolgpu discover
```

预期输出：
```
🔍 扫描 10.61.16.0/24...
发现 X 台 Worker:
  - 10.61.16.36 (5090 × 2)
  - 10.61.16.37 (5090 × 2)
将发现的 Worker 添加到配置？ [y/N]: y
✅ 已添加 2 台 Worker 到配置
```

### 4.2 测试指定网段发现

```bash
poolgpu discover --subnet 192.168.1.0/24
```

### 4.3 验证发现结果

```bash
# 查看配置中的服务器列表
poolgpu config show | grep -A 20 "servers:"
```

---

## 五、服务启动测试

### 5.1 测试前台启动

```bash
# 终端 1：启动 Master
poolgpu start master

# 终端 2：启动 Worker
poolgpu start worker server1
```

预期输出：
```
🚀 PoolGPU Master 启动中...
  - API: http://10.61.16.33:8080
  - Web UI: http://10.61.16.33:5000
```

### 5.2 测试后台启动

```bash
# 启动 Master（后台）
poolgpu start master --daemon

# 启动 Worker（后台）
poolgpu start worker server1 --daemon
```

### 5.3 验证进程

```bash
# 检查进程
pgrep -f poolgpu-master
pgrep -f poolgpu-worker

# 检查 PID 文件
ls -la ~/.local/share/poolgpu/pids/

# 查看日志
tail -f ~/.local/share/poolgpu/pids/master.log
```

### 5.4 测试停止服务

```bash
# 停止 Master
poolgpu stop master

# 停止 Worker
poolgpu stop worker server1

# 验证进程已停止
pgrep -f poolgpu-master  # 应无输出
pgrep -f poolgpu-worker  # 应无输出
```

---

## 六、功能测试

### 6.1 测试 GPU 状态

```bash
poolgpu gpu
```

预期输出：
```
  server1 (5090×2): 🟢 空闲 🟢 空闲
  server2 (5090×2): 🟢 空闲 🟢 空闲
```

### 6.2 测试提交任务

```bash
poolgpu submit --gpu 1 --name "test_task" -- echo hello
```

预期输出：
```
任务已提交: ID=1, 名称=test_task, GPU=1
任务已调度: 服务器=server1, GPU=[0]
```

### 6.3 测试查看状态

```bash
poolgpu status
```

预期输出：
```
ID    名称          GPU   状态          进度       服务器
------------------------------------------------------------
1     test_task     1     completed    100        server1
```

### 6.4 测试代码同步

```bash
poolgpu sync
```

### 6.5 测试 Web UI

浏览器访问：`http://<Master IP>:5000`

检查：
- [ ] GPU 状态显示正确
- [ ] 任务列表显示任务
- [ ] 通知记录显示任务完成

---

## 七、端到端测试

### 7.1 完整流程测试

```bash
# 1. 安装
bash install.sh

# 2. 配置（Master 节点）
poolgpu init
# 选择 Master，确认自动发现

# 3. 启动 Master
poolgpu start master --daemon

# 4. 配置（Worker 节点，另一台机器）
poolgpu init
# 选择 Worker

# 5. 启动 Worker
poolgpu start worker server1 --daemon

# 6. 回到 Master 测试
poolgpu gpu
poolgpu submit --gpu 1 --name "e2e_test" -- sleep 5
poolgpu status

# 7. 清理
poolgpu stop master
poolgpu stop worker server1
```

---

## 八、故障排查

### 8.1 命令未找到

```bash
# 检查 PATH
echo $PATH | grep -q "$HOME/.local/bin" && echo "PATH OK" || echo "PATH missing"

# 手动添加 PATH
export PATH="$HOME/.local/bin:$PATH"
```

### 8.2 配置文件不存在

```bash
# 检查配置目录
ls -la ~/.local/share/poolgpu/config/

# 重新运行 init
poolgpu init
```

### 8.3 发现不到 Worker

```bash
# 检查 Worker 是否运行
curl http://<Worker IP>:8090/api/health

# 检查防火墙
sudo ufw allow 8090

# 手动指定网段
poolgpu discover --subnet <网段>
```

### 8.4 服务启动失败

```bash
# 查看日志
tail -50 ~/.local/share/poolgpu/pids/master.log

# 检查端口占用
lsof -i :8080
lsof -i :8090

# 杀掉占用进程
kill $(lsof -t -i :8080)
```

---

## 九、清理测试环境

```bash
# 停止所有服务
poolgpu stop master
poolgpu stop worker server1

# 删除配置
rm -rf ~/.local/share/poolgpu/config/

# 删除 PID 文件
rm -rf ~/.local/share/poolgpu/pids/

# 删除安装
rm -rf ~/.local/share/poolgpu/
rm ~/.local/bin/poolgpu
```
