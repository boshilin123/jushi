# BlueDot 后端接口对接说明

本文档基于素材 `jushipaasapi.zip` 中的 Flask 接口整理，目标是让当前前端演示版可以平滑接入真实后端。

## 1. 运行方式

当前前端仍以假数据演示为主。正式接入时设置环境变量：

```bash
VITE_API_BASE_URL=http://后端服务地址
```

已新增前端接口适配文件：

- `src/api.ts`

该文件封装了创建实例、资源预检、查询、停止、释放、重启、排队、实例日志、端口白名单、告警、审计日志、日志导入与导出接口的请求结构。

## 2. 统一请求结构

```json
{
  "msg_id": "c-001",
  "serial": "s-001",
  "context": "create inference instance",
  "content": {}
}
```

通用字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `msg_id` | string | 是 | 请求 ID，后端响应会返回 `${msg_id}_Resp` |
| `serial` | string | 是 | 请求序列号 |
| `context` | string | 是 | 请求上下文说明 |
| `content` | object | 是 | 业务请求体 |
| `gpu_resource_name` | string | 否 | Ascend 场景使用，如 `huawei.com/Ascend310P` |

通用 Header：

| Header | 说明 |
| --- | --- |
| `Content-Type: application/json` | JSON 请求 |
| `X-User` | 创建人或操作人 |
| `X-Forwarded-User` | 反向代理透传用户 |
| `X-Forwarded-For` | 车间固定端口模式或审计 IP |

## 3. 创建实例

接口：

```http
POST /api/deploy/create-default
```

NVIDIA 示例：

```json
{
  "msg_id": "c-001",
  "serial": "s-001",
  "context": "create inference instance",
  "content": {
    "devices": { "NVIDIA/GPU": 1 },
    "deployType": "NvidiaInfer",
    "creator": "admin"
  }
}
```

Ascend 示例：

```json
{
  "msg_id": "c-001",
  "serial": "s-001",
  "gpu_resource_name": "huawei.com/Ascend310P",
  "context": "create inference instance",
  "content": {
    "devices": { "Huawei/Ascend310P": 1 },
    "deployType": "HuaweiInfer",
    "creator": "admin"
  }
}
```

创建字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `content.devices` | object | 是 | 资源类型到数量的映射 |
| `content.deployType` | string | 是 | `NvidiaInfer` 或 `HuaweiInfer` |
| `content.creator` | string | 是 | 创建人，后端也会兜底读取 Header |
| `gpu_resource_name` | string | Ascend 必填 | K8s 资源名 |

当前后端自动生成或模板固定的字段：

| 字段 | 后端行为 | 前端处理 |
| --- | --- | --- |
| 实例 / Deployment 名 | `nvidia-cuda-${uuid}` | 前端只保留“展示名称” |
| 镜像地址 | 后端模板写死 | 前端不作为入参 |
| 容器端口 | 默认 `8018` | 前端展示策略，不手填 |
| NodePort | 后端自动选择并避让冲突 | 前端展示策略，不手填 |
| 日志路径 | `/workspace/Alg/log/${name}` | 从创建响应读取 |

成功响应核心字段：

```json
{
  "status": 0,
  "is_success": true,
  "content": {
    "deployment_name": "nvidia-cuda-xxxxxx",
    "node_ports": [
      { "name": "tcp-8018", "port": 30001 },
      { "name": "tcp-8019", "port": 35001 }
    ],
    "devices": { "NVIDIA/GPU": 1 },
    "gpu_type": "NVIDIA/GPU",
    "deployType": "NvidiaInfer",
    "log_path": "/workspace/Alg/log/nvidia-cuda-xxxxxx"
  }
}
```

## 4. 资源预检

接口：

```http
POST /api/deploy/check-available
```

请求体与创建接口一致，后端只读取 `content.devices`。

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `can_create` | boolean | 是否可创建 |
| `reason` | string | 不可创建或资源充足原因 |
| `cpu_available_m` | number | 可用 CPU，单位 m |
| `mem_available_bytes` | number | 可用内存，单位 bytes |
| `gpu_details` | object | GPU 请求、可用、总量、已用 |
| `total_deployments` | number | 当前 deployment 数 |
| `devices` | object | 本次请求设备 |

前端建议：

- `can_create=true`：按钮展示“确认创建”。
- `can_create=false`：按钮展示“排队”，并允许保存到待发布。
- 高优先级队列需要后端新增队列接口或在创建响应中返回排队状态。

## 5. 实例运维接口

### 查询单个部署

```http
POST /api/deploy/retrieve
```

```json
{
  "msg_id": "retrieve-001",
  "serial": "s-001",
  "context": "retrieve deploy",
  "content": { "name": "nvidia-cuda-xxxxxx" }
}
```

### 释放部署

```http
POST /api/deploy/release
```

```json
{
  "msg_id": "release-001",
  "serial": "s-001",
  "context": "release deploy",
  "content": { "name": "nvidia-cuda-xxxxxx" }
}
```

### 重启部署

```http
POST /api/deploy/reset
```

```json
{
  "msg_id": "reset-001",
  "serial": "s-001",
  "context": "restart deploy",
  "content": { "name": "nvidia-cuda-xxxxxx" }
}
```

### 部署列表

```http
POST /api/deploy/list
```

### 停止部署

```http
POST /api/deploy/stop
```

```json
{
  "msg_id": "stop-001",
  "serial": "s-001",
  "context": "stop deploy",
  "content": { "name": "nvidia-cuda-xxxxxx" }
}
```

