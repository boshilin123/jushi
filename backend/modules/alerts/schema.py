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
        "source": content.get("source"),
    }


def normalize_alert_action(payload: dict) -> dict:
    if not payload:
        return {}
    return {
        "id": payload.get("id"),
        "resolver": payload.get("resolver", ""),
    }
