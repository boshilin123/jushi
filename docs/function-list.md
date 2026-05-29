# 聚时 AI 推理资源管理平台功能清单

本文档汇总当前项目一期已实现、部分实现和暂缓实现的功能范围，覆盖前端页面、后端接口、数据库表、外部系统依赖和已知注意事项。简版 Excel 清单见 `docs/function-list.xls`。

## 1. 总体定位

聚时 AI 推理资源管理平台面向算力资源运维和推理实例管理场景，当前一期重点是把原有 PaaS/DCE、Kubernetes、MySQL 和前端管理页面串起来，形成可登录、可查询资源、可创建/管理推理实例、可避让端口、可扫描告警、可查看审计日志的管理端。

当前后端是 Flask API，前端是 React + Vite，部署形态为三容器：

| 服务 | 容器 | 说明 |
| --- | --- | --- |
| 前端 | `jushi-frontend` | Nginx 托管前端构建产物，对外端口 `18000` |
| 后端 | `jushi-api` | Flask API，按业务模块注册蓝图 |
| 数据库 | `jushi-mysql` | MySQL 8.0，保存用户、部署实例、端口规则、告警、审计、资源快照 |

## 2. 通用基础能力

### 2.1 系统健康检查

| 项目 | 内容 |
| --- | --- |
| 功能 | 提供后端健康检查，用于确认 Flask 服务是否启动 |
| 接口 | `GET /api/health` |
| 状态 | 已实现 |
| 鉴权 | 免登录 |
| 返回 | 基础健康状态 |
| 主要文件 | `backend/modules/system/routes.py` |

### 2.2 Swagger / OpenAPI 文档

| 项目 | 内容 |
| --- | --- |
| 功能 | 提供 Swagger UI 和 OpenAPI JSON，便于调试后端接口 |
| 页面 | `GET /api/docs` |
| JSON | `GET /api/docs/openapi.json` |
| 状态 | 已实现 |
| 鉴权 | 开发阶段免登录 |
| 主要文件 | `backend/modules/docs/routes.py`、`backend/modules/docs/openapi_specs/` |
| 注意事项 | OpenAPI 规格在模块导入时构建，部署后若页面未展示新接口，通常是服务仍在运行旧代码或旧镜像 |

### 2.3 统一鉴权拦截

| 项目 | 内容 |
| --- | --- |
| 功能 | 对 `/api/*` 接口做 Bearer Token 拦截 |
| 免鉴权 | `/api/health`、`/api/auth/login`、`/api/docs*` |
| 状态 | 已实现 |
| 主要文件 | `backend/app.py`、`backend/common/auth.py` |
| 行为 | 未登录返回 401，禁用用户返回 403 |

### 2.4 跨域支持

| 项目 | 内容 |
| --- | --- |
| 功能 | 支持 Swagger UI、前端页面跨域访问后端 API |
| 状态 | 已实现 |
| 方式 | 优先使用 `flask_cors.CORS`，缺失依赖时使用后置响应头兜底 |
| 主要文件 | `backend/app.py` |

### 2.5 操作审计中间件

| 项目 | 内容 |
| --- | --- |
| 功能 | 自动记录部署相关接口调用，用于审计日志 |
| 覆盖接口 | `check-available`、`create-default`、`retrieve`、`release`、`reset`、`list` |
| 状态 | 已实现 |
| 数据表 | `operation_log` |
| 主要文件 | `backend/app.py`、`backend/modules/logs/repository.py` |
| 注意事项 | 当前主要记录部署类操作，其他业务动作是否纳入审计可后续扩展 |

## 3. 用户认证功能

### 3.1 登录

| 项目 | 内容 |
| --- | --- |
| 功能 | 用户使用账号密码登录，返回 Bearer Token 和用户信息 |
| 接口 | `POST /api/auth/login` |
| 状态 | 已实现 |
| 数据表 | `sys_user` |
| 默认账号 | `admin` |
| 主要文件 | `backend/modules/auth/routes.py`、`backend/modules/auth/service.py`、`backend/modules/auth/repository.py` |

