# PoolGPU 代码同步功能设计

## 1. 概述

实现代码同步功能，将主服务器的代码目录同步到所有 Worker 服务器。采用 Worker 代理同步方案——Worker 主动从 Master 拉取代码，无需 SSH 免密登录。

## 2. 范围

**包含：**
- Worker 新增 `/api/sync` 接口，通过 rsync 从 Master 拉取代码
- CLI 新增 `poolgpu sync` 命令
- CLI `poolgpu submit --sync` 支持任务提交时自动同步
- rsync 排除规则（__pycache__, .git, .venv 等）

**不包含：**
- 双向同步
- 文件监控自动同步
- 冲突解决

## 3. 架构

```
用户运行 poolgpu sync（或 --sync）
    │
    ▼
┌──────────────────┐
│  Master           │
│  读取 config.yaml │
│  code_dir 路径    │
└────────┬─────────┘
         │ 并发 POST /api/sync
    ┌────┼────┐
    │    │    │
    ▼    ▼    ▼
┌─────┐┌─────┐┌─────┐
│ W1  ││ W2  ││ W3  │  每个 Worker
│rsync││rsync││rsync│  从 Master 拉取
└─────┘└─────┘└─────┘
```

## 4. 同步流程

### 4.1 手动同步

```
poolgpu sync
    │
    ▼
1. Master 读取 config.yaml 的 code_dir
    │
    ▼
2. Master 并发调用所有 Worker 的 POST /api/sync
   请求体: {source: "master_host:code_dir"}
    │
    ▼
3. 每个 Worker 执行 rsync 从 Master 拉取
    │
    ▼
4. Master 汇总结果并显示
```

### 4.2 任务提交时自动同步

```
poolgpu submit --sync --gpu 1 --name "train" -- bash train.sh
    │
    ▼
1. 先执行同步流程（同上）
    │
    ▼
2. 同步成功后继续提交任务
```

## 5. API 接口

### 5.1 Worker 新增接口

| 接口 | 方法 | 说明 | 请求体 | 响应体 |
|------|------|------|--------|--------|
| `/api/sync` | POST | 同步代码 | `{source: "master_host:/path/to/code"}` | `{status, files_changed, duration, error?}` |

### 5.2 rsync 命令

```bash
rsync -avz --delete \
  --exclude='__pycache__/' \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='.pytest_cache/' \
  master_host:/path/to/code/ /local/path/to/code/
```

参数说明：
- `-a`: 归档模式（保留权限、时间戳等）
- `-v`: 详细输出
- `-z`: 压缩传输
- `--delete`: 删除目标中源没有的文件（保持一致）

## 6. 配置

```yaml
# config.yaml 已有配置
sync:
  code_dir: "/home/albin/code"  # 主服务器代码目录
```

Worker 端需要知道本地代码目录路径，可以通过配置或环境变量指定。

## 7. 错误处理

- 某个 Worker 同步失败不影响其他 Worker
- Master 汇总时标记失败的 Worker
- rsync 错误通过返回码和 stderr 传递

## 8. 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `worker/worker.py` | 修改 | 新增 `/api/sync` 接口 |
| `scheduler/scheduler.py` | 修改 | 新增 `sync_all_workers()` 方法 |
| `cli/main.py` | 修改 | 实现 `sync` 命令，`submit` 支持 `--sync` |
| `shared/config.py` | 修改 | 新增同步相关配置读取 |
| `tests/test_sync.py` | 新建 | 同步功能测试 |

## 9. 测试策略

- 单元测试：rsync 命令构建、排除规则
- 集成测试：Worker 同步接口
- Mock 测试：模拟 Master-Worker 同步流程
