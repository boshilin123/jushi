# 聚时 AI 推理资源管理平台一期开发方案

## 一、方案定位

一期目标不是建设复杂平台治理体系，而是围绕“用户登录 + 推理实例生命周期 + 资源查询 + Pod 操作 + 端口避让 + 日志告警”形成可交付版本。

技术路线：

```text
后端：Python + Flask + MySQL + Shell + Docker Compose
前端：React + TypeScript + Vite + Nginx
平台底座：PaaS / Kubernetes
```

现有后端已经具备推理部署的基础能力，包括资源预检、创建部署、查询部署、释放部署、重启部署和部署列表接口。创建接口已经支持创建 Deployment + NodePort Service，并写入 instance_name、createdAt、creatorIp、deployType 等标记；creator 保存在本地实例表用于审计。

端口避让服务已经具备查询、新增、修改、删除和解析快照接口，可用于创建实例时提前排除不允许随机分配的端口。

因此，一期不建议引入 Java、微服务、复杂中台、多租户、审批流或完整 RBAC，而是在现有 Python Flask 能力上做产品化封装。

## 二、后端模块划分

一期后端建议按业务域拆分接口：

```text
1. 用户认证接口
2. 用户管理接口
3. 集群与部署接口
4. 封闭端口 / 端口避让接口
5. 集群资源接口
6. Pod 运维接口
7. 告警接口
8. 日志与审计接口
9. 系统与接口文档接口
```

模块边界：

- 用户认证只做登录、登出和当前用户查询。
- 用户管理只做基础用户增删改查和重置密码，不做复杂 RBAC。
- 部署接口复用现有核心能力，并补齐前端已预留的停止、排队和日志接口。
- 封闭端口统一使用 `/api/port-list/*`，不再提供 `/api/ports/allowlist/*`。
- 集群资源和 Pod 类接口通过 PaaS API 或 Kubernetes API 查询。
- 告警、日志和审计按前端页面需要补必要接口，不做复杂规则引擎。
- Swagger 文档通过 `/api/docs` 提供，根路径 `/` 暂不占用，后续留给前端或网关。

## 三、接口分类设计

### 1. 用户类接口

一期只做基础登录和用户管理，不做复杂 RBAC、多租户、菜单权限细分。

```http
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me

GET  /api/users/list
POST /api/users/create
POST /api/users/update
POST /api/users/delete
POST /api/users/reset-password
```

数据表：

```sql
sys_user
```

建议字段：

```text
id
username
password
real_name
role
status
created_at
updated_at
```

角色先简单处理：

```text
admin     管理员
operator  运维人员
user      普通用户
```

### 2. 集群与部署接口

部署类复用现有后端的核心能力，并补齐前端适配层已预留的接口：

```http
POST /api/cluster
POST /api/deploy/check-available
POST /api/deploy/create-default
POST /api/deploy/retrieve
POST /api/deploy/release
POST /api/deploy/reset
POST /api/deploy/list
POST /api/deploy/stop
POST /api/deploy/queue
POST /api/deploy/logs
```

用途分别是集群查询、资源预检、创建部署、查询部署、释放部署、重启部署、部署列表、停止部署、资源不足排队和部署 Pod 描述。

当前后端已经具备除 `queue` 外的主要部署能力；`logs` 入口当前返回接近 `kubectl describe pod` 的纯文本排障信息。

### 3. NVIDIA 和 Huawei GPU 区分

主服务创建实例时必须区分 NVIDIA GPU 和 Huawei Ascend GPU。

NVIDIA 请求示例：

```json
{
  "content": {
    "devices": {
      "NVIDIA/GPU": 1
    },
    "deployType": "NvidiaInfer",
    "creator": "alice"
  }
}
```

Huawei 请求示例：

```json
{
  "gpu_resource_name": "huawei.com/Ascend310P",
  "content": {
    "devices": {
      "Huawei/Ascend310P": 1
    },
    "deployType": "HuaweiInfer",
    "creator": "alice"
  }
}
```

前端可以继续使用当前 `ui/src/api.ts` 的请求结构；后端内部再归一化 GPU 厂商、资源名和算法包：

```text
gpu_vendor: NVIDIA / Huawei
gpu_type: NVIDIA/GPU / Huawei/Ascend310P
gpu_count: 1
deployType: NvidiaInfer / HuaweiInfer
```

后端内部映射：


| 前端选择   | 后端 devices          | K8s 资源名                 | 算法包                  |
| ------ | ------------------- | ----------------------- | -------------------- |
| NVIDIA | `NVIDIA/GPU`        | `nvidia.com/gpu`        | `mtworkflow_x86.zip` |
| Huawei | `Huawei/Ascend310P` | `huawei.com/Ascend310P` | `mtworkflow_arm.zip` |


