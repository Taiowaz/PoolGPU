# PoolGPU 通知系统功能设计

## 1. 概述

实现通知系统，任务完成/失败时通过 WebSocket 推送通知到浏览器，并在 Web UI 上显示通知历史记录。

## 2. 范围

**包含：**
- Master 通过 SocketIO 推送通知到浏览器
- Web UI 显示 Toast 通知
- 通知历史记录持久化到数据库
- `/api/notifications` 接口获取通知记录

**不包含：**
- 邮件通知
- 企业微信/钉钉通知
- 通知筛选/搜索

## 3. 架构

```
任务状态变化 (completed/failed)
    │
    ▼
Master 检测到状态变化
    │
    ▼
1. 保存通知到数据库
2. 通过 SocketIO 推送事件
    │
    ▼
浏览器收到事件
    │
    ▼
1. 显示 Toast 通知（3 秒后消失）
2. 追加到通知记录列表
```

## 4. 数据库

### 4.1 notifications 表

```sql
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    task_name TEXT,
    status TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## 5. API 接口

### 5.1 新增接口

| 接口 | 方法 | 说明 | 响应体 |
|------|------|------|--------|
| `/api/notifications` | GET | 获取通知记录 | `[{id, task_id, task_name, status, message, created_at}]` |

### 5.2 SocketIO 事件

| 事件名 | 数据 | 说明 |
|--------|------|------|
| `notification` | `{task_id, task_name, status, message}` | 新通知 |

## 6. 前端实现

### 6.1 Toast 通知

- 成功：绿色 Toast
- 失败：红色 Toast
- 3 秒后自动消失

### 6.2 通知记录区域

```
┌─────────────────────────────────────┐
│  通知记录                           │
│  ✅ train_gnn 已完成 - server1      │
│  ❌ eval_model 失败 - server2       │
│  ✅ preprocess 已完成 - server3     │
└─────────────────────────────────────┘
```

## 7. 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `scheduler/scheduler.py` | 修改 | 新增通知相关方法 |
| `scheduler/master_api.py` | 修改 | 任务完成/失败时发送通知 |
| `webui/app.py` | 修改 | 初始化 SocketIO，新增通知 API |
| `webui/templates/index.html` | 修改 | 监听 SocketIO 事件，显示通知 |
| `tests/test_notification.py` | 新建 | 通知系统测试 |

## 8. 测试策略

- 单元测试：通知保存、查询
- 集成测试：SocketIO 事件推送
- 前端测试：Toast 显示
