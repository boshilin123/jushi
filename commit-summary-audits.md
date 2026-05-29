# 操作日志 & 审计接口 — 提交总结

**分支**: `feature/pod-alert-api`
**日期**: 2026-05-29

---

## 一、针对什么问题

上一期已完成 Pod 运维和告警接口（接口文档第 8、9 节）。本期补齐第 10 节剩余内容：**操作日志查询** 和 **审计功能**。

现状：
- `GET /api/logs/operations` 路由已存在，但返回 `{"items": []}` 空数据
- `POST /api/audits/list` 和 `POST /api/audits/export` 整个 audits 模块缺失
- `operation_log` 表已在 `init.sql` 中定义，但无任何代码写入或读取

---

## 二、干了什么

### 2.1 接口实现（3 个）

| 接口 | 原来 | 现在 |
|------|------|------|
| `GET /api/logs/operations` | 返回 `{"items": []}` | MySQL 分页查询，支持按操作人/类型/关键词筛选 |
| `POST /api/audits/list` | 不存在 | envelope 格式响应，含分页 + 筛选 |
| `POST /api/audits/export` | 不存在 | JSON 文件下载，支持筛选 |

### 2.2 部署接口自动记录中间件

在 `app.py` 中新增 `@app.after_request` 钩子，拦截 6 个 `/api/deploy/*` 接口，自动写入 `operation_log`：

| 接口路径 | operation_type |
|----------|---------------|
| `POST /api/deploy/check-available` | `check_available` |
| `POST /api/deploy/create-default` | `create` |
| `POST /api/deploy/retrieve` | `retrieve` |
| `POST /api/deploy/release` | `release` |
| `POST /api/deploy/reset` | `reset` |
| `POST /api/deploy/list` | `list` |

每条记录包含：`operation_type`、`operator`（来自登录用户）、`operator_ip`、`target_type`、`target_name`、`request_payload`、`response_payload`、`http_status_code`、`is_success`、`error_message`。

### 2.3 改动文件（12 个）

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `backend/app.py` | 新增中间件函数 + audits 蓝图注册 |
| 修改 | `backend/modules/logs/schema.py` | 新增 5 个查询参数 |
| 修改 | `backend/modules/logs/repository.py` | `save_operation_log` / `list_operation_logs`(含分页) / `export_operation_logs` / `list_audit_envelope`，MySQL + 文件/内存回退 |
| 修改 | `backend/modules/logs/service.py` | `operation_logs` 返回 total |
| 新建 | `backend/modules/audits/__init__.py` | 导出 `audits_bp` |
| 新建 | `backend/modules/audits/schema.py` | `normalize_audit_list` / `normalize_audit_export` |
| 新建 | `backend/modules/audits/service.py` | 委托到 logs.repository |
| 新建 | `backend/modules/audits/routes.py` | `POST /list`(envelope) + `POST /export`(JSON 下载) |
| 新建 | `backend/modules/docs/openapi_specs/audits.py` | Swagger 两个路径 |
| 修改 | `backend/modules/docs/openapi_specs/__init__.py` | 导入 + Audits tag + 合并路径 |
| 修改 | `backend/modules/docs/openapi_specs/components.py` | AuditListBody / AuditExportBody 等 4 个 schema |

---

## 三、验证结果

### 3.1 接口验证

```
查询: GET /api/logs/operations?page=1&page_size=3
    → 共 15 条, 当前页 3 条

筛选: GET /api/logs/operations?keyword=不足
    → 命中 2 条 "GPU卡数量不足" "GPU数量不足"

筛选: GET /api/logs/operations?operator=zhangsan
    → 命中 7 条 zhangsan 的操作

审计: POST /api/audits/list {"content":{"operation_type":"create"}}
    → 返回 3 条创建记录, msg_id/serial/context 回传

导出: POST /api/audits/export {"content":{"operator":"zhangsan"}}
    → 下载 7 条记录的 JSON 文件
```

### 3.2 Swagger

3 个接口均在 Swagger UI 可见可测：
- `GET /api/logs/operations` — Logs 分组
- `POST /api/audits/list` — Audits 分组
- `POST /api/audits/export` — Audits 分组

### 3.3 测试数据设计

为 Swagger 测试准备了 15 条假数据，每条记录包含 `operation_log` 表完整的 11 个字段。数据从三个维度覆盖，且每个取值均有项目文件作为依据。

#### 字段覆盖 — 11 个字段来自 `init.sql` 表定义