### 3.2 登出

| 项目 | 内容 |
| --- | --- |
| 功能 | 登出接口，供前端统一流程调用 |
| 接口 | `POST /api/auth/logout` |
| 状态 | 已实现 |
| 说明 | 当前主要是无状态 Token 语义下的成功响应，不做服务端会话销毁 |

### 3.3 当前用户

| 项目 | 内容 |
| --- | --- |
| 功能 | 根据 Authorization Token 返回当前登录用户 |
| 接口 | `GET /api/auth/me` |
| 状态 | 已实现 |
| 鉴权 | 需要 Bearer Token |

## 4. 用户管理功能

用户管理功能基于 `sys_user` 表，支持后台管理账号、角色和状态。

| 功能 | 接口 | 状态 | 说明 |
| --- | --- | --- | --- |
| 用户列表 | `GET /api/users/list` | 已实现 | 支持按关键字、角色、状态筛选 |
| 创建用户 | `POST /api/users/create` | 已实现 | 创建账号、密码、姓名、角色、状态 |
| 更新用户 | `POST /api/users/update` | 已实现 | 更新姓名、角色、状态等基础字段 |
| 删除用户 | `POST /api/users/delete` | 已实现 | 当前为物理删除 |
| 重置密码 | `POST /api/users/reset-password` | 已实现 | 管理员重置用户密码 |

字段说明：

| 字段 | 说明 |
| --- | --- |
| `username` | 登录用户名，唯一 |
| `password` | 当前阶段明文保存，后续上线前应改为哈希 |
| `real_name` | 展示姓名 |
| `role` | `admin`、`operator`、`user` |
| `status` | `active`、`disabled` |
| `created_at` / `updated_at` | 创建和更新时间 |

## 5. 集群查询功能

| 项目 | 内容 |
| --- | --- |
| 功能 | 查询 PaaS/DCE 集群列表或集群基础信息 |
| 接口 | `POST /api/cluster` |
| 状态 | 已实现 |
| 外部依赖 | PaaS/DCE API |
| 配置 | `.env.example` 中的 DCE/PaaS 地址和 Token |
| 主要文件 | `backend/modules/cluster/`、`backend/services/paas_client.py` |
| 注意事项 | PaaS/DCE Token 与平台登录 Token 是两套不同概念 |

## 6. 推理部署生命周期功能

部署模块是一期开核心功能，围绕资源预检、创建、查询、列表、释放、重启、停止和日志排查展开。

### 6.1 资源预检

| 项目 | 内容 |
| --- | --- |
| 功能 | 创建实例前检查资源是否满足，例如 GPU/NPU、CPU、内存、端口避让等 |
| 接口 | `POST /api/deploy/check-available` |
| 状态 | 已实现 |
| 输入 | `devices`、`deployType`、`creator`、`instance_name` 等 |
| 输出 | 是否可创建、资源详情、失败原因 |
| 数据来源 | Kubernetes/PaaS 资源、GPU profile、端口规则 |
| 主要文件 | `backend/modules/deploy/service.py` |

### 6.2 创建推理部署

| 项目 | 内容 |
| --- | --- |
| 功能 | 创建默认推理实例，生成 Kubernetes Deployment/Service，并保存本地记录 |
| 接口 | `POST /api/deploy/create-default` |
| 状态 | 已实现 |
| 数据表 | `deploy_instance` |
| 输出 | `deployment_name`、端口、GPU 类型、日志路径等 |
| 并发控制 | 使用 MySQL `GET_LOCK` 做创建链路串行锁 |
| 注意事项 | 创建成功后写入本地 MySQL，供实例列表和告警关联使用 |

### 6.3 查询单个部署

