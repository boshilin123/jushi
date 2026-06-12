USER_PATHS = {
    "/api/users/list": {
        "get": {
            "tags": ["Users"],
            "summary": "用户列表",
            "parameters": [
                {"$ref": "#/components/parameters/UserKeyword"},
                {"$ref": "#/components/parameters/UserRole"},
                {"$ref": "#/components/parameters/UserStatus"},
                {"$ref": "#/components/parameters/Page"},
                {"$ref": "#/components/parameters/PageSize"},
            ],
            "responses": {"200": {"description": "用户列表"}},
        }
    },
    "/api/users/create": {
        "post": {
            "tags": ["Users"],
            "summary": "创建用户",
            "requestBody": {"$ref": "#/components/requestBodies/UserCreateBody"},
            "responses": {"200": {"description": "创建结果"}},
        }
    },
    "/api/users/update": {
        "post": {
            "tags": ["Users"],
            "summary": "更新用户",
            "requestBody": {"$ref": "#/components/requestBodies/UserUpdateBody"},
            "responses": {"200": {"description": "更新结果"}},
        }
    },
    "/api/users/delete": {
        "post": {
            "tags": ["Users"],
            "summary": "删除用户",
            "requestBody": {"$ref": "#/components/requestBodies/UserIdBody"},
            "responses": {"200": {"description": "删除结果"}},
        }
    },
    "/api/users/reset-password": {
        "post": {
            "tags": ["Users"],
            "summary": "重置密码",
            "requestBody": {"$ref": "#/components/requestBodies/UserResetPasswordBody"},
            "responses": {"200": {"description": "重置结果"}},
        }
    },
}
