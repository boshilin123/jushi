try:
    from backend.config import Config
    from backend.modules.deploy.repository import list_deploy_instances
    from backend.services.k8s_client import K8sClient
except ModuleNotFoundError:
    from config import Config
    from modules.deploy.repository import list_deploy_instances
    from services.k8s_client import K8sClient


IMAGE_PULL_REASONS = {"ImagePullBackOff", "ErrImagePull", "InvalidImageName"}
START_FAILED_REASONS = {"CrashLoopBackOff", "CreateContainerConfigError", "CreateContainerError", "RunContainerError"}
RESOURCE_MESSAGES = ("Insufficient nvidia.com/gpu", "Insufficient huawei.com/Ascend", "Insufficient cpu", "Insufficient memory")


def detect_algorithm_alerts() -> tuple[list[dict], dict | None]:
    namespace = "algorithm"
    client = K8sClient.from_config(Config)
    pod_status, pod_result = client.list_pods(namespace)
    if not 200 <= pod_status < 300:
        return [], {"source": "pods", "status": pod_status, "response": pod_result}

    event_status, event_result = client.list_events(namespace)
    events = event_result.get("items", []) if 200 <= event_status < 300 else []
    events_by_pod = {}
    for event in events:
        involved = event.get("involvedObject") or {}
        pod_name = involved.get("name")
        if pod_name:
            events_by_pod.setdefault(pod_name, []).append(event)

    records = {
        row.get("deployment_name"): row
        for row in list_deploy_instances()
        if row.get("deployment_name")
    }
    alerts = []
    for pod in pod_result.get("items", []) or []:
        alerts.extend(_detect_pod_alerts(namespace, pod, events_by_pod, records))
    return alerts, None


def _detect_pod_alerts(namespace: str, pod: dict, events_by_pod: dict, records: dict) -> list[dict]:
    meta = pod.get("metadata") or {}
    status = pod.get("status") or {}
    labels = meta.get("labels") or {}
    pod_name = meta.get("name") or ""
    deployment_name = labels.get("app") or _deployment_from_pod_name(pod_name)
    record = records.get(deployment_name, {})
    instance_name = record.get("instance_name") or deployment_name or pod_name
    created_at = record.get("created_at") or meta.get("creationTimestamp")
    events = events_by_pod.get(pod_name, [])

    context = {
        "namespace": namespace,
        "pod_name": pod_name,
        "deployment_name": deployment_name,
        "instance_name": instance_name,
        "created_at": created_at,
        "node_name": (pod.get("spec") or {}).get("nodeName"),
        "phase": status.get("phase"),
    }

    detected = []
    phase = status.get("phase")
    if phase == "Pending":
        message = _event_message(events) or "Pod 处于 Pending，实例暂不可用。"
        level = "high" if _has_resource_shortage(message) else "medium"
        title = "GPU 资源不足" if _has_resource_shortage(message) else "实例 Pending 超时"
        detected.append(_alert(context, "pod_pending", level, title, message, events))
    elif phase == "Failed":
        detected.append(_alert(context, "pod_failed", "high", "实例运行异常", "Pod 已进入 Failed 状态。", events))

    for container in status.get("containerStatuses", []) or []:
        state = container.get("state") or {}
        waiting = state.get("waiting") or {}
        terminated = state.get("terminated") or {}
        reason = waiting.get("reason") or terminated.get("reason")
        if reason in IMAGE_PULL_REASONS:
            detected.append(
                _alert(
                    context,
                    "image_pull_failed",
                    "high",
                    "镜像拉取失败",
                    waiting.get("message") or _event_message(events) or "镜像无法拉取，实例创建或重启流程中断。",
                    events,
                    container.get("name"),
                )
            )
        elif reason in START_FAILED_REASONS:
            detected.append(
                _alert(
                    context,
                    "container_start_failed",
                    "high",
                    "实例启动失败",
                    waiting.get("message") or _event_message(events) or "容器启动失败，实例暂不可用。",
                    events,
                    container.get("name"),
                )
            )
        elif reason == "OOMKilled":
            detected.append(
                _alert(
                    context,
                    "oom_killed",
                    "high",
                    "实例运行异常",
                    terminated.get("message") or "容器因内存不足被终止。",
                    events,
                    container.get("name"),
                )
            )
    return detected


def _alert(
    context: dict,
    alert_type: str,
    level: str,
    title: str,
    message: str,
    events: list[dict],
    container_name: str | None = None,
) -> dict:
    fingerprint_parts = [
        context["namespace"],
        context.get("deployment_name") or context.get("pod_name"),
        alert_type,
        container_name or "",
    ]
    return {
        "alert_type": alert_type,
        "alert_level": level,
        "title": title,
        "message": message,
        "source": "algorithm",
        "target_name": context.get("pod_name"),
        "instance_name": context.get("instance_name"),
        "deployment_name": context.get("deployment_name"),
        "fingerprint": ":".join(fingerprint_parts),
        "evidence": {
            **context,
            "container_name": container_name,
            "events": [_event_snapshot(event) for event in events[:5]],
        },
    }


def _deployment_from_pod_name(pod_name: str) -> str:
    parts = pod_name.rsplit("-", 2)
    if len(parts) >= 3:
        return parts[0]
    return pod_name


def _event_message(events: list[dict]) -> str:
    if not events:
        return ""
    latest = sorted(events, key=lambda item: item.get("lastTimestamp") or item.get("eventTime") or "", reverse=True)[0]
    return latest.get("message") or latest.get("reason") or ""


def _event_snapshot(event: dict) -> dict:
    return {
        "type": event.get("type"),
        "reason": event.get("reason"),
        "message": event.get("message"),
        "last_timestamp": event.get("lastTimestamp") or event.get("eventTime"),
    }


def _has_resource_shortage(message: str) -> bool:
    return any(item in (message or "") for item in RESOURCE_MESSAGES)
