AUTH_PATHS = {
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
}
