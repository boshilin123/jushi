POD_PATHS = {
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
}
