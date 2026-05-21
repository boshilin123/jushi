from . import repository


def operation_logs(query: dict) -> dict:
    # 查询操作日志。
    return {"items": repository.list_operation_logs(query)}


def instance_logs(query: dict) -> dict:
    # 查询实例日志，后续读取 /workspace/Alg/log/<deployment_name>。
    return {"lines": [], "query": query}


def pod_logs(query: dict) -> dict:
    # 查询 Pod 日志，后续对接 Kubernetes logs。
    return {"lines": [], "query": query}
