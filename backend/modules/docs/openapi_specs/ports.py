PORT_PATHS = {
    "/api/port-list/list": {
        "get": {
            "tags": ["Ports"],
            "summary": "封闭端口列表",
            "responses": {"200": {"description": "封闭端口列表"}},
        }
    },
    "/api/port-list/add": {
        "post": {
            "tags": ["Ports"],
            "summary": "新增封闭端口",
            "requestBody": {"$ref": "#/components/requestBodies/PortBody"},
            "responses": {"200": {"description": "新增结果"}},
        }
    },
    "/api/port-list/update/{item_id}": {
        "put": {
            "tags": ["Ports"],
            "summary": "更新封闭端口",
            "parameters": [{"$ref": "#/components/parameters/ItemId"}],
            "requestBody": {"$ref": "#/components/requestBodies/PortBody"},
            "responses": {"200": {"description": "更新结果"}},
        }
    },
    "/api/port-list/delete/{item_id}": {
        "delete": {
            "tags": ["Ports"],
            "summary": "删除封闭端口",
            "parameters": [{"$ref": "#/components/parameters/ItemId"}],
            "responses": {"200": {"description": "删除结果"}},
        }
    },
    "/api/port-list/resolve": {
        "get": {
            "tags": ["Ports"],
            "summary": "解析端口避让快照",
            "responses": {"200": {"description": "端口避让快照"}},
        }
    },
}
