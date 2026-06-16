# PoolGPU 调度器核心逻辑设计

## 1. 概述

实现调度器核心逻辑，包括 GPU 分配、任务调度、Master-Worker HTTP 通信。采用同步调度方案——任务提交时立即触发调度，无需后台常驻进程。

## 2. 范围

**包含：**
- 调度器核心逻辑（GPU 分配、任务分配）
- Worker HTTP 服务（GPU 状态查询、任务执行）
- Master-Worker HTTP API
- 任务状态管理（状态机、重试）
- CLI submit/status 命令实现
- WebUI API 对接真实数据

**不包含（后续迭代）：**
- 代码同步（rsync）
- 环境同步（conda-pack）
- 结果收集
- 通知系统

## 3. 架构

```
用户 (CLI/WebUI)
    │
    ▼
┌──────────────────┐
│  Master           │
│  ┌──────────────┐ │
│  │ Scheduler    │ │  SQLite (tasks)
│  │ (核心调度)    │ │
│  └──────┬───────┘ │
│         │ HTTP    │
└─────────┼─────────┘
          │
    ┌─────┼─────┐
    │     │     │
    ▼     ▼     ▼
┌─────┐┌─────┐┌─────┐
│Worker││Worker││Worker│  每台服务器
│ HTTP││ HTTP││ HTTP│  Worker 作为 HTTP 服务
└─────┘└─────┘└─────┘
```

## 4. 调度流程

### 4.1 任务提交

```
CLI/WebUI 提交任务
    │
    ▼
1. 写入 SQLite (status=pending)
    │
    ▼
2. 触发 scheduler.schedule_next()
    │
    ▼
3. 查询所有 Worker GPU 状态 (HTTP GET /api/gpu)
    │
    ▼
4. 按性能优先策略分配 GPU
    │
    ▼
5. 提交任务到 Worker (HTTP POST /api/tasks)
    │
    ▼
6. 更新任务状态 (status=running, server=xxx, gpu_ids=xxx)
```

### 4.2 Worker 端执行

```
Worker 收到任务
    │
    ▼
1. 启动 subprocess (CUDA_VISIBLE_DEVICES=gpu_ids)
    │
    ▼
2. 每 10 秒汇报进度 → Master POST /api/tasks/<id>/progress
    │
    ▼
3. 任务完成/失败 → Master POST /api/tasks/<id>/progress (最终状态)
```

## 5. GPU 分配策略

### 5.1 性能等级

从 config.yaml 的 `gpu_model` 字段映射：

| GPU 型号 | 性能等级 |
|----------|----------|
| 5090     | 3        |
| 4090D    | 2        |
| 3090Ti   | 1        |

### 5.2 分配算法

1. 查询所有 Worker 的 GPU 状态
2. 筛选 `status=idle` 的 GPU
3. 按性能等级降序排列
4. 从头部取出 `gpu_count` 个 GPU
5. 如果可用 GPU 不足，任务保持 pending 状态

## 6. HTTP API

### 6.1 Worker API

| 接口 | 方法 | 说明 | 请求体 | 响应体 |
|------|------|------|--------|--------|
| `/api/health` | GET | 健康检查 | - | `{status, server}` |
| `/api/gpu` | GET | GPU 状态 | - | `[{index, name, memory_used, memory_total, utilization, status}]` |
| `/api/tasks` | POST | 提交任务 | `{task_id, command, gpu_ids}` | `{status: "accepted"}` |
| `/api/tasks/<id>/status` | GET | 任务状态 | - | `{status, progress, stdout, stderr}` |
| `/api/tasks/<id>/cancel` | POST | 取消任务 | - | `{status: "cancelled"}` |

### 6.2 Master API（供 Worker 回调）

| 接口 | 方法 | 说明 | 请求体 |
|------|------|------|--------|
| `/api/tasks/<id>/progress` | POST | 汇报进度 | `{status, progress, stdout, stderr}` |

## 7. 任务状态机

```
pending → running → completed
                  → failed → (retry) → pending
                  → cancelled
```

- `pending`: 等待调度
- `running`: 在 Worker 上执行中
- `completed`: 执行成功
- `failed`: 执行失败，可重试
- `cancelled`: 用户取消

## 8. 错误处理

### 8.1 重试策略

- 最大重试次数：3 次（config.yaml `retry.max_attempts`）
- 重试间隔：5 秒（config.yaml `retry.delay_seconds`）
- 重试条件：任务失败（非手动取消）
- 重试时重新走调度流程

### 8.2 Worker 不可用

- 调度时 Worker 无法连接，跳过该服务器
- 所有 Worker 不可用，任务保持 pending

### 8.3 任务取消

- CLI/WebUI 可取消 pending 或 running 的任务
- 取消 running 任务时调用 Worker `/api/tasks/<id>/cancel`

## 9. 数据库变更

无需新增表，现有 tasks 表已包含所需字段：

```sql
-- 已有字段足够使用
tasks.id, tasks.name, tasks.command, tasks.gpu_count,
tasks.server, tasks.gpu_ids, tasks.status, tasks.progress,
tasks.retry_count, tasks.max_retries, tasks.created_at,
tasks.started_at, tasks.finished_at, tasks.result_path, tasks.error
```

## 10. 配置

```yaml
# config.yaml 新增字段
worker:
  port: 8090          # Worker HTTP 端口
  report_interval: 10 # 状态汇报间隔（秒）

gpu_models:           # GPU 性能等级映射
  "5090": 3
  "4090D": 2
  "3090Ti": 1
```

## 11. 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `scheduler/scheduler.py` | 重写 | 核心调度逻辑 |
| `worker/worker.py` | 重写 | Worker HTTP 服务 |
| `cli/main.py` | 修改 | 实现 submit/status 命令 |
| `webui/app.py` | 修改 | API 对接真实数据 |
| `shared/config.py` | 修改 | 新增配置项读取 |
| `tests/test_scheduler.py` | 扩展 | 调度逻辑测试 |

## 12. 测试策略

- 单元测试：调度逻辑、GPU 分配算法
- 集成测试：Master-Worker 通信
- Mock Worker：测试调度流程 without 真实服务器
