def list_alerts(query: dict):
    # 查询告警列表，后续接入 alert_event 表。
    return []


def create_alert(payload: dict):
    # 创建告警事件。
    return {"is_success": True, **payload}


def update_alert_status(payload: dict, status: str):
    # 更新告警状态，如 resolved 或 ignored。
    return {"is_success": True, "status": status, **payload}
