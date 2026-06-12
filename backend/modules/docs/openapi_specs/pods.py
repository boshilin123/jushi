POD_PATHS = {
    "/api/pods/list": {
        "get": {
            "tags": ["Pods"],
            "summary": "Pod 列表",
            "parameters": [
                {"$ref": "#/components/parameters/Namespace"},
                {"$ref": "#/components/parameters/DeploymentName"},
                {"$ref": "#/components/parameters/PodPhase"},
                {"$ref": "#/components/parameters/NodeName"},
            ],
            "responses": {"200": {"description": "Pod 列表"}},
        }
    },
    "/api/pods/detail": {
        "get": {
            "tags": ["Pods"],
            "summary": "Pod 详情",
            "parameters": [
                {"$ref": "#/components/parameters/Namespace"},
                {"$ref": "#/components/parameters/PodName"},
            ],
            "responses": {"200": {"description": "Pod 详情"}},
        }
    },
    "/api/pods/logs": {
        "get": {
            "tags": ["Pods"],
            "summary": "Pod 日志",
            "parameters": [
                {"$ref": "#/components/parameters/Namespace"},
                {"$ref": "#/components/parameters/PodName"},
                {"$ref": "#/components/parameters/TailLines"},
            ],
            "responses": {"200": {"description": "Pod 日志"}},
        }
    },
    "/api/pods/delete": {
        "post": {
            "tags": ["Pods"],
            "summary": "删除 Pod",
            "requestBody": {"$ref": "#/components/requestBodies/PodActionBody"},
            "responses": {"200": {"description": "删除结果"}},
        }
    },
    "/api/pods/restart": {
        "post": {
            "tags": ["Pods"],
            "summary": "重启 Pod",
            "requestBody": {"$ref": "#/components/requestBodies/PodActionBody"},
            "responses": {"200": {"description": "重启结果"}},
        }
    },
}
