try:
    from backend.services.k8s_client import K8sClient
except ModuleNotFoundError:
    from services.k8s_client import K8sClient


_k8s = K8sClient()


def list_pods(query: dict) -> dict:
    namespace = query.get("namespace", "algorithm")
    pods = _k8s.list_pods(namespace)

    deployment_name = query.get("deployment_name")
    if deployment_name:
        pods = [p for p in pods if p["pod_name"].startswith(deployment_name)]
    phase = query.get("phase")
    if phase:
        pods = [p for p in pods if p["phase"] == phase]
    node_name = query.get("node_name")
    if node_name:
        pods = [p for p in pods if p["node_name"] == node_name]

    return {"items": pods}


def pod_detail(query: dict) -> dict:
    namespace = query.get("namespace", "algorithm")
    pod_name = query.get("pod_name", "")
    if not pod_name:
        return {"msg": "pod_name 不能为空"}
    return _k8s.read_pod(namespace, pod_name)


def pod_logs(query: dict) -> dict:
    namespace = query.get("namespace", "algorithm")
    pod_name = query.get("pod_name", "")
    tail_lines = query.get("tail_lines", 200)
    if not pod_name:
        return {"lines": []}
    lines = _k8s.pod_logs(namespace, pod_name, tail_lines=tail_lines)
    return {"lines": lines}


def delete_pod(action: dict) -> dict:
    namespace = action.get("namespace", "algorithm")
    pod_name = action.get("pod_name", "")
    if not pod_name:
        return {"is_success": False, "msg": "pod_name 不能为空"}
    deleted = _k8s.delete_pod(namespace, pod_name)
    if not deleted:
        return {"is_success": False, "msg": "Pod 不存在"}
    return {"is_success": True}


def restart_pod(action: dict) -> dict:
    namespace = action.get("namespace", "algorithm")
    pod_name = action.get("pod_name", "")
    if not pod_name:
        return {"is_success": False, "msg": "pod_name 不能为空"}
    deleted = _k8s.delete_pod(namespace, pod_name)
    if not deleted:
        return {"is_success": False, "msg": "Pod 不存在"}
    return {"is_success": True}
