from . import repository


def list_alerts(query: dict) -> dict:
    # 告警列表业务，后续加入筛选、分页和排序。
    return {"is_success": True, **repository.list_alerts(query)}


def create_alert(payload: dict) -> dict:
    # 告警创建业务，后续由资源、部署、Pod 等异常流程调用。
    return repository.create_alert(payload)


def resolve_alert(payload: dict) -> dict:
    # 告警解决业务，记录处理人和解决时间。
    return repository.update_alert_status(payload, "resolved")


def ignore_alert(payload: dict) -> dict:
    # 告警忽略业务，记录忽略状态。
    return repository.update_alert_status(payload, "ignored")
