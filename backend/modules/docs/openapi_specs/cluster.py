CLUSTER_PATHS = {
    "/api/cluster": {
        "post": {
            "tags": ["Cluster"],
            "summary": "集群查询",
            "requestBody": {"$ref": "#/components/requestBodies/ClusterEnvelope"},
            "responses": {"200": {"description": "集群列表"}},
        }
    },
}
