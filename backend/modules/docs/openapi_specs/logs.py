LOG_PATHS = {
    "/api/logs/operations": {
        "get": {
            "tags": ["Logs"],
            "summary": "操作日志",
            "parameters": [
                {"$ref": "#/components/parameters/UserKeyword"},
                {"$ref": "#/components/parameters/Page"},
                {"$ref": "#/components/parameters/PageSize"},
            ],
            "responses": {"200": {"description": "操作日志"}},
        }
    },
    "/api/logs/instance": {
        "get": {
            "tags": ["Logs"],
            "summary": "实例日志",
            "parameters": [
                {"$ref": "#/components/parameters/DeploymentName"},
                {"$ref": "#/components/parameters/TailLines"},
            ],
            "responses": {"200": {"description": "实例日志"}},
        }
    },
    "/api/logs/pod": {
        "get": {
            "tags": ["Logs"],
            "summary": "Pod 日志",
            "parameters": [
                {"$ref": "#/components/parameters/Namespace"},
                {"$ref": "#/components/parameters/PodName"},
                {"$ref": "#/components/parameters/TailLines"},
            ],
            "responses": {"200": {"description": "Pod 日志"}},
        }
    },
}
