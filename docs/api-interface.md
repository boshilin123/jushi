# 聚时 AI 推理资源管理平台一期接口文档

## 1. 文档说明

本文档基于当前前端 `ui/src/api.ts`、后端 `backend/modules/*` 以及一期开发方案整理，用于前后端联调和后端补齐接口。

约定：

- 后端基础地址：`http://localhost:8080`
- Swagger UI：`/api/docs`
- OpenAPI JSON：`/api/docs/openapi.json`
- 端口管理统一使用 `/api/port-list/*`，不再使用 `/api/ports/allowlist/*`
- 前端如果通过 Vite 开发服务访问后端，需要设置 `VITE_API_BASE_URL=http://localhost:8080`

当前后端仍有部分接口只返回占位数据。本文档以“一期应交付接口契约”为准，并在每个接口标注当前状态。

## 2. 通用约定

### 2.1 接口风格划分

产品化后不强制所有接口使用同一种请求体。按接口类型分为两类：

| 类型 | 适用接口 | 请求格式 | 说明 |
| --- | --- | --- | --- |
| 产品化 REST 接口 | 认证、用户、端口、资源、Pod、告警、日志等 | 直接 JSON、query 参数或 path 参数 | 面向页面管理能力，字段应贴近业务对象 |
| 兼容部署 envelope 接口 | 集群、部署、审计等 POST 接口 | `msg_id` / `serial` / `context` / `content` | 兼容原服务器部署服务和当前前端适配层 |

部署类接口本期继续使用 envelope，方便从原 `app_x86_195.py` / `app_arm_195.py` 迁移，并保持前端 `ui/src/api.ts` 的 `ApiEnvelope<T>` 可用。

### 2.2 鉴权约定

除以下接口外，所有 `/api/*` 业务接口都需要携带登录 token：

```text
GET  /api/health
POST /api/auth/login
GET  /api/docs
GET  /api/docs/openapi.json
```

请求头：

```http
Authorization: Bearer <login_token>
```

说明：

- 登录 token 来自 `/api/auth/login`，用于访问本系统后端。
- `DCE_TOKEN` 是后端内部调用 PaaS/DCE 使用的 token，只配置在服务端环境变量中，前端、Swagger、curl 都不应该传入。
- 旧版前端中的 `X-User` 只能作为创建人兜底信息，不能作为登录鉴权凭证。

### 2.3 部署 envelope 请求包

集群与部署类 POST 接口使用以下结构：

