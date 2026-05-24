LOG_PATHS = {
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
}