`operation_log` 表结构定义在 `backend/db/init.sql` 第 54-66 行，每条记录包含：

| 字段 | 类型 | 覆盖情况 |
|------|------|----------|
| `id` | BIGINT | 自增 23-37 |
| `operation_type` | VARCHAR(64) | 6 种全部覆盖 |
| `operator` | VARCHAR(64) | admin / zhangsan / lisi |
| `operator_ip` | VARCHAR(64) | 10.0.1.100 / 10.0.2.50 / 10.0.3.88 |
| `target_type` | VARCHAR(64) | deploy |
| `target_name` | VARCHAR(128) | NVIDIA/GPU、Huawei/Ascend310P、4 个 deployment 名、all |
| `request_payload` | JSON | 每条不同，对应用档第 5 节 envelope 格式 |
| `response_payload` | JSON | 每条不同，成功含 deployment_name/node_ports，失败含 msg/error |
| `http_status_code` | INT | 200 / 400 / 404 / 502 / 504 |
| `is_success` | TINYINT | 成功 10 条 + 失败 5 条 |
| `error_message` | TEXT | 5 条不同中文说明 |
| `created_at` | DATETIME | 15 天时间跨度 |

#### 场景覆盖 — 每种操作类型对应真实可能发生的成功和失败情形

每种操作类型的取值来自 `app.py` 中间件 `DEPLOY_PATHS` 路由映射（第 43-51 行），共 6 种。每种操作类型的 `target_name` 提取规则来自中间件的 if/elif 分支（第 67-83 行）——`check_available` 从 `request.devices` 取 GPU 类型、`create` 从 `response.deployment_name` 取生成名、`retrieve/release/reset` 从 `request.name` 取实例名、`list` 固定为 "all"。

| 操作类型 | 覆盖场景 | 条数 | 涉及用户 | 状态码 | 对应中间件规则 |
|----------|----------|------|----------|--------|---------------|
| `check_available` | NVIDIA 资源充足 / GPU 不足 / Ascend 不可用 | 3 | admin, zhangsan | 200, 400 | target_name = devices 第一个 key |
| `create` | 创建成功 / PaaS 502 失败 | 3 | admin, zhangsan, lisi | 200, 502 | target_name = response.deployment_name |
| `retrieve` | 查到 Pod / 查不到 Pod | 2 | admin, lisi | 200 | target_name = request.name |
| `reset` | 重启成功 / Deployment 不存在 404 | 2 | admin, zhangsan | 200, 404 | target_name = request.name |
| `release` | 释放成功 / 释放超时 504 | 2 | admin, zhangsan | 200, 504 | target_name = request.name |
| `list` | 有实例 / 无实例 | 2 | lisi, zhangsan | 200 | target_name = "all" |

每条记录的 `request_payload` 和 `response_payload` 结构遵循 `docs/api-interface.md` 第 2.3 节 envelope 格式和第 5.1-5.7 节各接口响应示例。`error_message` 的文案参考了 API 文档中的错误消息——如第 5.2 节 "GPU卡数量不足"、第 5.3 节 "创建部署失败"——再结合部署领域推断出 "PaaS API 返回 502"、"释放超时请重试"、"Ascend 设备不可用" 等贴近真实场景的表述。

#### 数据来源对照 — 每个字段取值在项目中都有迹可循

| 字段 | 取值依据 | 关键文件 |
|------|----------|----------|
| 表结构和字段名 | `operation_log` 建表 DDL | `backend/db/init.sql:54-66` |
| `operation_type` 的 6 种取值 | 中间件路由路径到操作类型映射 | `backend/app.py:43-51` |
| `target_name` 的 5 种规则 | 中间件按路径分支提取逻辑 | `backend/app.py:67-83` |
| `request_payload` 请求体 | 部署 envelope 协议（msg_id/serial/context/content） | `docs/api-interface.md:2.3` |
| `response_payload` 响应体 | 各部署接口成功/失败示例 | `docs/api-interface.md:5.1-5.7` |
| `error_message` 错误文案 | API 文档错误响应 + 部署领域推断 | `docs/api-interface.md:5.2-5.3` |
| `operator` 用户身份 | sys_user 表初始数据 + 角色定义 | `backend/db/init.sql:77` |
| `http_status_code` 状态码 | HTTP 标准 + API 文档 2.4 节 | `docs/api-interface.md:2.4` |
| `operator_ip` IP 地址 | 中间件从 X-Forwarded-For / X-Real-IP 提取 | `backend/app.py:85-88` |
