# PoolGPU 设计文档

## 1. 项目概述

PoolGPU 是一个轻量级 GPU 资源池调度系统，将多台服务器的 GPU 聚合为一个统一的资源池，自动分配空闲 GPU 运行任务。

## 2. 需求背景

### 2.1 环境
- 5 台服务器，10 张 GPU
  - 2 台 4090D（各 2 张）
  - 2 台 3090Ti（各 2 张）
  - 1 台 5090（2 张）
- 任务类型：时序/GNN 模型训练
- 当前方式：手动 SSH 到每台服务器

### 2.2 核心需求
1. **GPU 自动调度**：任务提交后自动找空闲 GPU 运行
2. **代码同步**：改一次代码自动同步到所有服务器
3. **环境共享**：主服务器配置一次环境，所有服务器共享
4. **结果收集**：训练结果统一存放到主服务器
5. **失败处理**：任务失败自动重试 + 通知
6. **管理界面**：CLI 提交任务 + Web 查看状态

## 3. 架构设计

### 3.1 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    主服务器 (Master)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  调度器      │  │  Web UI     │  │  代码仓库    │ │
│  │  Scheduler  │  │  Flask      │  │  /code/     │ │
│  └──────┬──────┘  └─────────────┘  └──────┬──────┘ │
│         │                                  │        │
│  ┌──────┴──────┐                   ┌──────┴──────┐ │
│  │  任务队列    │                   │  环境目录    │ │
│  │  SQLite     │                   │  /envs/     │ │
│  └─────────────┘                   └─────────────┘ │
└─────────────────────┬───────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
   ┌────┴────┐  ┌────┴────┐  ┌────┴────┐
   │ Server1 │  │ Server2 │  │ Server3 │
   │  Worker │  │  Worker │  │  Worker │
   │ 4090D×2 │  │ 4090D×2 │  │3090Ti×2 │
   └─────────┘  └─────────┘  └─────────┘
                      │
        ┌─────────────┼─────────────┐
   ┌────┴────┐  ┌────┴────┐
   │ Server4 │  │ Server5 │
   │ Worker │  │ Worker │
   │3090Ti×2 │  │  5090×2 │
   └─────────┘  └─────────┘
```

### 3.2 核心组件

| 组件 | 作用 | 部署位置 |
|------|------|----------|
| **Master** | 主节点，运行调度器和 Web UI | 主服务器 |
| **Worker** | 执行任务、汇报 GPU 状态 | 每台服务器 |
| **Scheduler** | 任务调度，分配 GPU | 主服务器 |
| **Notifier** | 任务失败/完成时发送通知 | 主服务器 |

## 4. 功能设计

### 4.1 GPU 调度

**调度逻辑**：
1. 任务提交到队列
2. 调度器轮询队列，查找待处理任务
3. 查询所有服务器 GPU 状态
4. 分配空闲 GPU 给任务
5. 通过 SSH 在目标服务器执行任务

**GPU 状态**：
- idle：空闲
- busy：运行中
- error：故障

### 4.2 代码同步

**同步方式**：
- 手动触发：`poolgpu sync`
- 任务运行时自动同步：`poolgpu submit --sync -- bash train.sh`

**同步实现**：
- 使用 rsync 同步代码目录
- 支持增量同步

### 4.3 环境管理

**环境共享方案**：
1. 在主服务器上用 conda-pack 打包环境
2. 分发到所有服务器
3. 任务运行时激活环境

**命令**：
```bash
# 打包环境
conda-pack -n myenv -o myenv.tar.gz

# 分发环境
poolgpu env-sync
```

### 4.4 结果收集

任务完成后自动将结果从目标服务器拉取到主服务器：
```
/results/
  ├── task_001/
  │   ├── model.pth
  │   └── log.txt
  ├── task_002/
  │   └── ...
```

### 4.5 失败处理

**重试策略**：
- 最大重试次数：3 次
- 重试间隔：5 秒
- 重试条件：任务失败（非手动取消）

**通知方式**：
- 终端通知：任务完成/失败时显示
- Web UI 通知：Dashboard 上显示

## 5. 接口设计

### 5.1 CLI 命令

```bash
# 提交任务
poolgpu submit --gpu 1 --name "train_gnn" -- bash train.sh

# 查看任务状态
poolgpu status

# 查看 GPU 使用率
poolgpu gpu

# 同步代码
poolgpu sync

# 同步环境
poolgpu env-sync
```

### 5.2 Web API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/tasks` | GET | 获取任务列表 |
| `/api/gpu` | GET | 获取 GPU 状态 |
| `/api/tasks` | POST | 提交任务 |

## 6. 数据模型

### 6.1 任务表 (tasks)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | TEXT | 任务名称 |
| command | TEXT | 执行命令 |
| gpu_count | INTEGER | 需要 GPU 数量 |
| server | TEXT | 分配的服务器 |
| gpu_ids | TEXT | 分配的 GPU ID |
| status | TEXT | 状态：pending/running/completed/failed |
| progress | REAL | 进度百分比 |
| retry_count | INTEGER | 已重试次数 |
| max_retries | INTEGER | 最大重试次数 |
| created_at | TIMESTAMP | 创建时间 |
| started_at | TIMESTAMP | 开始时间 |
| finished_at | TIMESTAMP | 完成时间 |
| result_path | TEXT | 结果路径 |
| error | TEXT | 错误信息 |

## 7. 技术栈

| 组件 | 技术 |
|------|------|
| Master | Python (Flask/FastAPI) |
| Worker | Python |
| 通信 | SSH (paramiko) + HTTP API |
| 数据库 | SQLite |
| Web UI | HTML + JavaScript |
| 环境管理 | conda-pack |
| 代码同步 | rsync |

## 8. 部署步骤

### 8.1 主服务器
1. 安装依赖：`pip install -e .`
2. 配置 `config.yaml`
3. 启动调度器和 Web UI

### 8.2 各服务器
1. 安装 Worker 依赖
2. 配置 SSH 免密登录
3. 启动 Worker

## 9. 使用示例

```bash
# 1. 提交任务
poolgpu submit --gpu 1 --name "train_gnn" -- bash train.sh

# 2. 查看状态
poolgpu status

# 3. 查看 GPU
poolgpu gpu

# 4. 同步代码
poolgpu sync

# 5. 同步环境
poolgpu env-sync
```

## 10. 待实现功能

- [ ] 调度器核心逻辑
- [ ] Worker 实现
- [ ] Web UI 完善
- [ ] 代码同步实现
- [ ] 环境同步实现
- [ ] 结果收集实现
- [ ] 通知系统
- [ ] 测试用例
