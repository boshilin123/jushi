SYSTEM_PATHS = {
    "/api/health": {
        "get": {
            "tags": ["System"],
            "summary": "健康检查",
            "security": [],
            "responses": {"200": {"description": "服务正常"}},
        }
    },
}
