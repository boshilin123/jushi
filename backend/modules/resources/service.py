def summary(query: dict) -> dict:
    # 查询资源总览，后续复用 PaaS API 的集群资源统计。
    return {}


def nodes(query: dict) -> dict:
    # 查询节点资源列表。
    return {"items": []}


def gpus(query: dict) -> dict:
    # 查询 GPU 类型统计。
    return {"items": []}


def quotas(query: dict) -> dict:
    # 查询资源配额。
    return {"items": []}
