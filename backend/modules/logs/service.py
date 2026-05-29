from . import repository

try:
    from backend.config import Config
    from backend.services.k8s_client import K8sClient
except ModuleNotFoundError:
    from config import Config
    from services.k8s_client import K8sClient


def operation_logs(query: dict) -> dict:
    result = repository.list_operation_logs(query)
    return {"items": result["items"], "total": result["total"]}


def instance_logs(query: dict) -> dict:
    deployment_name = query.get("deployment_name", "")
    if not deployment_name:
        return {"is_success": False, "msg": "deployment_name 不能为空", "lines": []}

    namespace = query.get("namespace") or Config.DCE_NAMESPACE
    tail_lines = int(query.get("tail_lines") or 200)
    client = K8sClient.from_config(Config)
    pod_status, pod_result = client.list_pods_by_app(namespace, deployment_name)
    if not 200 <= pod_status < 300:
        return {
            "is_success": False,
            "msg": "实例 Pod 查询失败",
            "http_status_code": pod_status,
            "response": pod_result,
            "lines": [],
        }

    pods = pod_result.get("items", []) or []
    running = [pod for pod in pods if (pod.get("status") or {}).get("phase") == "Running"]
    target = (running or pods or [None])[0]
    if not target:
        return {"is_success": False, "msg": "实例暂无可读取日志的 Pod", "lines": []}

    pod_name = (target.get("metadata") or {}).get("name")
    log_status, log_result = client.pod_logs(namespace, pod_name, tail_lines=tail_lines)
    if not 200 <= log_status < 300:
        return {
            "is_success": False,
            "msg": "实例日志查询失败",
            "http_status_code": log_status,
            "response": log_result,
            "lines": [],
        }
    raw = log_result.get("raw", "")
    return {"is_success": True, "pod_name": pod_name, "lines": raw.splitlines() if raw else []}


def pod_logs(query: dict) -> dict:
    try:
        from backend.modules.pods.service import pod_logs as _pods_pod_logs
    except ModuleNotFoundError:
        from modules.pods.service import pod_logs as _pods_pod_logs
    return _pods_pod_logs(query)