| 项目 | 内容 |
| --- | --- |
| 功能 | 查询单个部署详情，合并本地记录、PaaS/Kubernetes 状态、Pod 状态等 |
| 接口 | `POST /api/deploy/retrieve` |
| 状态 | 已实现 |
| 输入 | `content.name` |
| 输出 | 实例基本信息、状态、端口、Pod 信息等 |

### 6.4 部署列表

| 项目 | 内容 |
| --- | --- |
| 功能 | 查询平台创建的部署实例列表 |
| 接口 | `POST /api/deploy/list` |
| 状态 | 已实现 |
| 数据表 | `deploy_instance` |
| 展示字段 | `instance_name`、`deployment_name`、`status`、`created_at` |
| 注意事项 | `released` 状态默认不在列表展示 |

### 6.5 释放部署

| 项目 | 内容 |
| --- | --- |
| 功能 | 删除或释放部署资源，并更新本地实例状态 |
| 接口 | `POST /api/deploy/release` |
| 状态 | 已实现 |
| 行为 | 调用 PaaS/Kubernetes 释放资源，本地记录软删除为 `released` |

### 6.6 重启部署

| 项目 | 内容 |
| --- | --- |
| 功能 | 重启已部署实例 |
| 接口 | `POST /api/deploy/reset` |
| 状态 | 已实现 |
| 注意事项 | 对已停止工作负载，PaaS 可能返回无历史副本无法启动的语义错误 |

### 6.7 停止部署

| 项目 | 内容 |
| --- | --- |
| 功能 | 停止部署实例 |
| 接口 | `POST /api/deploy/stop` |
| 状态 | 已实现 |
| 行为 | 调整工作负载状态，并更新本地状态 |

### 6.8 部署日志 / Pod 描述

| 项目 | 内容 |
| --- | --- |
| 功能 | 返回部署排查文本，便于 Swagger 或前端直接查看 |
| 接口 | `POST /api/deploy/logs` |
| 状态 | 已实现 |
| 返回类型 | 成功时返回 `text/plain` |

### 6.9 资源不足排队

| 项目 | 内容 |
| --- | --- |
| 功能 | 资源不足时进入排队 |
| 接口 | `POST /api/deploy/queue` |
| 状态 | 一期暂缓 / 文档保留 |
| 说明 | 当前一期明确不优先建设复杂排队治理 |

## 7. 端口封闭与端口避让功能

端口模块用于维护不能被实例随机分配使用的端口。

| 功能 | 接口 | 状态 | 数据表 | 说明 |
| --- | --- | --- | --- | --- |
| 查询封闭端口 | `GET /api/port-list/list` | 已实现 | `port_block_rule` | 返回所有封闭端口 |
| 新增封闭端口 | `POST /api/port-list/add` | 已实现 | `port_block_rule` | 唯一索引防止重复端口 |
| 更新封闭端口 | `PUT /api/port-list/update/{item_id}` | 已实现 | `port_block_rule` | 修改端口或备注 |
| 删除封闭端口 | `DELETE /api/port-list/delete/{item_id}` | 已实现 | `port_block_rule` | 删除后端口可重新参与分配 |
| 端口避让快照 | `GET /api/port-list/resolve` | 已实现 | `port_block_rule` | 创建实例前可调用，输出避让端口集合 |

## 8. 集群资源中心功能

资源模块用于支撑首页和资源中心的数据展示。

| 功能 | 接口 | 状态 | 说明 |
| --- | --- | --- | --- |
| 资源总览 | `GET /api/resources/summary` | 已实现 | 返回节点、GPU、显存、资源使用等总览 |
| 节点列表 | `GET /api/resources/nodes` | 已实现 | 返回节点资源状态 |
| GPU 统计 | `GET /api/resources/gpus` | 已实现 | 返回 GPU/NPU 资源统计 |
| 配额信息 | `GET /api/resources/quotas` | 已实现 | 返回命名空间配额 |
| 显卡/卡片列表 | `GET /api/resources/cards` | 已实现 | 返回资源卡片信息 |
| 资源趋势 | `GET /api/resources/trend` | 已实现 | 从 `resource_snapshot` 读取趋势 |
| 推荐策略 | `GET /api/resources/recommendation` | 已实现 | 返回资源推荐或调度建议 |

