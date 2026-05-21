def normalize_alert_query(payload: dict) -> dict:
    # 规范告警查询条件，后续支持等级、状态、来源和时间范围。
    return payload or {}


def normalize_alert_action(payload: dict) -> dict:
    # 规范告警处理参数，后续至少包含告警 id 和处理人。
    return payload or {}
