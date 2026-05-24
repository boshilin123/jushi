from flask import Blueprint, Response, jsonify


docs_bp = Blueprint("docs", __name__)


# Swagger 页面展示的中文标题、模块名称和接口说明都来自这个 OpenAPI 配置。
OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "聚时 AI 推理资源管理平台 API",
        "version": "0.1.0",
        "description": "一期开发接口调试文档，覆盖用户、部署、端口、资源、Pod、告警和日志接口。",
    },
    "servers": [
        {"url": "/", "description": "Current host"},
    ],
    "tags": [
        {"name": "System", "description": "系统健康检查"},
        {"name": "Auth", "description": "登录与当前用户"},
        {"name": "Users", "description": "用户管理"},
        {"name": "Deploy", "description": "推理部署生命周期"},
        {"name": "Ports", "description": "封闭端口 / 端口避让"},
        {"name": "Resources", "description": "集群资源"},
        {"name": "Pods", "description": "Pod 查询与操作"},
        {"name": "Alerts", "description": "告警"},
        {"name": "Logs", "description": "日志"},
    ],
    "security": [{"BearerAuth": []}],
    "paths": {
        "/api/health": {
            "get": {
                "tags": ["System"],
                "summary": "健康检查",
                "security": [],
                "responses": {"200": {"description": "服务正常"}},
            }
        },
        "/api/auth/login": {
            "post": {
                "tags": ["Auth"],
                "summary": "用户登录",
                "security": [],
                "requestBody": {"$ref": "#/components/requestBodies/LoginBody"},
                "responses": {"200": {"description": "登录成功"}},
            }
        },
        "/api/auth/logout": {
            "post": {
                "tags": ["Auth"],
                "summary": "用户登出",
                "responses": {"200": {"description": "登出成功"}},
            }
        },
        "/api/auth/me": {
            "get": {
                "tags": ["Auth"],
                "summary": "当前用户",
                "responses": {"200": {"description": "当前用户信息"}},
            }
        },
        "/api/users/list": {
            "get": {
                "tags": ["Users"],
                "summary": "用户列表",
                "responses": {"200": {"description": "用户列表"}},
            }
        },
        "/api/deploy/check-available": {
            "post": {
                "tags": ["Deploy"],
                "summary": "资源预检",
                "requestBody": {"$ref": "#/components/requestBodies/DeployEnvelope"},
                "responses": {"200": {"description": "资源可创建"}},
            }
        },
        "/api/deploy/create-default": {
            "post": {
                "tags": ["Deploy"],
                "summary": "创建推理部署",
                "requestBody": {"$ref": "#/components/requestBodies/DeployEnvelope"},
                "responses": {"200": {"description": "创建成功"}},
            }
        },
        "/api/deploy/retrieve": {
            "post": {
                "tags": ["Deploy"],
                "summary": "查询单个部署",
                "requestBody": {"$ref": "#/components/requestBodies/NameEnvelope"},
                "responses": {"200": {"description": "部署详情"}},
            }
        },
        "/api/deploy/release": {
            "post": {
                "tags": ["Deploy"],
                "summary": "释放部署",
                "requestBody": {"$ref": "#/components/requestBodies/NameEnvelope"},
                "responses": {"200": {"description": "释放结果"}},
            }
        },
        "/api/deploy/reset": {
            "post": {
                "tags": ["Deploy"],
                "summary": "重启部署",
                "requestBody": {"$ref": "#/components/requestBodies/NameEnvelope"},
                "responses": {"200": {"description": "重启结果"}},
            }
        },
        "/api/deploy/list": {
            "post": {
                "tags": ["Deploy"],
                "summary": "部署列表",
                "responses": {"200": {"description": "部署列表"}},
            }
        },
        "/api/port-list/list": {
            "get": {
                "tags": ["Ports"],
                "summary": "封闭端口列表",
                "responses": {"200": {"description": "封闭端口列表"}},
            }
        },
        "/api/port-list/add": {
            "post": {
                "tags": ["Ports"],
                "summary": "新增封闭端口",
                "requestBody": {"$ref": "#/components/requestBodies/PortBody"},
                "responses": {"200": {"description": "新增结果"}},
            }
        },
        "/api/port-list/update/{item_id}": {
            "put": {
                "tags": ["Ports"],
                "summary": "更新封闭端口",
                "parameters": [{"$ref": "#/components/parameters/ItemId"}],
                "requestBody": {"$ref": "#/components/requestBodies/PortBody"},
                "responses": {"200": {"description": "更新结果"}},
            }
        },
        "/api/port-list/delete/{item_id}": {
            "delete": {
                "tags": ["Ports"],
                "summary": "删除封闭端口",
                "parameters": [{"$ref": "#/components/parameters/ItemId"}],
                "responses": {"200": {"description": "删除结果"}},
            }
        },
        "/api/port-list/resolve": {
            "get": {
                "tags": ["Ports"],
                "summary": "解析端口避让快照",
                "responses": {"200": {"description": "端口避让快照"}},
            }
        },
        "/api/resources/summary": {
            "get": {
                "tags": ["Resources"],
                "summary": "资源概览",
                "responses": {"200": {"description": "资源概览"}},
            }
        },
        "/api/resources/nodes": {
            "get": {
                "tags": ["Resources"],
                "summary": "节点列表",
                "responses": {"200": {"description": "节点列表"}},
            }
        },
        "/api/resources/gpus": {
            "get": {
                "tags": ["Resources"],
                "summary": "GPU 统计",
                "responses": {"200": {"description": "GPU 统计"}},
            }
        },
        "/api/resources/quotas": {
            "get": {
                "tags": ["Resources"],
                "summary": "配额列表",
                "responses": {"200": {"description": "配额列表"}},
            }
        },
        "/api/pods/list": {
            "get": {
                "tags": ["Pods"],
                "summary": "Pod 列表",
                "responses": {"200": {"description": "Pod 列表"}},
            }
        },
        "/api/pods/detail": {
            "get": {
                "tags": ["Pods"],
                "summary": "Pod 详情",
                "responses": {"200": {"description": "Pod 详情"}},
            }
        },
        "/api/pods/logs": {
            "get": {
                "tags": ["Pods"],
                "summary": "Pod 日志",
                "responses": {"200": {"description": "Pod 日志"}},
            }
        },
        "/api/pods/delete": {
            "post": {
                "tags": ["Pods"],
                "summary": "删除 Pod",
                "responses": {"200": {"description": "删除结果"}},
            }
        },
        "/api/pods/restart": {
            "post": {
                "tags": ["Pods"],
                "summary": "重启 Pod",
                "responses": {"200": {"description": "重启结果"}},
            }
        },
        "/api/alerts/list": {
            "post": {
                "tags": ["Alerts"],
                "summary": "告警列表",
                "responses": {"200": {"description": "告警列表"}},
            }
        },
        "/api/alerts/create": {
            "post": {
                "tags": ["Alerts"],
                "summary": "创建告警",
                "responses": {"200": {"description": "创建结果"}},
            }
        },
        "/api/alerts/resolve": {
            "post": {
                "tags": ["Alerts"],
                "summary": "解决告警",
                "responses": {"200": {"description": "解决结果"}},
            }
        },
        "/api/alerts/ignore": {
            "post": {
                "tags": ["Alerts"],
                "summary": "忽略告警",
                "responses": {"200": {"description": "忽略结果"}},
            }
        },
        "/api/logs/operations": {
            "get": {
                "tags": ["Logs"],
                "summary": "操作日志",
                "responses": {"200": {"description": "操作日志"}},
            }
        },
        "/api/logs/instance": {
            "get": {
                "tags": ["Logs"],
                "summary": "实例日志",
                "responses": {"200": {"description": "实例日志"}},
            }
        },
        "/api/logs/pod": {
            "get": {
                "tags": ["Logs"],
                "summary": "Pod 日志",
                "responses": {"200": {"description": "Pod 日志"}},
            }
        },
    },
    "components": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "Token",
                "description": "登录成功后复制 token 到 Authorize，不需要手动添加 Bearer 前缀",
            }
        },
        "parameters": {
            "ItemId": {
                "name": "item_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            }
        },
        "requestBodies": {
            "LoginBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/LoginRequest"}
                    }
                },
            },
            "DeployEnvelope": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/DeployEnvelope"}
                    }
                },
            },
            "NameEnvelope": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/NameEnvelope"}
                    }
                },
            },
            "PortBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/PortRule"}
                    }
                },
            },
        },
        "schemas": {
            "LoginRequest": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "example": "admin"},
                    "password": {"type": "string", "example": "bluedot@123"},
                },
                "required": ["username", "password"],
            },
            "DeployEnvelope": {
                "type": "object",
                "properties": {
                    "msg_id": {"type": "string", "example": "create-001"},
                    "serial": {"type": "string", "example": "serial-001"},
                    "context": {
                        "type": "string",
                        "example": "create inference instance",
                    },
                    "gpu_resource_name": {
                        "type": "string",
                        "example": "huawei.com/Ascend310P",
                    },
                    "content": {"$ref": "#/components/schemas/DeployContent"},
                },
                "required": ["msg_id", "serial", "context", "content"],
            },
            "DeployContent": {
                "type": "object",
                "properties": {
                    "devices": {
                        "type": "object",
                        "additionalProperties": {"type": "integer"},
                        "example": {"NVIDIA/GPU": 1},
                    },
                    "deployType": {
                        "type": "string",
                        "enum": ["NvidiaInfer", "HuaweiInfer"],
                        "example": "NvidiaInfer",
                    },
                    "creator": {"type": "string", "example": "alice"},
                },
                "required": ["devices", "deployType", "creator"],
            },
            "NameEnvelope": {
                "type": "object",
                "properties": {
                    "msg_id": {"type": "string", "example": "retrieve-001"},
                    "serial": {"type": "string", "example": "serial-001"},
                    "context": {"type": "string", "example": "retrieve deploy"},
                    "content": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "example": "nvidia-cuda-xxxxxx",
                            }
                        },
                        "required": ["name"],
                    },
                },
                "required": ["msg_id", "serial", "context", "content"],
            },
            "PortRule": {
                "type": "object",
                "properties": {
                    "port": {"type": "integer", "example": 50055},
                    "remark": {"type": "string", "example": "reserved port"},
                },
                "required": ["port"],
            },
        },
    },
}


@docs_bp.get("/openapi.json")
def openapi_json():
    # 返回 Swagger UI 读取的 OpenAPI JSON。
    return jsonify(OPENAPI_SPEC)


@docs_bp.get("")
@docs_bp.get("/")
def swagger_ui():
    # 渲染 Swagger UI 页面，方便开发和联调阶段直接调试接口。
    html = """
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <title>聚时 API Docs</title>
        <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
        <style>body { margin: 0; }</style>
      </head>
      <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
          window.ui = SwaggerUIBundle({
            url: "/api/docs/openapi.json",
            dom_id: "#swagger-ui",
            deepLinking: true,
            presets: [SwaggerUIBundle.presets.apis],
          });
        </script>
      </body>
    </html>
    """
    return Response(html, mimetype="text/html")
