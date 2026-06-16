# PoolGPU 结果收集功能设计

## 1. 概述

实现结果收集功能，任务完成后自动将 Worker 上的结果目录推送到 Master。采用 Worker 推送方案——Worker 任务完成后主动把结果 rsync 推送到 Master。

## 2. 范围

**包含：**
- Worker 新增 `/api/collect-result` 接口，推送结果到 Master
- Master 收到任务完成通知时自动触发结果收集
- 结果按任务 ID 隔离存储
- 配置项读取（results.dir）

**不包含：**
- 结果可视化
- 结果版本控制
- 结果清理策略

## 3. 架构

```
Worker 任务完成
    │
    ▼
Worker POST /api/tasks/<id>/progress
    │
    ▼
Master 收到完成通知
    │
    ▼
Master POST /api/collect-result → Worker
    │
    ▼
Worker rsync 推送结果到 Master
    │
    ▼
Master 更新 result_path
```

## 4. 收集流程

### 4.1 Worker 端

```
1. 任务完成/失败
2. 汇报进度给 Master (POST /api/tasks/<id>/progress)
   包含 result_dir 字段
3. 收到 Master 的 collect-result 请求
4. rsync 推送结果目录到 Master
```

### 4.2 Master 端

```
1. 收到 Worker 的进度汇报
2. 如果 status=completed 且有 result_dir
3. 调用 Worker 的 /api/collect-result
4. 更新任务的 result_path
```

## 5. API 接口

### 5.1 Worker 新增接口

| 接口 | 方法 | 说明 | 请求体 | 响应体 |
|------|------|------|--------|--------|
| `/api/collect-result` | POST | 推送结果到 Master | `{task_id, result_dir, target_host}` | `{status, files_count, duration}` |

### 5.2 进度汇报变更

`POST /api/tasks/<id>/progress` 新增字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `result_dir` | string | Worker 上的结果目录路径 |

### 5.3 rsync 命令

```bash
rsync -avz /path/to/results/ master_host:/poolgpu/results/task_{id}/
```

## 6. 配置

```yaml
results:
  dir: "/home/albin/poolgpu/results"  # Master 结果存储目录
```

## 7. 数据库变更

tasks 表已有 `result_path` 字段，无需新增。

## 8. 错误处理

- Worker 推送失败时结果保留在 Worker 上
- Master 标记 result_path 为空
- 结果目录不存在时返回错误

## 9. 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `shared/config.py` | 修改 | 新增结果目录配置读取 |
| `worker/worker.py` | 修改 | 新增 `/api/collect-result` 接口，修改进度汇报 |
| `scheduler/master_api.py` | 修改 | 收到完成通知时触发结果收集 |
| `scheduler/scheduler.py` | 修改 | 新增 `collect_result()` 方法 |
| `tests/test_result_collection.py` | 新建 | 结果收集测试 |

## 10. 测试策略

- 单元测试：配置读取、收集方法
- 集成测试：Worker 结果推送接口
- Mock 测试：模拟 Master-Worker 结果收集流程
