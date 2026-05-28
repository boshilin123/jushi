def normalize_alert_query(payload: dict) -> dict:
    if not payload:
        return {}
    content = payload.get("content") or {}
    return {
        "level": content.get("level", "all"),
        "limit": content.get("limit", 20),
        "page": content.get("page", 1),
        "page_size": content.get("page_size", 20),
        "status": content.get("status"),
        "deployment_name": content.get("deployment_name"),
    }


def normalize_alert_action(payload: dict) -> dict:
    if not payload:
        return {}
    content = payload.get("content") or {}
    return {
        "id": content.get("id") or payload.get("id"),
        "resolver": content.get("resolver") or payload.get("resolver", ""),
    }


def normalize_alert_create(payload: dict) -> dict:
    if not payload:
        return {}
    content = payload.get("content") or {}
    source = content if content else payload
    return {
        "alert_type": source.get("alert_type", ""),
        "alert_level": source.get("alert_level", "low"),
        "title": source.get("title", ""),
        "message": source.get("message", ""),
        "source": source.get("source", ""),
        "target_name": source.get("target_name", ""),
        "instance_name": source.get("instance_name"),
        "deployment_name": source.get("deployment_name"),
        "fingerprint": source.get("fingerprint"),
        "evidence": source.get("evidence"),
        "status": source.get("status") or "open",
    }
