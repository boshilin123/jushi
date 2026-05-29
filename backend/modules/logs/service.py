from . import repository


def operation_logs(query: dict) -> dict:
    result = repository.list_operation_logs(query)
    return {"items": result["items"], "total": result["total"]}


def instance_logs(query: dict) -> dict:
    deployment_name = query.get("deployment_name", "")
    if not deployment_name:
        return {"lines": []}
    namespace = query.get("namespace", "algorithm")
    tail_lines = int(query.get("tail_lines", 200))
    try:
        try:
            from backend.services.k8s_client import K8sClient
        except ModuleNotFoundError:
            from services.k8s_client import K8sClient

        k8s = K8sClient()
        pods = k8s.list_pods(namespace)
        target_pods = [p for p in pods if p["pod_name"].startswith(deployment_name)]
        if target_pods:
            lines = k8s.pod_logs(namespace, target_pods[0]["pod_name"], tail_lines=tail_lines)
            return {"lines": lines}
    except Exception:
        pass
    return {"lines": []}


def pod_logs(query: dict) -> dict:
    try:
        from backend.modules.pods.service import pod_logs as _pods_pod_logs
    except ModuleNotFoundError:
        from modules.pods.service import pod_logs as _pods_pod_logs
    return _pods_pod_logs(query)
