from . import detector, repository


def list_alerts(query: dict) -> dict:
    # 告警列表先扫描 algorithm 命名空间，再返回未静默/未解决的实例级告警。
    detected, scan_error = detector.detect_algorithm_alerts()
    written = repository.upsert_detected_alerts(detected)
    result = repository.list_alerts(query)
    return {"is_success": True, "scan_error": scan_error, "detected": len(detected), "written": written, **result}


def create_alert(payload: dict) -> dict:
    # 告警创建业务，后续由资源、部署、Pod 等异常流程调用。
    return repository.create_alert(payload)


def resolve_alert(payload: dict) -> dict:
    # 告警解决业务，记录处理人和解决时间。
    return repository.update_alert_status(payload, "resolved")


def ignore_alert(payload: dict) -> dict:
    # 告警忽略业务，记录忽略状态。
    return repository.update_alert_status(payload, "ignored")