资源快照说明：

| 项目 | 内容 |
| --- | --- |
| 数据表 | `resource_snapshot` |
| 写入节流 | 同类快照默认约 60 秒最多写一次，避免前端刷新导致数据库爆量 |
| 清理 | 有旧快照清理逻辑 |
| 时间注意事项 | 快照时间依赖容器和数据库时区，已在 Compose 增加 `Asia/Shanghai` 配置 |

## 9. Pod 运维功能

Pod 模块直接面向 Kubernetes Pod 排查和操作。

| 功能 | 接口 | 状态 | 说明 |
| --- | --- | --- | --- |
| Pod 列表 | `GET /api/pods/list` | 已实现 | 支持命名空间、Deployment 等筛选 |
| Pod 详情 | `GET /api/pods/detail` | 已实现 | 查询单个 Pod 状态和详情 |
| Pod 日志 | `GET /api/pods/logs` | 已实现 | 获取 Kubernetes logs |
| 删除 Pod | `POST /api/pods/delete` | 已实现 | 删除指定 Pod |
| 重启 Pod | `POST /api/pods/restart` | 已实现 | 通常通过删除 Pod 触发控制器重建 |

注意事项：

- Kubernetes 原始时间通常是 UTC ISO 格式，例如 `2026-05-29T09:21:15Z`。
- Pod 运维依赖 Kubernetes Token 对 Pod、Events、Logs 等资源具备相应权限。

## 10. 告警中心功能

告警模块是本轮重点补齐的能力，当前包含自动扫描、数据库去重、告警处理、历史记录和恢复。

### 10.1 告警列表

| 项目 | 内容 |
| --- | --- |
| 功能 | 扫描集群告警并返回未处理告警列表 |
| 接口 | `POST /api/alerts/list` |
| 状态 | 已实现 |
| 默认行为 | 扫描 Kubernetes 后写入/更新 `alert_event`，再查询 `status = open` |
| 扫描来源 | Pods、Events、Nodes |
| 返回 | `items`、`summary`、`total`、`detected`、`written`、`scan_scope`、`scan_error` |

扫描来源说明：

| 来源 | 检测内容 |
| --- | --- |
| Pods | `Pending`、`Failed`、`Unknown`、容器 waiting/terminated reason |
| Events | `type = Warning` 的事件，例如 `BackOff`、`Unhealthy`、`FailedScheduling` |
| Nodes | `Ready != True`、`MemoryPressure`、`DiskPressure`、`PIDPressure`、`NetworkUnavailable` |

### 10.2 告警去重和入库

| 项目 | 内容 |
| --- | --- |
| 数据表 | `alert_event` |
| 去重字段 | `fingerprint` 唯一索引 |
| 新告警 | 插入为 `status = open` |
| 重复 open 告警 | 更新告警内容、证据、最近发现时间，`occurrence_count + 1` |
| 重复 resolved 告警 | 保持 `resolved`，不被扫描重新打开 |
| 重复 ignored 告警 | 保持 `ignored`，不被扫描重新打开 |
| 注意事项 | 当前没有“本轮未扫到就自动关闭旧 open 告警”的生命周期逻辑 |

### 10.3 告警历史记录

| 项目 | 内容 |
| --- | --- |
| 功能 | 查询已解决和已忽略告警，供历史记录列表展示 |
| 接口 | `POST /api/alerts/history` |
| 状态 | 已实现 |
| 默认状态 | `resolved` + `ignored` |
| 支持筛选 | `status`、`level`、`cluster_name`、`namespace`、`deployment_name`、分页 |
| 是否扫描集群 | 否，只查数据库 |
| 排序 | `handled_at`、`resolved_at`、`last_seen_at`、`created_at` 倒序 |

