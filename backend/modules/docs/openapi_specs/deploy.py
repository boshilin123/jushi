DEPLOY_PATHS = {
    "/api/deploy/check-available": {
        "post": {
            "tags": ["Deploy"],
            "summary": "资源预检",
            "requestBody": {"$ref": "#/components/requestBodies/DeployCheckEnvelope"},
            "responses": {"200": {"description": "资源可创建"}},
        }
    },
    "/api/deploy/create-default": {
        "post": {
            "tags": ["Deploy"],
            "summary": "创建推理部署",
            "requestBody": {"$ref": "#/components/requestBodies/DeployCreateEnvelope"},
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
            "requestBody": {"$ref": "#/components/requestBodies/DeployReleaseEnvelope"},
            "responses": {"200": {"description": "释放结果"}},
        }
    },
    "/api/deploy/reset": {
        "post": {
            "tags": ["Deploy"],
            "summary": "重启部署",
            "requestBody": {"$ref": "#/components/requestBodies/DeployResetEnvelope"},
            "responses": {"200": {"description": "重启结果"}},
        }
    },
    "/api/deploy/stop": {
        "post": {
            "tags": ["Deploy"],
            "summary": "停止部署",
            "requestBody": {"$ref": "#/components/requestBodies/DeployStopEnvelope"},
            "responses": {"200": {"description": "停止结果"}},
        }
    },
    "/api/deploy/logs": {
        "post": {
            "tags": ["Deploy"],
            "summary": "部署日志",
            "requestBody": {"$ref": "#/components/requestBodies/DeployLogsEnvelope"},
            "responses": {"200": {"description": "部署日志"}},
        }
    },
    "/api/deploy/list": {
        "post": {
            "tags": ["Deploy"],
            "summary": "部署列表",
            "requestBody": {"$ref": "#/components/requestBodies/DeployListEnvelope"},
            "responses": {"200": {"description": "部署列表"}},
        }
    },
}
