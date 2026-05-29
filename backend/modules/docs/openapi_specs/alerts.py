ALERT_PATHS = {
    "/api/alerts/list": {
        "post": {
            "tags": ["Alerts"],
            "summary": "告警列表",
            "requestBody": {"$ref": "#/components/requestBodies/AlertListBody"},
            "responses": {"200": {"description": "告警列表"}},
        }
    },
    "/api/alerts/history": {
        "post": {
            "tags": ["Alerts"],
            "summary": "告警历史记录",
            "requestBody": {"$ref": "#/components/requestBodies/AlertHistoryBody"},
            "responses": {"200": {"description": "告警历史记录"}},
        }
    },
    "/api/alerts/create": {
        "post": {
            "tags": ["Alerts"],
            "summary": "创建告警",
            "requestBody": {"$ref": "#/components/requestBodies/AlertCreateBody"},
            "responses": {"200": {"description": "创建结果"}},
        }
    },
    "/api/alerts/resolve": {
        "post": {
            "tags": ["Alerts"],
            "summary": "解决告警",
            "requestBody": {"$ref": "#/components/requestBodies/AlertActionBody"},
            "responses": {"200": {"description": "解决结果"}},
        }
    },
    "/api/alerts/ignore": {
        "post": {
            "tags": ["Alerts"],
            "summary": "忽略告警",
            "requestBody": {"$ref": "#/components/requestBodies/AlertActionBody"},
            "responses": {"200": {"description": "忽略结果"}},
        }
    },
    "/api/alerts/reopen": {
        "post": {
            "tags": ["Alerts"],
            "summary": "重新打开告警",
            "requestBody": {"$ref": "#/components/requestBodies/AlertActionBody"},
            "responses": {"200": {"description": "重新打开结果"}},
        }
    },
}
