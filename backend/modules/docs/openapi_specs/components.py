COMPONENTS = {
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
        },
        "UserKeyword": {
            "name": "keyword",
            "in": "query",
            "required": False,
            "schema": {"type": "string"},
            "description": "按用户名或真实姓名模糊搜索",
        },
        "UserRole": {
            "name": "role",
            "in": "query",
            "required": False,
            "schema": {"type": "string", "enum": ["admin", "operator", "user"]},
            "description": "用户角色筛选",
        },
        "UserStatus": {
            "name": "status",
            "in": "query",
            "required": False,
            "schema": {"type": "string", "enum": ["active", "disabled"]},
            "description": "用户状态筛选；不传时返回全部状态",
        },
        "Page": {
            "name": "page",
            "in": "query",
            "required": False,
            "schema": {"type": "integer", "default": 1, "minimum": 1},
            "description": "页码",
        },
        "PageSize": {
            "name": "page_size",
            "in": "query",
            "required": False,
            "schema": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
            "description": "每页数量，最大 100",
        },
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
        "ClusterEnvelope": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ClusterEnvelope"}
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
        "UserCreateBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/UserCreateRequest"}
                }
            },
        },
        "UserUpdateBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/UserUpdateRequest"}
                }
            },
        },
        "UserIdBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/UserIdRequest"}
                }
            },
        },
        "UserResetPasswordBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/UserResetPasswordRequest"}
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
                "context": {"type": "string", "example": "create inference instance"},
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
                        "name": {"type": "string", "example": "nvidia-cuda-xxxxxx"}
                    },
                    "required": ["name"],
                },
            },
            "required": ["msg_id", "serial", "context", "content"],
        },
        "ClusterEnvelope": {
            "type": "object",
            "properties": {
                "msg_id": {"type": "string", "example": "cluster-001"},
                "serial": {"type": "string", "example": "serial-001"},
                "context": {"type": "string", "example": "query cluster"},
                "content": {"type": "object", "example": {}},
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
        "UserCreateRequest": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "example": "alice"},
                "password": {"type": "string", "example": "Init@123"},
                "real_name": {"type": "string", "example": "Alice"},
                "role": {
                    "type": "string",
                    "enum": ["admin", "operator", "user"],
                    "example": "operator",
                },
                "status": {
                    "type": "string",
                    "enum": ["active", "disabled"],
                    "example": "active",
                },
            },
            "required": ["username", "password"],
        },
        "UserUpdateRequest": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "example": 2},
                "real_name": {"type": "string", "example": "Alice Zhang"},
                "role": {
                    "type": "string",
                    "enum": ["admin", "operator", "user"],
                    "example": "operator",
                },
                "status": {
                    "type": "string",
                    "enum": ["active", "disabled"],
                    "example": "active",
                },
            },
            "required": ["id"],
        },
        "UserIdRequest": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "example": 2},
            },
            "required": ["id"],
        },
        "UserResetPasswordRequest": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "example": 2},
                "password": {"type": "string", "example": "New@123"},
            },
            "required": ["id", "password"],
        },
    },
}