> 素材接口中未明确停止接口，前端已预留 `/api/deploy/stop`。如果后端以 `scale=0` 或更新状态实现停止，可保持前端契约不变。

### 资源不足排队

```http
POST /api/deploy/queue
```

```json
{
  "msg_id": "queue-001",
  "serial": "s-001",
  "context": "queue deploy",
  "content": {
    "name": "nvidia-cuda-auto-001",
    "priority": "high",
    "reason": "current resource is full"
  }
}
```

响应建议返回：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `queue_id` | string | 排队任务 ID |
| `rank` | number | 当前排队序号 |
| `priority` | string | `high` / `normal` / `low` |
| `status` | string | `queued` / `scheduled` / `failed` |

### 实例日志

```http
POST /api/deploy/logs
```

```json
{
  "msg_id": "logs-001",
  "serial": "s-001",
  "context": "deploy logs",
  "content": { "name": "nvidia-cuda-xxxxxx" }
}
```

响应建议：

```json
{
  "content": [
    { "time": "2026-05-18 09:15:00", "level": "INFO", "message": "Instance started successfully" }
  ]
}
```

## 6. 端口白名单接口

端口白名单用于创建实例资源预检，避免 NodePort 冲突。前端已做本地唯一性提示，后端仍需做强校验：

```text
端口需为 1-65535 的整数，且不能重复。
```

### 列表

```http
POST /api/ports/allowlist/list
```

请求：

```json
{
  "msg_id": "ports-list-001",
  "serial": "s-001",
  "context": "list port allowlist",
  "content": {}
}
```

响应 `content`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 记录 ID |
| `port` | number | 端口号 |
| `name` | string | 端口名称 / 用途 |
| `creator` | string | 设置人员 |
| `created_at` | string | 设置时间 |
| `remark` | string | 备注 |

### 新增

```http
POST /api/ports/allowlist/create
```

```json
{
  "msg_id": "ports-create-001",
  "serial": "s-001",
  "context": "create port allowlist",
  "content": {
    "port": 50056,
    "name": "web api",
    "creator": "admin",
    "remark": "debug allowlist"
  }
}
```

### 删除

```http
POST /api/ports/allowlist/delete
```

```json
{
  "msg_id": "ports-delete-001",
  "serial": "s-001",
  "context": "delete port allowlist",
  "content": { "id": "2c8004b2", "port": 50056 }
}
```

## 7. 告警接口

### 告警列表

```http
POST /api/alerts/list
```

```json
{
  "msg_id": "alerts-list-001",
  "serial": "s-001",
  "context": "list alerts",
  "content": {
    "level": "all",
    "limit": 5
  }
}
```

响应 `content` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 告警 ID |
| `level` | string | `high` / `medium` / `low` |
| `category` | string | 异常类别，如虚拟化异常、峰值重叠风险 |
| `title` | string | 告警标题 |
| `target` | string | 节点、vGPU、实例或端口 |
| `description` | string | 告警描述 |
| `action` | string | 推荐处理动作 |
| `created_at` | string | 发生时间 |
| `status` | string | `open` / `resolved` |

### 标记解决

```http
POST /api/alerts/resolve
```

```json
{
  "msg_id": "alerts-resolve-001",
  "serial": "s-001",
  "context": "resolve alert",
  "content": {
    "id": "alert-001",
    "resolver": "admin"
  }
}
```

前端成功 toast：

```text
已标记解决，可在历史记录查看
```

## 8. 审计日志接口

### 审计列表

```http
POST /api/audits/list
```

```json
{
  "msg_id": "audits-list-001",
  "serial": "s-001",
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

响应建议：

```json
{
  "content": {
    "list": [
      {
        "operator": "admin",
        "action": "虚拟卡推荐",
        "target": "node-gpu-03 / vGPU-03-1",
        "result": "成功",
        "created_at": "2026-05-18 14:22:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

### 导入日志

```http
POST /api/audits/import
Content-Type: multipart/form-data
```

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `file` | file | Excel 或 PDF 文件 |

前端交互：选择文件后展示上传与解析进度，进度到 100% 后才允许点击“确定”。

### 导出日志

```http
POST /api/audits/export
```

```json
{
  "msg_id": "audits-export-001",
  "serial": "s-001",
  "context": "export audits",
  "content": {
    "format": "excel",
    "result": "all",
    "time_range": "7d"
  }
}
```

响应建议：

```json
{
  "content": { "download_url": "https://example.com/audit-export.xlsx" }
}
```

## 9. 需要后端确认或补充

1. 是否继续沿用 `content.devices` 的展示资源名，还是统一改为 K8s 资源名。
2. 创建接口是否需要支持前端展示名称、任务优先级、队列状态。
3. 资源不足时是返回 `can_create=false`，还是直接创建排队任务。
4. 停止接口是否采用 `/api/deploy/stop`，或由释放/缩容接口承载。
5. 日志接口是否采用 `/api/deploy/logs`，是否需要流式输出。
6. vGPU 最小 / 最大预测值是否由后端返回，目前前端按演示规则展示。
7. 端口白名单是否按本文件 CRUD 契约提供。
8. 告警与审计日志是否统一分页、排序与导出权限。

## 10. 当前前端字段优化结果

创建弹窗最终保留：

- 展示名称
- 部署类型
- 资源设备
- 设备数量
- 创建人
- 请求 ID
- 请求序列
- 请求上下文
- K8s 资源名
- NodePort 策略
- 推荐方案
- 资源预检

已移除或降级为后端默认策略说明：

- 手动镜像地址
- 手动服务端口
- 健康检查路径
- Team
- 手动物理 GPU 分配