### 10.4 创建告警

| 项目 | 内容 |
| --- | --- |
| 功能 | 手工或后端流程创建告警 |
| 接口 | `POST /api/alerts/create` |
| 状态 | 已实现 |
| 说明 | 自动告警优先通过 `/api/alerts/list` 扫描生成 |

### 10.5 解决告警

| 项目 | 内容 |
| --- | --- |
| 功能 | 将告警标记为已解决 |
| 接口 | `POST /api/alerts/resolve` |
| 状态 | 已实现 |
| 行为 | `status = resolved`，写入 `resolver`、`resolved_at`、`handled_at` |
| 后续扫描 | 不会自动重开 |

### 10.6 忽略告警

| 项目 | 内容 |
| --- | --- |
| 功能 | 将告警标记为忽略 |
| 接口 | `POST /api/alerts/ignore` |
| 状态 | 已实现 |
| 行为 | `status = ignored`，写入 `resolver`、`handled_at`，`resolved_at` 为空 |
| 后续扫描 | 不会自动重开 |

### 10.7 恢复告警

| 项目 | 内容 |
| --- | --- |
| 功能 | 将历史记录中的已解决/已忽略告警恢复为未处理 |
| 接口 | `POST /api/alerts/reopen` |
| 状态 | 已实现 |
| 行为 | `status = open`，清空 `resolver`、`resolved_at`、`handled_at` |
| 使用场景 | 历史记录列表下点击“恢复告警” |

### 10.8 告警与 Kubernetes Events 的关系

`/api/alerts/list` 不等价于 `kubectl get events -A`。差异如下：

| 项目 | `kubectl get events -A` | `/api/alerts/list` |
| --- | --- | --- |
| 数据来源 | Kubernetes Events | Pods + Events + Nodes + 数据库 |
| 时间显示 | 默认相对时间，如 `21s`、`3m` | 数据库时间和 K8s evidence 时间 |
| 是否入库 | 否 | 是 |
| 是否去重 | Kubernetes 自身事件聚合 | `fingerprint` 去重 |
| 是否保留旧 open | 不涉及 | 数据库中仍为 open 的旧告警会继续展示 |
| 同一问题多条 | 可能较少 | 可能同时有容器状态告警和 Event 告警 |

## 11. 日志与审计功能

### 11.1 操作日志

| 项目 | 内容 |
| --- | --- |
| 功能 | 查询平台操作日志 |
| 接口 | `GET /api/logs/operations` |
| 状态 | 已实现 |
| 数据表 | `operation_log` |
| 主要来源 | 部署类接口 after_request 中间件自动写入 |

### 11.2 实例日志

| 项目 | 内容 |
| --- | --- |
| 功能 | 查询推理实例日志 |
| 接口 | `GET /api/logs/instance` |
| 状态 | 已实现 |
| 说明 | 供实例排查使用 |

### 11.3 Pod 日志

| 项目 | 内容 |
| --- | --- |
| 功能 | 查询 Pod 日志 |
| 接口 | `GET /api/logs/pod` |
| 状态 | 已实现 |
| 说明 | 与 Pod 运维模块日志能力有交叉 |

### 11.4 审计列表

| 项目 | 内容 |
| --- | --- |
| 功能 | 查询审计日志，支持筛选和分页 |
| 接口 | `POST /api/audits/list` |
| 状态 | 已实现 |
| 数据来源 | `operation_log` |

### 11.5 审计导入

| 项目 | 内容 |
| --- | --- |
| 功能 | 导入外部审计日志文件 |
| 接口 | `POST /api/audits/import` |
| 状态 | 文档中保留，当前后端路由未发现该接口 |
| 注意事项 | 如前端需要，应补齐后端路由和实现 |

### 11.6 审计导出

