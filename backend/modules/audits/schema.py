def normalize_audit_list(payload: dict) -> dict:
    content = (payload or {}).get("content") or {}
    return {
        "operator": content.get("operator", ""),
        "operation_type": content.get("operation_type", ""),
        "keyword": content.get("keyword", ""),
        "page": max(int(content.get("page", 1) or 1), 1),
        "page_size": max(min(int(content.get("page_size", 20) or 20), 100), 1),
    }


def normalize_audit_export(payload: dict) -> dict:
    content = (payload or {}).get("content") or {}
    return {
        "operator": content.get("operator", ""),
        "operation_type": content.get("operation_type", ""),
        "keyword": content.get("keyword", ""),
    }