建议抽出 GPU profile 配置：

```python
GPU_PROFILE = {
    "NVIDIA": {
        "device_key": "NVIDIA/GPU",
        "resource_name": "nvidia.com/gpu",
        "deploy_type": "NvidiaInfer",
        "package": "mtworkflow_x86.zip",
        "workdir": "mtworkflow_x86",
        "image": "nvidia/cuda:11.6.2-cudnn8-devel-ubuntu20.04_v1"
    },
    "Huawei": {
        "device_key": "Huawei/Ascend310P",
        "resource_name": "huawei.com/Ascend310P",
        "deploy_type": "HuaweiInfer",
        "package": "mtworkflow_arm.zip",
        "workdir": "mtworkflow_arm",
        "image": "ascend-ubuntu20.04-8.1.rc1"
    }
}
```

### 4. 封闭端口 / 端口避让类接口

端口避让接口由 `jushi-api` 中的 `backend/modules/ports` 统一提供，不再单独部署 `jushi-port-list` 容器：

```http
GET    /api/port-list/list
POST   /api/port-list/add
PUT    /api/port-list/update/{item_id}
DELETE /api/port-list/delete/{item_id}
GET    /api/port-list/resolve
```

页面名称建议统一为“封闭端口管理”或“端口避让规则”。

一期明确不再兼容以下旧路径：

```text
/api/ports/allowlist/list
/api/ports/allowlist/create
/api/ports/allowlist/delete
```

前端需要把端口接口改为 `/api/port-list/*`。

主服务创建实例时直接复用端口模块生成避让快照，对外仍保留：

```http
GET /api/port-list/resolve
```

拿到被封闭端口后，在随机端口时避开这些端口。

### 5. 集群资源类接口

资源中心新增接口：

```http
GET /api/resources/summary
GET /api/resources/nodes
GET /api/resources/gpus
GET /api/resources/quotas
```

数据来源可以二选一：

```text
1. PaaS 平台 API
2. Kubernetes API / kubectl
```

现阶段建议优先复用 PaaS API。

### 6. Pod 类接口

Pod 类接口用于前端查看实例运行状态，以及执行基础操作。

```http
GET  /api/pods/list
GET  /api/pods/detail
GET  /api/pods/logs
POST /api/pods/delete
POST /api/pods/restart
```

`/api/deploy/retrieve` 面向部署实例，适合实例中心；`/api/pods/*` 面向运维排查，适合 Pod 管理页面。

一期日志先返回最近 N 行，不做实时流式日志。

### 7. 告警类接口

一期告警根据前端页面需要提供必要能力，不做复杂告警规则引擎。

```http
POST /api/alerts/list
POST /api/alerts/create
POST /api/alerts/resolve
POST /api/alerts/ignore
```

一期告警来源：

```text
资源不足
创建实例失败
释放实例失败
Pod Pending
Pod Failed
容器重启次数过高
端口服务不可用
集群资源查询失败
```

数据表：

```sql
alert_event
```

状态：

```text
open
resolved
ignored
```

### 8. 日志类接口

日志分三类：

```text
1. 操作日志
2. 实例 / Pod 运行日志
3. 审计日志导入导出
```

操作日志接口：

```http
GET /api/logs/operations
```

实例日志接口：

```http
GET /api/logs/instance
GET /api/logs/pod
```

审计接口需要兼容当前前端适配层：

```http
POST /api/audits/list
POST /api/audits/import
POST /api/audits/export
```

一期实现方式：

- `/api/deploy/logs` 保留历史接口名，但当前返回 Pod describe 风格的纯文本排障信息。
- Pod 通过 `app=<deployment_name>` 查找，优先展示 Running Pod。
- 暂不做实时 WebSocket 日志，也不保存容器 stdout 到数据库。

操作日志表：

```sql
operation_log
```

## 四、一期数据库表建议

核心表：

```text
sys_user
deploy_instance
port_block_rule
operation_log
alert_event
```

如需支持 GPU 区分和资源快照，可增加：

```text
resource_snapshot
```

优先级：


| 表                   | 是否必须 | 说明                      |
| ------------------- | ---- | ----------------------- |
| `sys_user`          | 必须   | 登录和用户管理                 |
| `deploy_instance`   | 必须   | 实例中心产品化记录               |
| `port_block_rule`   | 建议   | 后续替代 blocked_ports.json |
| `operation_log`     | 必须   | 操作追踪                    |
| `alert_event`       | 必须   | 告警中心                    |
| `resource_snapshot` | 可选   | 资源中心统计                  |


