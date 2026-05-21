def list_pods(query: dict) -> dict:
    # 查询 Pod 列表。
    return {"items": [], "query": query}


def pod_detail(query: dict) -> dict:
    # 查询 Pod 详情。
    return {"query": query}


def pod_logs(query: dict) -> dict:
    # 查询 Pod 日志。
    return {"lines": [], "query": query}


def delete_pod(action: dict) -> dict:
    # 删除 Pod。
    return {"is_success": True, **action}


def restart_pod(action: dict) -> dict:
    # 重启 Pod。
    return {"is_success": True, **action}
