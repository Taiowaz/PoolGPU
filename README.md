# PoolGPU

GPU 资源池调度系统，将多台服务器的 GPU 聚合为一个统一的资源池，自动分配空闲 GPU 运行任务。

## 功能

- 自动分配空闲 GPU
- 代码同步（手动触发或运行时自动）
- 环境共享（主服务器配置一次，所有服务器共享）
- 结果收集（统一存放到主服务器）
- 任务失败自动重试 + 通知
- Web 界面查看任务状态和 GPU 使用率

## 架构

```
主服务器 (Master)
├── 调度器 (Scheduler)
├── Web UI
├── 代码仓库
└── 环境目录

各服务器 (Worker)
├── GPU 监控
├── 任务执行
└── 结果上传
```

## 安装

```bash
# 主服务器
pip install -e .

# 各服务器 Worker
pip install -e ./worker
```

## 使用

```bash
# 提交任务
poolgpu submit --gpu 1 --name "train_gnn" -- bash train.sh

# 查看状态
poolgpu status

# 查看 GPU
poolgpu gpu

# 同步代码
poolgpu sync

# 同步环境
poolgpu env-sync
```

## 目录结构

```
PoolGPU/
├── scheduler/       # 调度器核心逻辑
├── worker/           # 服务器端 Worker
├── webui/           # Web 界面
├── cli/             # 命令行工具
├── shared/          # 共享工具和配置
├── tests/           # 测试
└── docs/            # 文档
```
