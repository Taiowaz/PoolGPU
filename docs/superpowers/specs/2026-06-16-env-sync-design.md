# PoolGPU 环境同步功能设计

## 1. 概述

实现环境同步功能，将主服务器的 conda 环境打包并分发到所有 Worker 服务器。采用 Worker 代理同步方案——Worker 主动从 Master 拉取环境包并解压。

## 2. 范围

**包含：**
- Master 执行 conda-pack 打包环境
- Worker 新增 `/api/env-sync` 接口，下载并解压环境包
- CLI 新增 `poolgpu env-sync` 命令
- 配置项读取（env_name, env_pack_path）

**不包含：**
- 环境创建/删除
- 多环境管理
- 环境版本控制

## 3. 架构

```
用户运行 poolgpu env-sync
    │
    ▼
┌──────────────────┐
│  Master           │
│  conda-pack 打包  │
└────────┬─────────┘
         │ 并发 POST /api/env-sync
    ┌────┼────┐
    │    │    │
    ▼    ▼    ▼
┌─────┐┌─────┐┌─────┐
│ W1  ││ W2  ││ W3  │  每个 Worker
│下载  ││下载  ││下载  │  下载并解压
│解压  ││解压  ││解压  │
└─────┘└─────┘└─────┘
```

## 4. 同步流程

### 4.1 Master 端

```
1. 读取 config.yaml 的 env_name 和 env_pack_path
2. 执行 conda-pack -n {env_name} -o {pack_path}
3. 并发调用所有 Worker 的 POST /api/env-sync
4. 汇总结果并显示
```

### 4.2 Worker 端

```
1. 收到 {source, env_name} 请求
2. 从 Master 下载 .tar.gz 文件
3. 创建目标目录
4. tar -xzf {pack_path} -C {target_dir}
5. 返回结果
```

## 5. API 接口

### 5.1 Worker 新增接口

| 接口 | 方法 | 说明 | 请求体 | 响应体 |
|------|------|------|--------|--------|
| `/api/env-sync` | POST | 同步环境 | `{source, env_name}` | `{status, duration, error?}` |

### 5.2 conda-pack 命令

```bash
# 打包
conda-pack -n myenv -o /tmp/myenv.tar.gz

# 解压（Worker 端）
mkdir -p /home/albin/envs/myenv
tar -xzf /tmp/myenv.tar.gz -C /home/albin/envs/myenv
```

## 6. 配置

```yaml
sync:
  env_name: "myenv"                    # conda 环境名
  env_pack_path: "/tmp/myenv.tar.gz"  # 打包文件路径
```

## 7. 错误处理

- conda-pack 打包失败时不调用 Worker，直接报错
- 某个 Worker 同步失败不影响其他 Worker
- Master 汇总时标记失败的 Worker

## 8. 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `shared/config.py` | 修改 | 新增环境同步配置读取 |
| `worker/worker.py` | 修改 | 新增 `/api/env-sync` 接口 |
| `scheduler/scheduler.py` | 修改 | 新增 `env_sync_all_workers()` 方法 |
| `cli/main.py` | 修改 | 实现 `env-sync` 命令 |
| `tests/test_env_sync.py` | 新建 | 环境同步测试 |

## 9. 测试策略

- 单元测试：配置读取、打包命令构建
- 集成测试：Worker 环境同步接口
- Mock 测试：模拟 Master-Worker 环境同步流程
