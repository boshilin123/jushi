from urllib.parse import quote_plus


def envelope_field(payload: dict, key: str, default: str = "") -> str:
    return str(payload.get(key) or default)


def response_envelope(
    payload: dict,
    content: dict,
    http_status_code: int = 200,
    msg: str = "OK",
    status: int = 0,
) -> dict:
    # 部署类接口沿用旧服务 envelope，方便前端和历史脚本按 msg_id/serial/context 追踪链路。
    return {
        "msg_id": f"{envelope_field(payload, 'msg_id')}_Resp",
        "head_id": 0,
        "context": envelope_field(payload, "context"),
        "serial": envelope_field(payload, "serial"),
        "version": "1.0.0.1",
        "status": status,
        "content": content,
        "token": "",
        "http_status_code": http_status_code,
        "msg": msg,
        "is_success": 200 <= http_status_code < 300,
    }


def deployment_items(result) -> list:
    # PaaS 列表接口通常把资源放在 items 中；异常结构按空列表处理，避免后续遍历报错。
    if isinstance(result, dict) and isinstance(result.get("items"), list):
        return result["items"]
    return []


def deployment_pod_path(cluster: str, namespace: str, name: str) -> str:
    label_selector = quote_plus(f"app={name}")
    return f"/clusters/{cluster}/namespaces/{namespace}/pods?labelSelector={label_selector}"


def pod_items(result) -> list:
    if isinstance(result, dict) and isinstance(result.get("items"), list):
        return result["items"]
    return []


def _container_state(container_status: dict) -> str | None:
    state = container_status.get("state") or {}
    if isinstance(state, dict) and state:
        return next(iter(state.keys()))
    return None


def summarize_pod(pod: dict) -> dict:
    metadata = pod.get("metadata", {}) or {}
    status_obj = pod.get("status", {}) or {}
    spec_obj = pod.get("spec", {}) or {}
    container_statuses = status_obj.get("containerStatuses", []) or []

    containers = []
    for container_status in container_statuses:
        containers.append({
            "name": container_status.get("name"),
            "ready": container_status.get("ready"),
            "restart_count": container_status.get("restartCount"),
            "state": _container_state(container_status),
        })

    restart_count = sum(
        int(item.get("restart_count") or 0)
        for item in containers
    )
    ready = bool(containers) and all(item.get("ready") for item in containers)

    return {
        "pod_name": metadata.get("name"),
        "namespace": metadata.get("namespace"),
        "phase": status_obj.get("phase"),
        "node_name": spec_obj.get("nodeName"),
        "pod_ip": status_obj.get("podIP"),
        "ip": status_obj.get("podIP"),
        "restart_count": restart_count,
        "ready": ready,
        "created_at": metadata.get("creationTimestamp") or status_obj.get("startTime"),
        "start_time": status_obj.get("startTime"),
        "containers": containers,
    }


def summarize_pods(pods: list[dict]) -> dict:
    return {
        "total_pods": len(pods),
        "running_pods": sum(1 for pod in pods if pod.get("phase") == "Running"),
        "ready_pods": sum(1 for pod in pods if pod.get("ready")),
    }
