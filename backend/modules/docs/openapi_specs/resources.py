RESOURCE_PATHS = {
    "/api/resources/summary": {
        "get": {
            "tags": ["Resources"],
            "summary": "资源概览",
            "description": "查询集群资源总览，用于首页和资源中心顶部统计卡片。",
            "responses": {"200": {"description": "资源概览"}},
        }
    },
    "/api/resources/nodes": {
        "get": {
            "tags": ["Resources"],
            "summary": "节点资源列表",
            "description": "查询节点维度的 GPU / vGPU / 显存 / 算力 / CPU / 内存资源状态。",
            "responses": {"200": {"description": "节点列表"}},
        }
    },
    "/api/resources/gpus": {
        "get": {
            "tags": ["Resources"],
            "summary": "GPU / vGPU 资源统计",
            "description": "按资源类型和显卡型号统计资源总量、已用量和可用量。",
            "responses": {"200": {"description": "GPU 统计"}},
        }
    },
    "/api/resources/quotas": {
        "get": {
            "tags": ["Resources"],
            "summary": "配额列表",
            "description": "查询命名空间 ResourceQuota 信息；无权限时降级为空列表，不阻塞页面。",
            "responses": {"200": {"description": "配额列表"}},
        }
    },
    "/api/resources/cards": {
        "get": {
            "tags": ["Resources"],
            "summary": "资源卡片列表",
            "description": "查询显卡 / vGPU 卡片列表，用于资源中心卡片表格。",
            "responses": {"200": {"description": "资源卡片列表"}},
        }
    },
    "/api/resources/trend": {
        "get": {
            "tags": ["Resources"],
            "summary": "资源趋势",
            "description": "查询资源使用趋势。当前基于实时快照，后续可接 Prometheus 或采集表。",
            "responses": {"200": {"description": "资源趋势"}},
        }
    },
    "/api/resources/recommendation": {
        "get": {
            "tags": ["Resources"],
            "summary": "资源推荐策略",
            "description": "根据当前 GPU / vGPU / 显存 / 算力资源余量返回推荐策略。",
            "responses": {"200": {"description": "资源推荐策略"}},
        }
    },
}
