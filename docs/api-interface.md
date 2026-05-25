# 聚时 AI 推理资源管理平台一期接口文档

## 1. 文档说明

本文档基于当前前端 `ui/src/api.ts`、后端 `backend/modules/*` 以及一期开发方案整理，用于前后端联调和后端补齐接口。

约定：

- 后端基础地址：`http://localhost:8080`
- Swagger UI：`/api/docs`
- OpenAPI JSON：`/api/docs/openapi.json`
- 端口管理统一使用 `/api/port-list/*`，不再使用 `/api/ports/allowlist/*`
- 前端如果通过 Vite 开发服务访问后端，需要设置 `VITE_API_BASE_URL=http://localhost:8080`

当前后端仍是骨架实现，部分接口只返回占位数据。本文档以“一期应交付接口契约”为准，并在每个接口标注当前状态。

## 2. 通用约定

### 2.1 统一请求包

部署、告警、审计等 POST 接口建议使用统一请求结构：

```json
{
  "msg_id": "create-001",
  "serial": "serial-001",
  "context": "create inference instance",
  "content": {}
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `msg_id` | string | 是 | 请求 ID |
| `serial` | string | 是 | 请求序列 |
| `context` | string | 是 | 请求上下文 |
| `content` | object | 是 | 业务参数 |
| `gpu_resource_name` | string | 否 | Huawei 场景使用，如 `huawei.com/Ascend310P` |

### 2.2 统一响应建议

后端最终建议统一返回：

```json
{
  "is_success": true,
  "msg": "OK",
  "http_status_code": 200,
  "content": {}
}
```

如果接口需要兼容原始部署服务，也可以返回原有 envelope：

```json
{
  "msg_id": "create-001_Resp",
  "head_id": 0,
  "context": "create inference instance",
  "serial": "serial-001",
  "version": "1.0.0.1",
  "status": 0,
  "content": {},
  "token": "",
  "time": "2026-05-21 15:30:00",
  "timestamp": 1780000000000,
  "http_status_code": 200,
  "msg": "OK",
  "is_success": true
}
```

前端 `ui/src/api.ts` 当前按第二种 envelope 读取 `is_success`、`msg` 和 `content`。因此后端正式联调时必须保证：

- HTTP 状态码成功时为 2xx
- 响应体包含 `is_success`
- 失败时响应体包含 `msg`

## 3. 用户认证接口

### 3.1 用户登录

```http
POST /api/auth/login
```

当前状态：后端已建路由，占位实现。

请求：

```json
{
  "username": "admin",
  "password": "admin123"
}
```

响应：

```json
{
  "is_success": true,
  "token": "dev-token",
  "user": {
    "username": "admin",
    "real_name": "系统管理员",
    "role": "admin"
  }
}
```

### 3.2 用户登出

```http
POST /api/auth/logout
```

当前状态：后端已建路由，占位实现。

响应：

```json
{
  "is_success": true
}
```

### 3.3 当前用户

```http
GET /api/auth/me
```

当前状态：后端已建路由，占位实现。

响应：

```json
{
  "username": "admin",
  "real_name": "系统管理员",
  "role": "admin"
}
```

## 4. 用户管理接口

### 4.1 用户列表

```http
GET /api/users/list
```

当前状态：后端已建路由，占位实现。

响应：

```json
{
  "items": [
    {
      "id": 1,
      "username": "admin",
      "real_name": "系统管理员",
      "role": "admin",
      "status": "active",
      "created_at": "2026-05-21 15:30:00"
    }
  ]
}
```

### 4.2 创建用户

```http
POST /api/users/create
```

当前状态：一期需补齐。

请求：

```json
{
  "username": "alice",
  "password": "Init@123",
  "real_name": "Alice",
  "role": "operator",
  "status": "active"
}
```

响应：

```json
{
  "is_success": true,
  "id": 2
}
```

### 4.3 更新用户

```http
POST /api/users/update
```

当前状态：一期需补齐。

请求：

```json
{
  "id": 2,
  "real_name": "Alice Zhang",
  "role": "operator",
  "status": "active"
}
```

响应：

```json
{
  "is_success": true
}
```

### 4.4 删除用户

```http
POST /api/users/delete
```

当前状态：一期需补齐。建议做逻辑禁用，不做物理删除。

请求：

```json
{
  "id": 2
}
```

响应：

```json
{
  "is_success": true
}
```

### 4.5 重置密码

```http
POST /api/users/reset-password
```

当前状态：一期需补齐。

请求：

```json
{
  "id": 2,
  "password": "New@123"
}
```

响应：

```json
{
  "is_success": true
}
```

## 5. 集群与部署接口

### 5.1 集群查询

```http
POST /api/cluster
```

当前状态：后端已补齐。新版实现通过 `DCE_API_BASE` 和 `DCE_TOKEN` 调用 PaaS 集群列表接口。

请求：

```json
{
  "msg_id": "cluster-001",
  "serial": "serial-001",
  "context": "query cluster",
  "content": {}
}
```

响应：

```json
{
  "is_success": true,
  "content": {
    "items": []
  }
}
```

### 5.2 资源预检

```http
POST /api/deploy/check-available
```

当前状态：后端已建路由，占位实现。

NVIDIA 请求：

```json
{
  "msg_id": "check-001",
  "serial": "serial-001",
  "context": "check deploy available",
  "content": {
    "devices": {
      "NVIDIA/GPU": 1
    },
    "deployType": "NvidiaInfer",
    "creator": "admin"
  }
}
```

Huawei 请求：

```json
{
  "msg_id": "check-002",
  "serial": "serial-002",
  "context": "check deploy available",
  "gpu_resource_name": "huawei.com/Ascend310P",
  "content": {
    "devices": {
      "Huawei/Ascend310P": 1
    },
    "deployType": "HuaweiInfer",
    "creator": "admin"
  }
}
```

响应：

```json
{
  "is_success": true,
  "content": {
    "can_create": true,
    "reason": "resource available",
    "cpu_available_m": 64000,
    "mem_available_bytes": 137438953472,
    "gpu_details": {
      "NVIDIA/GPU": {
        "requested": 1,
        "available": 3,
        "total": 8,
        "used": 5
      }
    },
    "total_deployments": 5,
    "devices": {
      "NVIDIA/GPU": 1
    }
  }
}
```

### 5.3 创建推理部署

```http
POST /api/deploy/create-default
```

当前状态：后端已建路由，占位实现。正式实现需迁移历史后端创建 Deployment + Service 的能力。

请求同资源预检。

响应：

```json
{
  "is_success": true,
  "content": {
    "deployment_name": "nvidia-cuda-xxxxxx",
    "node_ports": [
      {
        "name": "tcp-8018",
        "port": 30001
      },
      {
        "name": "tcp-8019",
        "port": 35001
      }
    ],
    "devices": {
      "NVIDIA/GPU": 1
    },
    "gpu_type": "NVIDIA/GPU",
    "deployType": "NvidiaInfer",
    "log_path": "/workspace/Alg/log/nvidia-cuda-xxxxxx"
  }
}
```

### 5.4 查询单个部署

```http
POST /api/deploy/retrieve
```

当前状态：后端已建路由，占位实现。

请求：

```json
{
  "msg_id": "retrieve-001",
  "serial": "serial-001",
  "context": "retrieve deploy",
  "content": {
    "name": "nvidia-cuda-xxxxxx"
  }
}
```

响应：

```json
{
  "is_success": true,
  "content": {
    "deployment": {},
    "pods": [],
    "summary": {
      "total_pods": 1,
      "running_pods": 1
    }
  }
}
```

### 5.5 释放部署

```http
POST /api/deploy/release
```

当前状态：后端已建路由，占位实现。

请求：

```json
{
  "msg_id": "release-001",
  "serial": "serial-001",
  "context": "release deploy",
  "content": {
    "name": "nvidia-cuda-xxxxxx"
  }
}
```

响应：

```json
{
  "is_success": true,
  "content": {
    "deployment_name": "nvidia-cuda-xxxxxx",
    "status": "released"
  }
}
```

### 5.6 重启部署

```http
POST /api/deploy/reset
```

当前状态：后端已建路由，占位实现。

请求：

```json
{
  "msg_id": "reset-001",
  "serial": "serial-001",
  "context": "restart deploy",
  "content": {
    "name": "nvidia-cuda-xxxxxx"
  }
}
```

响应：

```json
{
  "is_success": true,
  "content": {
    "deployment_name": "nvidia-cuda-xxxxxx"
  }
}
```

### 5.7 部署列表

```http
POST /api/deploy/list
```

当前状态：后端已建路由，占位实现。

请求：

```json
{
  "msg_id": "list-001",
  "serial": "serial-001",
  "context": "list deploy",
  "content": {}
}
```

响应：

```json
{
  "is_success": true,
  "content": {
    "items": [
      {
        "deployment_name": "nvidia-cuda-xxxxxx",
        "gpu_type": "NVIDIA/GPU",
        "gpu_count": 1,
        "deployType": "NvidiaInfer",
        "creator": "admin",
        "status": "running",
        "created_at": "2026-05-21 15:30:00"
      }
    ]
  }
}
```

### 5.8 停止部署

```http
POST /api/deploy/stop
```

当前状态：一期需补齐。前端适配层已预留该接口。

请求：

```json
{
  "msg_id": "stop-001",
  "serial": "serial-001",
  "context": "stop deploy",
  "content": {
    "name": "nvidia-cuda-xxxxxx"
  }
}
```

响应：

```json
{
  "is_success": true
}
```

### 5.9 资源不足排队

```http
POST /api/deploy/queue
```

当前状态：一期需补齐。前端适配层已预留该接口。

请求：

```json
{
  "msg_id": "queue-001",
  "serial": "serial-001",
  "context": "queue deploy",
  "content": {
    "name": "nvidia-cuda-auto-001",
    "priority": "high",
    "reason": "current resource is full"
  }
}
```

响应：

```json
{
  "is_success": true,
  "content": {
    "queue_id": "queue-001",
    "rank": 1,
    "priority": "high",
    "status": "queued"
  }
}
```

### 5.10 部署日志

```http
POST /api/deploy/logs
```

当前状态：一期需补齐。前端适配层已预留该接口。

请求：

```json
{
  "msg_id": "logs-001",
  "serial": "serial-001",
  "context": "deploy logs",
  "content": {
    "name": "nvidia-cuda-xxxxxx"
  }
}
```

响应：

```json
{
  "is_success": true,
  "content": [
    {
      "time": "2026-05-21 15:30:00",
      "level": "INFO",
      "message": "Instance started successfully"
    }
  ]
}
```

## 6. 封闭端口 / 端口避让接口

端口接口统一使用 `/api/port-list/*`。

不再提供：

```text
/api/ports/allowlist/list
/api/ports/allowlist/create
/api/ports/allowlist/delete
```

前端 `ui/src/api.ts` 后续需要把端口接口改为本节路径。

### 6.1 查询封闭端口

```http
GET /api/port-list/list
```

当前状态：后端已建路由，占位实现。

响应：

```json
{
  "items": [
    {
      "id": "1",
      "port": 50055,
      "remark": "reserved port",
      "created_at": "2026-05-21 15:30:00",
      "updated_at": "2026-05-21 15:30:00"
    }
  ]
}
```

### 6.2 新增封闭端口

```http
POST /api/port-list/add
```

当前状态：后端已建路由，占位实现。

请求：

```json
{
  "port": 50055,
  "remark": "reserved port"
}
```

响应：

```json
{
  "is_success": true,
  "id": "1",
  "port": 50055,
  "remark": "reserved port"
}
```

### 6.3 更新封闭端口

```http
PUT /api/port-list/update/{item_id}
```

当前状态：后端已建路由，占位实现。

请求：

```json
{
  "port": 50056,
  "remark": "updated reserved port"
}
```

响应：

```json
{
  "is_success": true,
  "id": "1",
  "port": 50056,
  "remark": "updated reserved port"
}
```

### 6.4 删除封闭端口

```http
DELETE /api/port-list/delete/{item_id}
```

当前状态：后端已建路由，占位实现。

响应：

```json
{
  "is_success": true,
  "id": "1"
}
```

### 6.5 端口避让快照

```http
GET /api/port-list/resolve
```

当前状态：后端已建路由，占位实现。

响应：

```json
{
  "blocked_ports": [50055, 55055],
  "blocked_singles": [50055, 55055]
}
```

## 7. 集群资源接口

### 7.1 资源总览

```http
GET /api/resources/summary
```

当前状态：后端已建路由，占位实现。

响应：

```json
{
  "gpu_total": 8,
  "gpu_used": 5,
  "gpu_available": 3,
  "cpu_total_m": 128000,
  "cpu_used_m": 32000,
  "memory_total_bytes": 274877906944,
  "memory_used_bytes": 85899345920,
  "running_instances": 5,
  "pending_instances": 1
}
```

### 7.2 节点列表

```http
GET /api/resources/nodes
```

当前状态：后端已建路由，占位实现。

响应：

```json
{
  "items": [
    {
      "node_name": "node-gpu-01",
      "status": "Ready",
      "gpu_total": 4,
      "gpu_used": 3,
      "cpu_allocatable": "64",
      "memory_allocatable": "128Gi"
    }
  ]
}
```

### 7.3 GPU 统计

```http
GET /api/resources/gpus
```

当前状态：后端已建路由，占位实现。

响应：

```json
{
  "items": [
    {
      "vendor": "NVIDIA",
      "resource_name": "nvidia.com/gpu",
      "total": 4,
      "used": 3,
      "available": 1
    },
    {
      "vendor": "Huawei",
      "resource_name": "huawei.com/Ascend310P",
      "total": 12,
      "used": 5,
      "available": 7
    }
  ]
}
```

### 7.4 资源配额

```http
GET /api/resources/quotas
```

当前状态：后端已建路由，占位实现。

响应：

```json
{
  "items": []
}
```

## 8. Pod 运维接口

### 8.1 Pod 列表

```http
GET /api/pods/list
```

当前状态：后端已建路由，占位实现。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `namespace` | string | 否 | 命名空间 |
| `deployment_name` | string | 否 | 部署名 |
| `phase` | string | 否 | Pod 状态 |
| `node_name` | string | 否 | 节点名 |

响应：

```json
{
  "items": [
    {
      "pod_name": "nvidia-cuda-xxxxxx-abcde",
      "namespace": "algorithm",
      "phase": "Running",
      "node_name": "node-1",
      "pod_ip": "10.244.x.x",
      "restart_count": 0,
      "ready": true,
      "created_at": "2026-05-21 15:30:00"
    }
  ]
}
```

### 8.2 Pod 详情

```http
GET /api/pods/detail
```

当前状态：后端已建路由，占位实现。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `namespace` | string | 是 | 命名空间 |
| `pod_name` | string | 是 | Pod 名称 |

响应：

```json
{
  "pod_name": "nvidia-cuda-xxxxxx-abcde",
  "namespace": "algorithm",
  "containers": [],
  "events": []
}
```

### 8.3 Pod 日志

```http
GET /api/pods/logs
```

当前状态：后端已建路由，占位实现。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `namespace` | string | 是 | 命名空间 |
| `pod_name` | string | 是 | Pod 名称 |
| `tail_lines` | number | 否 | 最近日志行数，默认 200 |

响应：

```json
{
  "lines": [
    "[2026-05-21 15:30:00] service started"
  ]
}
```

### 8.4 删除 Pod

```http
POST /api/pods/delete
```

当前状态：后端已建路由，占位实现。

请求：

```json
{
  "namespace": "algorithm",
  "pod_name": "nvidia-cuda-xxxxxx-abcde"
}
```

响应：

```json
{
  "is_success": true
}
```

### 8.5 重启 Pod

```http
POST /api/pods/restart
```

当前状态：后端已建路由，占位实现。

请求：

```json
{
  "namespace": "algorithm",
  "pod_name": "nvidia-cuda-xxxxxx-abcde"
}
```

响应：

```json
{
  "is_success": true
}
```

## 9. 告警接口

### 9.1 告警列表

```http
POST /api/alerts/list
```

当前状态：后端已建路由，占位实现。

请求：

```json
{
  "msg_id": "alerts-list-001",
  "serial": "serial-001",
  "context": "list alerts",
  "content": {
    "level": "all",
    "limit": 20
  }
}
```

响应：

```json
{
  "is_success": true,
  "content": [
    {
      "id": "alert-001",
      "level": "high",
      "category": "资源不足",
      "title": "GPU 资源不足",
      "target": "NVIDIA/GPU",
      "description": "当前 GPU 可用数量不足",
      "action": "等待资源释放或降低申请数量",
      "created_at": "2026-05-21 15:30:00",
      "status": "open"
    }
  ]
}
```

### 9.2 创建告警

```http
POST /api/alerts/create
```

当前状态：后端已建路由，占位实现。

请求：

```json
{
  "alert_type": "resource_insufficient",
  "alert_level": "high",
  "title": "GPU 资源不足",
  "message": "当前 GPU 可用数量不足",
  "source": "deploy",
  "target_name": "NVIDIA/GPU"
}
```

响应：

```json
{
  "is_success": true
}
```

### 9.3 解决告警

```http
POST /api/alerts/resolve
```

当前状态：后端已建路由，占位实现。

请求：

```json
{
  "id": "alert-001",
  "resolver": "admin"
}
```

响应：

```json
{
  "is_success": true,
  "status": "resolved"
}
```

### 9.4 忽略告警

```http
POST /api/alerts/ignore
```

当前状态：后端已建路由，占位实现。

请求：

```json
{
  "id": "alert-001",
  "resolver": "admin"
}
```

响应：

```json
{
  "is_success": true,
  "status": "ignored"
}
```

## 10. 日志与审计接口

### 10.1 操作日志

```http
GET /api/logs/operations
```

当前状态：后端已建路由，占位实现。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `operator` | string | 否 | 操作人 |
| `operation_type` | string | 否 | 操作类型 |
| `keyword` | string | 否 | 关键词 |
| `page` | number | 否 | 页码 |
| `page_size` | number | 否 | 每页数量 |

响应：

```json
{
  "items": [
    {
      "operator": "admin",
      "operation_type": "create",
      "target_type": "deploy",
      "target_name": "nvidia-cuda-xxxxxx",
      "is_success": true,
      "created_at": "2026-05-21 15:30:00"
    }
  ]
}
```

### 10.2 实例日志

```http
GET /api/logs/instance
```

当前状态：后端已建路由，占位实现。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `deployment_name` | string | 是 | 部署名称 |
| `tail_lines` | number | 否 | 最近日志行数 |

响应：

```json
{
  "lines": [
    "[2026-05-21 15:30:00] instance started"
  ]
}
```

### 10.3 Pod 日志

```http
GET /api/logs/pod
```

当前状态：后端已建路由，占位实现。

查询参数同 `/api/pods/logs`。

响应：

```json
{
  "lines": [
    "[2026-05-21 15:30:00] pod started"
  ]
}
```

### 10.4 审计列表

```http
POST /api/audits/list
```

当前状态：一期需补齐。前端适配层已预留该接口。

请求：

```json
{
  "msg_id": "audits-list-001",
  "serial": "serial-001",
  "context": "list audits",
  "content": {
    "result": "all",
    "operator": "admin",
    "time_range": "7d",
    "keyword": "vGPU",
    "page": 1,
    "page_size": 20
  }
}
```

响应：

```json
{
  "is_success": true,
  "content": {
    "list": [
      {
        "operator": "admin",
        "action": "创建实例",
        "target": "nvidia-cuda-xxxxxx",
        "result": "success",
        "created_at": "2026-05-21 15:30:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

### 10.5 导入审计日志

```http
POST /api/audits/import
Content-Type: multipart/form-data
```

当前状态：一期需补齐。前端适配层已预留该接口。

表单字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 是 | Excel 或 PDF 文件 |

响应：

```json
{
  "is_success": true,
  "imported": 10
}
```

### 10.6 导出审计日志

```http
POST /api/audits/export
```

当前状态：一期需补齐。前端适配层已预留该接口。

请求：

```json
{
  "msg_id": "audits-export-001",
  "serial": "serial-001",
  "context": "export audits",
  "content": {
    "format": "excel",
    "result": "all",
    "time_range": "7d"
  }
}
```

响应：

```json
{
  "is_success": true,
  "content": {
    "download_url": "http://localhost:8080/downloads/audit-export.xlsx"
  }
}
```

## 11. 前后端字段对齐说明

### 11.1 GPU 字段

前端可传：

```json
{
  "gpu_vendor": "NVIDIA",
  "gpu_type": "NVIDIA/GPU",
  "gpu_count": 1
}
```

但为了兼容当前前端 `ui/src/api.ts`，一期后端必须继续支持：

```json
{
  "devices": {
    "NVIDIA/GPU": 1
  },
  "deployType": "NvidiaInfer"
}
```

后端内部统一映射：

| 前端字段 | 内部资源名 | deployType | 算法包 |
| --- | --- | --- | --- |
| `NVIDIA/GPU` | `nvidia.com/gpu` | `NvidiaInfer` | `mtworkflow_x86.zip` |
| `Huawei/Ascend310P` | `huawei.com/Ascend310P` | `HuaweiInfer` | `mtworkflow_arm.zip` |

### 11.2 端口字段

端口接口统一使用：

```text
/api/port-list/*
```

前端旧的 `PortAllowlistItem` 可临时映射：

| 前端字段 | 后端字段 | 说明 |
| --- | --- | --- |
| `port` | `port` | 端口号 |
| `remark` | `remark` | 备注 |
| `name` | 可忽略或写入 remark | 端口名称 |
| `creator` | 可写入操作日志 | 创建人 |

### 11.3 告警字段

前端展示字段：

```text
id, level, category, title, target, description, action, created_at, status
```

后端表字段建议：

```text
id, alert_type, alert_level, title, message, source, target_name, status, created_at, resolved_at, resolver
```

接口返回时由后端适配：

| 后端字段 | 前端字段 |
| --- | --- |
| `alert_level` | `level` |
| `message` | `description` |
| `target_name` | `target` |
| `source` | `category` |

## 12. 一期后端补齐清单

当前后端已建路由：

```text
GET  /api/health
GET  /api/docs
GET  /api/docs/openapi.json
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
GET  /api/users/list
POST /api/deploy/check-available
POST /api/deploy/create-default
POST /api/deploy/retrieve
POST /api/deploy/release
POST /api/deploy/reset
POST /api/deploy/list
GET  /api/port-list/list
POST /api/port-list/add
PUT  /api/port-list/update/{item_id}
DELETE /api/port-list/delete/{item_id}
GET  /api/port-list/resolve
GET  /api/resources/summary
GET  /api/resources/nodes
GET  /api/resources/gpus
GET  /api/resources/quotas
GET  /api/pods/list
GET  /api/pods/detail
GET  /api/pods/logs
POST /api/pods/delete
POST /api/pods/restart
POST /api/alerts/list
POST /api/alerts/create
POST /api/alerts/resolve
POST /api/alerts/ignore
GET  /api/logs/operations
GET  /api/logs/instance
GET  /api/logs/pod
```

一期还需补齐路由和实现：

```text
POST /api/users/create
POST /api/users/update
POST /api/users/delete
POST /api/users/reset-password
POST /api/deploy/stop
POST /api/deploy/queue
POST /api/deploy/logs
POST /api/audits/list
POST /api/audits/import
POST /api/audits/export
```

前端需要调整：

```text
把 /api/ports/allowlist/* 改为 /api/port-list/*
```