| 项目 | 内容 |
| --- | --- |
| 功能 | 导出审计日志 |
| 接口 | `POST /api/audits/export` |
| 状态 | 已实现 |
| 格式 | 文档支持 JSON/Excel 等导出语义，具体以后端实现为准 |

## 12. 数据库表清单

| 表名 | 用途 | 关键字段 |
| --- | --- | --- |
| `sys_user` | 用户账号 | `username`、`password`、`role`、`status` |
| `deploy_instance` | 部署实例记录 | `instance_name`、`deployment_name`、`gpu_type`、`status`、`node_ports` |
| `port_block_rule` | 封闭端口规则 | `port`、`remark` |
| `operation_log` | 操作审计日志 | `operation_type`、`operator`、`target_name`、`request_payload`、`response_payload` |
| `alert_event` | 告警事件 | `alert_type`、`alert_level`、`fingerprint`、`status`、`last_seen_at`、`handled_at` |
| `resource_snapshot` | 资源快照 | `snapshot_type`、`payload`、`created_at` |

## 13. 前端页面功能范围

当前前端演示版主要页面包括：

| 页面 | 功能范围 |
| --- | --- |
| 登录页 | 用户登录 |
| 首页 | 资源总览、趋势、告警摘要 |
| 资源中心 | 节点、GPU/NPU、配额、卡片、趋势 |
| 实例中心 | 创建、查询、停止、释放、重启、日志排查 |
| 待发布/排队相关页面 | 部分演示，资源不足排队一期暂缓 |
| 端口白名单/封闭端口 | 端口规则增删改查和避让 |
| 告警中心 | 实时告警、历史记录、处理动作 |
| 审计日志 | 操作日志查询、导出等 |

## 14. 部署与运维配置

### 14.1 Docker Compose

| 项目 | 内容 |
| --- | --- |
| 文件 | `docker-compose.yml` |
| 服务 | `jushi-frontend`、`jushi-api`、`jushi-mysql` |
| 时区修复 | 已为 API 和 MySQL 增加 `TZ=Asia/Shanghai` 和 `/etc/localtime` 挂载 |
| MySQL 时区 | 已增加 `--default-time-zone=+08:00` |
| 注意事项 | 已写入数据库的旧 UTC 时间不会自动修正 |

### 14.2 服务器代码拉取

部署服务器路径为：

```text
/home/qhadmin/jushi
```

已知问题：

| 问题 | 说明 |
| --- | --- |
| 普通用户 pull 失败 | `.git/objects` 内存在 `root:root` object |
| HTTPS 拉取不稳定 | 出现过 GitHub `GnuTLS recv error (-110)` |
| SSH 拉取未就绪 | 服务器 root/qhadmin 的 SSH key 未被 GitHub 仓库授权 |
| 工作区有本地改动 | `.env.example`、`backend/config.py`、`.env.example.bak` |

建议：

```bash
sudo chown -R qhadmin:qhadmin /home/qhadmin/jushi/.git/objects
```

如改 SSH 拉取，需要先在 GitHub 仓库添加 Deploy key，再切换 remote。

## 15. 已知风险和后续优化

| 风险 / 待优化项 | 说明 |
| --- | --- |
| 时间历史数据 | 时区配置只影响后续数据；旧数据是否迁移需单独评估 |
| 告警生命周期 | 当前没有“本轮未扫到则自动关闭 open 告警”的逻辑 |
| 告警重复展示 | 同一 Pod 可能同时产生容器状态告警和 Event 告警 |
| 审计覆盖范围 | 当前主要覆盖部署类接口，告警处理、用户管理等可继续纳入 |
| 密码存储 | `sys_user.password` 当前阶段明文，生产前应改哈希 |
| Git 部署流程 | 服务器 Git 权限和远端认证需要规范化 |
| 资源不足排队 | 一期暂缓，后续若做调度治理再补 |
| OpenAPI 更新 | 部署后需重启 API 容器，避免 Swagger 仍显示旧接口 |