```json
{
  "msg_id": "create-001",
  "serial": "create-serial-001",
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

兼容规则：

- `/api/cluster` 可以接受没有 `content` 的旧请求；新请求建议统一传 `content: {}`。
- `content.creator` 作为创建人优先来源；没有时后端可退回当前登录用户，再退回 `X-User` / `X-Forwarded-User`。
- 部署类接口的响应建议继续回传 `msg_id`、`serial`、`context`，便于和历史服务及前端调试保持一致。
- 部署类接口会按动作校验 `msg_id`、`serial` 和 `context`；前端必须传对应动作的前缀和上下文，否则返回 `400`。

部署类动作约束：

| 接口 | `msg_id` / `serial` 前缀 | `context` |
| --- | --- | --- |
| `POST /api/deploy/check-available` | `check-` | `check deploy available` |
| `POST /api/deploy/create-default` | `create-` | `create inference instance` |
| `POST /api/deploy/retrieve` | `retrieve-` | `retrieve deploy` |
| `POST /api/deploy/list` | `list-` | `list deploy` |
| `POST /api/deploy/release` | `release-` | `release deploy` |
| `POST /api/deploy/reset` | `reset-` | `restart deploy` |
| `POST /api/deploy/stop` | `stop-` | `stop deploy` |
| `POST /api/deploy/logs` | `logs-` | `deploy logs` |

### 2.4 响应包

产品化 REST 接口可以返回简化结构：

```json
{
  "is_success": true,
  "msg": "OK",
  "http_status_code": 200,
  "content": {}
}
```

部署类接口必须返回兼容原始部署服务的 envelope：

```json
{
  "msg_id": "create-001_Resp",
  "head_id": 0,
  "context": "create inference instance",
  "serial": "create-serial-001",
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

所有接口正式联调时必须保证：

- HTTP 状态码成功时为 2xx
- 响应体包含 `is_success`
- 失败时响应体包含 `msg`
- 失败时 HTTP 状态码和 `http_status_code` 保持一致

部署类接口额外约定：

| 字段 | 说明 |
| --- | --- |
| `status` | 语义状态，`0` 成功，`-1` 失败 |
| `http_status_code` | HTTP 状态码镜像 |
| `content` | 业务返回体或下游错误快照 |
| `msg` | 给页面或 Swagger 展示的简短原因 |

### 2.5 部署开发顺序约定

后续部署类开发按以下顺序推进：

```text
1. POST /api/cluster
2. POST /api/deploy/check-available
3. POST /api/deploy/create-default
4. POST /api/deploy/retrieve
5. POST /api/deploy/list
6. POST /api/deploy/release
7. POST /api/deploy/reset
```

一期暂不优先开发：

```text
POST /api/deploy/queue
```

`queue` 只在资源不足排队能力重新纳入一期范围时实现。`stop` 和 `logs` 可以作为实例中心增强接口，在核心创建/释放链路稳定后补齐。

## 3. 用户认证接口

### 3.1 用户登录

```http
POST /api/auth/login
```

当前状态：后端已补齐。登录成功后返回本系统登录 token。

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

当前状态：后端已补齐。当前为轻量登出，后端校验 token，前端删除本地 token。

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

当前状态：后端已补齐。通过 Bearer token 恢复当前用户。

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

当前状态：后端已补齐。已接入 `sys_user` 表并支持基础筛选和分页。

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

当前状态：后端已补齐。已接入 `sys_user` 表。

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

当前状态：后端已补齐。已接入 `sys_user` 表。

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

当前状态：后端已补齐。当前实现为物理删除；如产品要求保留审计轨迹，建议后续改为逻辑禁用。

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

当前状态：后端已补齐。当前阶段密码仍按 `init.sql` 约定明文保存，正式上线前应改为哈希。

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

本节是后续部署类开发的主契约。除特别说明外，请求必须携带：

```http
Authorization: Bearer <login_token>
Content-Type: application/json
```

后端调用 PaaS/DCE 时统一通过 `backend/services/paas_client.py`，不要在业务模块中重复拼装 HTTP 客户端。部署类接口统一读取 `DCE_API_BASE`、`DCE_CLUSTER`、`DCE_NAMESPACE`、`DCE_TOKEN`。

### 5.0 部署公共字段

#### 5.0.1 GPU 请求字段

前端和接口请求继续使用产品字段：

```json
{
  "devices": {
    "NVIDIA/GPU": 1
  },
  "deployType": "NvidiaInfer",
  "creator": "admin"
}
```

后端内部统一映射：

| 请求设备字段 | PaaS/K8s 资源名 | deployType | GPU 厂商 | 算法包 |
| --- | --- | --- | --- | --- |
| `NVIDIA/GPU` | `nvidia.com/gpu` | `NvidiaInfer` | `NVIDIA` | `mtworkflow_x86.zip` |
| `Huawei/Ascend310P` | `huawei.com/Ascend310P` | `HuaweiInfer` | `Huawei` | `mtworkflow_arm.zip` |

Huawei 请求建议同时传顶层 `gpu_resource_name`：

```json
{
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

#### 5.0.2 创建人字段

创建人取值优先级：

```text
content.creator -> 当前登录用户 username -> X-User / X-Forwarded-User -> unknown
```

创建 Deployment / PodTemplate / Service 时建议写入：

```text
metadata.labels.instance_name
metadata.annotations.createdAt
metadata.annotations.creatorIp
metadata.annotations.deployType
```

#### 5.0.3 名称字段

查询、释放、重启、停止、日志接口统一从以下位置读取实例名：

```json
{
  "content": {
    "name": "nvidia-cuda-xxxxxx"
  }
}
```

如果缺少 `content.name`，返回 `400`。

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

兼容旧请求：

```json
{
  "msg_id": "q1",
  "serial": "s-001",
  "context": "optional"
}
```

响应：

```json
{
  "msg_id": "cluster-001",
  "serial": "serial-001",
  "context": "query cluster",
  "status": 0,
  "http_status_code": 200,
  "msg": "OK",
  "is_success": true,
  "content": {
    "items": []
  }
}
```

实现要求：

- 只做实时查询，不写 MySQL，不缓存。
- PaaS 路径为 `{DCE_API_BASE}/clusters`。
- PaaS token 过期或缺失时返回清晰错误 envelope，不暴露 Flask traceback。

### 5.2 资源预检

```http
POST /api/deploy/check-available
```

当前状态：后端已实现。已接入 PaaS 集群资源、Deployment、Service 和端口避让检查。

目标：在创建部署前判断资源是否满足，后续 `create-default` 必须先复用同一套预检逻辑。

NVIDIA 请求：

```json
{
  "msg_id": "check-001",
  "serial": "check-serial-001",
  "context": "check deploy available",
  "content": {
    "devices": {
      "NVIDIA/GPU": 1
    },
    "deployType": "NvidiaInfer",
    "creator": "admin",
    "instance_name": "qwen2.5-72b-prod"
  }
}
```

Huawei 请求：

```json
{
  "msg_id": "check-002",
  "serial": "check-serial-002",
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
  "msg_id": "check-001_Resp",
  "serial": "check-serial-001",
  "context": "check deploy available",
  "status": 0,
  "http_status_code": 200,
  "msg": "资源充足",
  "is_success": true,
  "content": {
    "can_create": true,
    "reason": "资源充足",
    "cpu_available_m": 64000,
    "mem_available_bytes": 137438953472,
    "gpu_details": {
      "nvidia.com/gpu": {
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

资源不足响应：

```json
{
  "msg_id": "check-001_Resp",
  "serial": "check-serial-001",
  "context": "check deploy available",
  "status": -1,
  "http_status_code": 400,
  "msg": "GPU 卡数量不足",
  "is_success": false,
  "content": {
    "can_create": false,
    "reason": "GPU 卡数量不足",
    "cpu_available_m": 64000,
    "mem_available_bytes": 137438953472,
    "gpu_details": {
      "nvidia.com/gpu": {
        "requested": 2,
        "available": 1,
        "total": 4,
        "used": 3
      }
    },
    "total_deployments": 3,
    "devices": {
      "NVIDIA/GPU": 2
    }
  }
}
```

实现要求：

- NVIDIA 逻辑参考旧 `app_x86_195.py`：查询 `clusters/{cluster}` 的 `resourceSummary.allocatable/allocated`，并查询 `clusters/{cluster}/namespaces/{namespace}/deployments` 估算占卡数量。
- Huawei 逻辑参考旧 `app_arm_195.py`：一期可先按 deployment 数量估算 Ascend310P 使用量；如果后续 PaaS 返回稳定 Ascend 资源字段，再切换到资源汇总判断。
- 默认资源下限：CPU `2000m`，内存 `4GiB`。
- `gpu_details` 的 key 使用 K8s 资源名，如 `nvidia.com/gpu`、`huawei.com/Ascend310P`。
- 不在预检阶段创建 Deployment、Service 或写入 `deploy_instance`。
- PaaS 查询失败返回 `502`；超时返回 `504`；参数错误返回 `400`。

### 5.3 创建推理部署

```http
POST /api/deploy/create-default
```

当前状态：后端已实现 NVIDIA 最小闭环。创建成功后会创建 PaaS Deployment / Service，并写入 `deploy_instance` 表。

NVIDIA 请求：

```json
{
  "msg_id": "create-001",
  "serial": "create-serial-001",
  "context": "create inference instance",
  "content": {
    "devices": {
      "NVIDIA/GPU": 1
    },
    "deployType": "NvidiaInfer",
    "creator": "admin"
  }
}
```

行为要求：

- 创建前必须调用资源预检；预检失败时直接返回 `400`，不得创建任何 PaaS 资源。
- 按 `deployType` / `devices` 区分 NVIDIA 与 Huawei 模板。
- 创建 Deployment 后，普通模式创建同名 NodePort Service；车间固定端口模式如继续沿用旧方案，可不创建 Service，但响应仍需返回固定端口。
- 随机端口必须避开三类端口：
  - `port_block_rule` 中的封闭端口，可直接调用 `backend/modules/ports/repository.py` 的 `resolve_blocked_ports()`。
  - PaaS/Kubernetes 已存在 Service 的 `nodePort`。
  - 宿主机已绑定端口。
- 创建成功后写入 `deploy_instance` 表，至少保存 `instance_name`、`deployment_name`、GPU 字段、`deploy_type`、`creator`、`status`、`node_ports`、`log_path`。其中 `instance_name` 是实例展示名称，`deployment_name` 是真实 Kubernetes/PaaS 工作负载名。
- PaaS 工作负载别名写入 `kpanda.io/alias-name = instance_name/client_ip`，方便在 PaaS 平台和本系统列表中对应展示。

响应：

```json
{
  "msg_id": "create-001_Resp",
  "serial": "create-serial-001",
  "context": "create inference instance",
  "status": 0,
  "http_status_code": 200,
  "msg": "OK",
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

预检失败响应同 `5.2` 的资源不足响应。PaaS 创建失败时返回：

```json
{
  "status": -1,
  "http_status_code": 502,
  "msg": "创建部署失败",
  "is_success": false,
  "content": {
    "error": "create deployment failed",
    "response": {}
  }
}
```

### 5.4 查询单个部署

```http
POST /api/deploy/retrieve
```

当前状态：后端已实现。返回前端实例详情展示字段，不透传完整 PaaS 原始对象，不写数据库。

请求：

```json
{
  "msg_id": "retrieve-001",
  "serial": "retrieve-serial-001",
  "context": "retrieve deploy",
  "content": {
    "name": "nvidia-cuda-xxxxxx"
  }
}
```

响应：

```json
{
  "msg_id": "retrieve-001_Resp",
  "serial": "retrieve-serial-001",
  "context": "retrieve deploy",
  "status": 0,
  "http_status_code": 200,
  "msg": "OK",
  "is_success": true,
  "content": {
    "deployment_name": "nvidia-cuda-xxxxxx",
    "status": "Running",
    "creator": "admin",
    "created_at": "2026-05-26 11:08:28",
    "deploy_area": "qhvgpu1",
    "replica_count": "1/1 个",
    "service_endpoint": "10.11.20.71",
    "open_ports": [30001],
    "resource_mode": "物理 GPU",
    "bound_resource": "qhvgpu1 / nvidia.com/gpu x1"
  }
}
```

实现要求：

- 查询 PaaS Deployment：`clusters/{cluster}/namespaces/{namespace}/deployments/{name}`。
- 查询 Pod 时按 Deployment 标签或 owner 关联，优先复用历史脚本中的 labelSelector 方式。
- 查询同名 Service，提取 `spec.ports[].nodePort` 作为 `open_ports`。
- `service_endpoint` 当前返回创建接口写入 Deployment annotation 的 `creatorIp`。
- `deploy_area` 返回关联 Pod 所在节点名；`replica_count` 返回 `ready_pods / replicas`。
- `resource_mode` 当前统一返回 `物理 GPU`；`bound_resource` 由节点名和 GPU resource limit 拼装。
- Deployment 不存在返回 `404`，响应体仍保持 envelope。

### 5.5 释放部署

```http
POST /api/deploy/release
```

当前状态：后端已实现。会删除同名 Service、Deployment，并删除本地 `deploy_instance` 记录。

请求：

```json
{
  "msg_id": "release-001",
  "serial": "release-serial-001",
  "context": "release deploy",
  "content": {
    "name": "nvidia-cuda-xxxxxx"
  }
}
```

响应：

```json
{
  "msg_id": "release-001_Resp",
  "serial": "release-serial-001",
  "context": "release deploy",
  "status": 0,
  "http_status_code": 200,
  "msg": "OK",
  "is_success": true,
  "content": {
    "deployment_name": "nvidia-cuda-xxxxxx",
    "status": "released",
    "deployment_delete": {},
    "service_delete": {},
    "db_delete": {
      "deployment_name": "nvidia-cuda-xxxxxx",
      "affected_rows": 1
    }
  }
}
```

实现要求：

- 删除同名 Deployment 和 Service。
- Service 不存在可视为释放成功，保持幂等。
- 成功后删除 `deploy_instance` 中的对应记录，不再保留 released 状态数据。
- 日志不保存到数据库；释放后若 Deployment/Pod 已删除，日志接口不再能通过集群实时读取该实例日志。

### 5.6 重启部署

```http
POST /api/deploy/reset
```

当前状态：后端已实现运行中实例重启。按 Deployment 查询关联 Pod，删除旧 Pod 后由 Deployment 控制器自动拉起新 Pod；不改动 Service 和端口。

已停止实例说明：

- `stop` 会把 Deployment `spec.replicas` 缩为 `0`，此时集群内没有可删除的 Pod。
- `reset` 保持原有语义，只处理运行中实例重启，不负责恢复已停止实例。
- 已停止实例再次调用 reset 时，如果没有 Pod 可删除，返回“暂无可重启的 Pod”属于预期行为。
- PaaS 报 `can not start a workload which has no historical replicas` 也符合当前平台语义：已停止工作负载没有可用于恢复的历史副本数。

请求：

```json
{
  "msg_id": "reset-001",
  "serial": "reset-serial-001",
  "context": "restart deploy",
  "content": {
    "name": "nvidia-cuda-xxxxxx"
  }
}
```

响应：

```json
{
  "msg_id": "reset-001_Resp",
  "serial": "reset-serial-001",
  "context": "restart deploy",
  "status": 0,
  "http_status_code": 200,
  "msg": "OK",
  "is_success": true,
  "content": {
    "deployment_name": "nvidia-cuda-xxxxxx",
    "status": "running",
    "pod_deletes": [
      {
        "pod_name": "nvidia-cuda-xxxxxx-abcde",
        "http_status_code": 200,
        "is_success": true
      }
    ]
  }
}
```

实现要求：

- 不调用 Deployment rollout restart，避免 GPU 单副本场景先创建新 Pod 导致 `Insufficient nvidia.com/gpu`。
- 按 `app=<deployment_name>` 查询 Pod，优先删除 Running Pod；如果没有 Running Pod，则删除查询到的 Pod。
- 删除 Pod 后由 Deployment/ReplicaSet 自动重建 Pod。
- 如果 Deployment 当前 `spec.replicas = 0`，表示已停止，reset 不做恢复启动。

### 5.7 部署列表

```http
POST /api/deploy/list
```

当前状态：后端已实现，返回实例列表页需要的精简字段。

请求：

```json
{
  "msg_id": "list-001",
  "serial": "list-serial-001",
  "context": "list deploy",
  "content": {}
}
```

响应：

```json
{
  "msg_id": "list-001_Resp",
  "serial": "list-serial-001",
  "context": "list deploy",
  "status": 0,
  "http_status_code": 200,
  "msg": "OK",
  "is_success": true,
  "content": {
    "items": [
      {
        "instance_name": "qwen2.5-72b-prod",
        "deployment_name": "nvidia-cuda-xxxxxx",
        "status": "已部署",
        "created_at": "2026-05-25 14:31:00"
      }
    ]
  }
}
```

实现要求：

- `instance_name`：实例展示名称，优先取本地 `deploy_instance.instance_name`；没有本地记录时回退为 `deployment_name`。
- `deployment_name`：真实 Kubernetes Deployment 名称，也就是工作负载 ID。
- `status`：由 PaaS Deployment 和 Pod 实时状态转换，副本正常可用显示为 `已部署`，Pod Pending 或副本还在启动中显示为 `等待`，副本数为 0 或本地状态为 stopped 显示为 `已停止`，启动失败/镜像拉取失败等明确失败状态显示为 `异常`。
- `created_at`：优先取 PaaS Deployment 注解或元数据创建时间，必要时回退本地记录创建时间。

### 5.8 停止部署

```http
POST /api/deploy/stop
```

当前状态：后端已实现。直接调用 Kubernetes API 把 Deployment 副本数缩为 `0`，并更新本地实例状态为 `stopped`。

请求：

```json
{
  "msg_id": "stop-001",
  "serial": "stop-serial-001",
  "context": "stop deploy",
  "content": {
    "name": "nvidia-cuda-xxxxxx"
  }
}
```

响应：

```json
{
  "msg_id": "stop-001_Resp",
  "serial": "stop-serial-001",
  "context": "stop deploy",
  "status": 0,
  "http_status_code": 200,
  "msg": "OK",
  "is_success": true,
  "content": {
    "deployment_name": "nvidia-cuda-xxxxxx",
    "status": "stopped",
    "response": {}
  }
}
```

说明：停止不会删除 Deployment / Service，只通过 Kubernetes 原生 PATCH 把 Deployment 副本数缩为 `0`。列表接口会把这类实例展示为 `已停止`。

### 5.9 资源不足排队

```http
POST /api/deploy/queue
```

当前状态：一期暂缓。前端适配层已预留该接口，但一期核心交付不依赖该接口。

请求：

```json
{
  "msg_id": "queue-001",
  "serial": "queue-serial-001",
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

说明：只有在重新纳入“一期资源不足排队”范围后再实现。当前资源不足应由 `check-available` 返回 `400` 和明确 reason。若后续启用该接口，建议沿用 `queue-` 作为 `msg_id` / `serial` 前缀。

### 5.10 部署日志

```http
POST /api/deploy/logs
```

当前状态：后端已实现。前端只需要传 Deployment 名称，后端会通过 Kubernetes API 查询对应 Pod 并读取 Pod 日志。

请求：

```json
{
  "msg_id": "logs-001",
  "serial": "logs-serial-001",
  "context": "deploy logs",
  "content": {
    "name": "nvidia-cuda-xxxxxx",
    "tail_lines": 200
  }
}
```

响应：

```json
{
  "msg_id": "logs-001_Resp",
  "serial": "logs-serial-001",
  "context": "deploy logs",
  "status": 0,
  "http_status_code": 200,
  "msg": "OK",
  "is_success": true,
  "content": {
    "deployment_name": "nvidia-cuda-xxxxxx",
    "pod_name": "nvidia-cuda-xxxxxx-abcde",
    "tail_lines": 200,
    "lines": [
      "service started"
    ]
  }
}
```

实现说明：

- 日志不会保存到数据库，也不读取本地 `deploy_instance`。
- 后端按 `app=<deployment_name>` 通过 Kubernetes API 查询 Deployment 对应 Pod，优先读取 Running Pod。
- 再调用 Kubernetes Pod log API 获取最近 `tail_lines` 行。
- 一期只返回最近 N 行，不做 WebSocket 或实时流。

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

当前状态：后端已补齐。已接入 MySQL `port_block_rule` 表。

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

当前状态：后端已补齐。已接入 MySQL `port_block_rule` 表。

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

当前状态：后端已补齐。已接入 MySQL `port_block_rule` 表。

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

当前状态：后端已补齐。已接入 MySQL `port_block_rule` 表。

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

当前状态：后端已补齐。已接入 MySQL `port_block_rule` 表。

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

产品化页面可以使用更直观的字段：

```json
{
  "gpu_vendor": "NVIDIA",
  "gpu_type": "NVIDIA/GPU",
  "gpu_count": 1
}
```

但部署类接口一期必须继续支持当前前端 `ui/src/api.ts` 和旧服务器接口使用的 `devices` 格式：

```json
{
  "devices": {
    "NVIDIA/GPU": 1
  },
  "deployType": "NvidiaInfer"
}
```

后端内部统一映射：

| 前端字段 | 内部资源名 | deployType | GPU 厂商 | 算法包 |
| --- | --- | --- | --- | --- |
| `NVIDIA/GPU` | `nvidia.com/gpu` | `NvidiaInfer` | `NVIDIA` | `mtworkflow_x86.zip` |
| `Huawei/Ascend310P` | `huawei.com/Ascend310P` | `HuaweiInfer` | `Huawei` | `mtworkflow_arm.zip` |

实现要求：

- 校验 `devices` 中只能出现当前支持的 GPU 字段。
- `deployType` 必须和 GPU 字段匹配。
- Huawei 场景如果传入顶层 `gpu_resource_name`，必须和映射表一致。
- 响应中的 `gpu_details` 使用 K8s 资源名作为 key，实例列表可同时返回产品字段 `gpu_type`。

### 11.2 部署 envelope 与产品字段

当前前端部署接口使用 `ApiEnvelope<T>`，后端部署模块应直接兼容：

```ts
type ApiEnvelope<T> = {
  msg_id: string;
  serial: string;
  context: string;
  content: T;
  gpu_resource_name?: string;
}
```

部署开发时不要把 envelope 字段写入 Deployment 业务 spec；只把 `content` 中的部署字段、当前登录用户和运行环境配置用于创建资源。

| 字段 | 来源 | 用途 |
| --- | --- | --- |
| `msg_id` / `serial` / `context` | 请求 envelope | 响应回传和链路追踪 |
| `content.devices` | 前端选择 | 资源预检和容器 requests/limits |
| `content.deployType` | 前端选择 | 区分 NVIDIA/Huawei 模板 |
| `content.creator` | 前端或当前用户 | 写入本地表，作为创建人审计字段 |
| `gpu_resource_name` | Huawei 兼容字段 | 指定底层 K8s 资源名 |

部署类接口当前会校验 `msg_id` / `serial` 前缀和 `context`，例如查询单个部署必须使用 `retrieve-` 前缀和 `retrieve deploy` 上下文；创建部署必须使用 `create-` 前缀和 `create inference instance` 上下文。前端不要复用其他动作的 envelope。

### 11.3 端口字段

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

创建部署随机端口时不通过 HTTP 调用 `/api/port-list/resolve`，而是在后端内部直接复用端口模块的 repository/service，避免 `jushi-api` 自己请求自己。

### 11.4 告警字段

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
POST /api/users/create
POST /api/users/update
POST /api/users/delete
POST /api/users/reset-password
POST /api/cluster
POST /api/deploy/check-available
POST /api/deploy/create-default
POST /api/deploy/retrieve
POST /api/deploy/release
POST /api/deploy/reset
POST /api/deploy/stop
POST /api/deploy/list
POST /api/deploy/logs
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

其中已接入真实 MySQL 或 PaaS 能力的接口：

```text
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
GET  /api/users/list
POST /api/users/create
POST /api/users/update
POST /api/users/delete
POST /api/users/reset-password
POST /api/cluster
POST /api/deploy/check-available
POST /api/deploy/create-default
POST /api/deploy/retrieve
GET  /api/port-list/list
POST /api/port-list/add
PUT  /api/port-list/update/{item_id}
DELETE /api/port-list/delete/{item_id}
GET  /api/port-list/resolve
```

部署类下一步优先补齐实现：

```text
POST /api/deploy/list
POST /api/deploy/release
POST /api/deploy/reset
```

后续业务增强或暂缓接口：

```text
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
请求头补充 Authorization: Bearer <login_token>
```
