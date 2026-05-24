RESOURCE_PATHS = {
    "/api/resources/summary": {
        "get": {
            "tags": ["Resources"],
            "summary": "资源概览",
            "responses": {"200": {"description": "资源概览"}},
        }
    },
    "/api/resources/nodes": {
        "get": {
            "tags": ["Resources"],
            "summary": "节点列表",
            "responses": {"200": {"description": "节点列表"}},
        }
    },
    "/api/resources/gpus": {
        "get": {
            "tags": ["Resources"],
            "summary": "GPU 统计",
            "responses": {"200": {"description": "GPU 统计"}},
        }
    },
    "/api/resources/quotas": {
        "get": {
            "tags": ["Resources"],
            "summary": "配额列表",
            "responses": {"200": {"description": "配额列表"}},
        }
    },
}