## 五、后端服务结构建议

建议代码结构：

```text
backend/
├── __init__.py
├── app.py
├── config.py
├── requirements.txt
├── common/
│   ├── response.py
│   └── __init__.py
├── modules/
│   ├── auth/
│   │   ├── routes.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   └── schema.py
│   ├── users/
│   │   ├── routes.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   └── schema.py
│   ├── deploy/
│   │   ├── routes.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── schema.py
│   │   └── model.py
│   ├── ports/
│   │   ├── routes.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   └── schema.py
│   ├── resources/
│   │   ├── routes.py
│   │   ├── service.py
│   │   └── schema.py
│   ├── pods/
│   │   ├── routes.py
│   │   ├── service.py
│   │   └── schema.py
│   ├── alerts/
│   │   ├── routes.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   └── schema.py
│   ├── logs/
│   │   ├── routes.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   └── schema.py
│   ├── docs/
│   │   └── routes.py
│   └── system/
│       └── routes.py
├── services/
│   ├── paas_client.py
│   ├── k8s_client.py
│   ├── gpu_profile.py
│   └── shell_runner.py
├── db/
│   ├── mysql.py
│   └── init.sql
├── scripts/
│   ├── start.sh
│   └── stop.sh
└── Dockerfile
```

保留原始 `app_xxx.py` 文件作为部署适配参考，新版本逻辑逐步迁移到 `modules/*/service.py` 和 `services/*` 中。

`backend/services/` 和 `modules/*/service.py` 的区别：

```text
modules/deploy/service.py  负责“创建推理实例”等业务流程
services/paas_client.py    负责“调用 PaaS API”等基础能力
```

## 六、Docker Compose 服务规划

```yaml
services:
  jushi-frontend:
    image: jushi-frontend
    ports:
      - "80:80"

  jushi-api:
    image: jushi-api
    ports:
      - "8080:8080"
    env_file:
      - .env.example
    depends_on:
      - jushi-mysql

  jushi-mysql:
    image: mysql:8.0
    ports:
      - "3306:3306"
    volumes:
      - ./mysql/data:/var/lib/mysql
      - ./backend/db/init.sql:/docker-entrypoint-initdb.d/init.sql
```

## 七、开发人天建议

按当前接口范围完整评估，总人天约为：

```text
约 23 人天
```

如果必须控制在 2 人 10 天内，需要按下方压缩项收敛范围。

模块拆分：


| 模块                     | 后端人天   | 前端人天  | 合计        |
| ---------------------- | ------ | ----- | --------- |
| 工程整理、Docker Compose、配置 | 1.5    | 0.5   | 2         |
| 用户登录与用户管理              | 1.5    | 1     | 2.5       |
| 部署接口整合与补齐              | 2.5    | 1     | 3.5       |
| NVIDIA / Huawei GPU 区分 | 1.5    | 0.5   | 2         |
| 封闭端口 5 个接口             | 0.5    | 1     | 1.5       |
| 集群资源接口                 | 1.5    | 1     | 2.5       |
| Pod 查询与基础操作            | 1.5    | 1     | 2.5       |
| 告警接口与页面                | 1      | 1     | 2         |
| 日志与审计接口及页面             | 1.5    | 1     | 2.5       |
| 联调、测试、文档               | 1      | 1     | 2         |
| **合计**                 | **14** | **9** | **23 人天** |


如需压缩到 20 人天：

- Pod 操作只做查询、日志、删除，重启复用 deploy/reset。
- 告警只做 list 和 resolve，不做 create。
- 日志只做操作日志、实例日志和基础审计列表，不做实时日志。
- 集群资源只做 summary 和 nodes，不做复杂 GPU 明细。

## 八、对外表述

结合现有后端能力和前端页面需求，一期后端框架采用 Python + Flask + MySQL + Shell + Docker Compose，前端框架保持 React + TypeScript + Vite 不变。后端按业务模块分包，并采用 `routes.py / service.py / repository.py / schema.py / model.py` 的 Python 分层方式。用户类只做登录和用户管理；部署类复用现有部署接口，并补齐停止、排队和日志接口，同时支持 NVIDIA 与 Huawei GPU 类型区分；封闭端口统一使用 `/api/port-list/`*；集群和 Pod 类接口通过 PaaS 平台或 Kubernetes 获取资源和运行状态；告警、日志与审计按前端必要页面提供基础接口。该方案不做复杂 RBAC、多租户、审批流和云弹性，重点保证推理实例生命周期、资源查询、Pod 管理、端口避让、日志告警等核心能力可交付。
