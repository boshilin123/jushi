SYSTEM_PATHS = {
    "/api/system/health": {
        "get": {
            "tags": ["System"],
            "summary": "健康检查",
            "security": [],
            "responses": {"200": {"description": "服务正常"}},
        }
    },
    "/api/system/logo": {
        "get": {
            "tags": ["System"],
            "summary": "获取系统 Logo 状态",
            "description": "返回当前 Logo 的 URL 和启用状态。免登录。",
            "security": [],
            "responses": {
                "200": {
                    "description": "Logo 状态",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/LogoStatus"},
                            "example": {"logo_url": "/api/system/logo/file", "logo_enabled": True},
                        }
                    },
                }
            },
        },
        "post": {
            "tags": ["System"],
            "summary": "上传/更换系统 Logo",
            "description": "上传新 Logo 图片并自动启用。需要管理员权限。支持 PNG/JPG/SVG/GIF，最大 2MB。",
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "logo": {
                                    "type": "string",
                                    "format": "binary",
                                    "description": "Logo 图片文件",
                                }
                            },
                            "required": ["logo"],
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "上传成功",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/LogoUploadResult"},
                        }
                    },
                },
                "400": {"description": "文件校验失败"},
                "401": {"description": "未登录"},
                "403": {"description": "非管理员"},
            },
        },
    },
    "/api/system/logo/file": {
        "get": {
            "tags": ["System"],
            "summary": "获取 Logo 图片文件",
            "description": "返回当前启用 Logo 的图片字节流。Logo 未启用时返回 404。免登录，可直接作为 img src。",
            "security": [],
            "responses": {
                "200": {"description": "Logo 图片（image/png 或 image/jpeg 等）"},
                "404": {"description": "Logo 未启用或文件不存在"},
            },
        }
    },
    "/api/system/logo/enable": {
        "put": {
            "tags": ["System"],
            "summary": "启用自定义 Logo",
            "description": "切换回之前上传的自定义 Logo（不删除文件，仅切换显示开关）。需要管理员权限。",
            "responses": {
                "200": {
                    "description": "已启用",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/LogoStatus"},
                        }
                    },
                },
                "401": {"description": "未登录"},
                "403": {"description": "非管理员"},
            },
        }
    },
    "/api/system/logo/disable": {
        "put": {
            "tags": ["System"],
            "summary": "恢复默认 Logo",
            "description": "关闭自定义 Logo 显示开关（文件全部保留不删除）。需要管理员权限。",
            "responses": {
                "200": {
                    "description": "已恢复默认",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/LogoStatus"},
                        }
                    },
                },
                "401": {"description": "未登录"},
                "403": {"description": "非管理员"},
            },
        }
    },
}
