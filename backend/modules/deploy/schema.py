def get_content(payload: dict) -> dict:
    # 读取统一请求包中的 content 字段。
    return payload.get("content", {}) or {}


def get_deploy_name(payload: dict) -> str:
    # 从统一请求包中提取部署名称。
    return str(get_content(payload).get("name") or "").strip()


def validate_create_payload(payload: dict) -> tuple[bool, str]:
    # 校验创建部署所需的核心字段。
    content = get_content(payload)
    if not content.get("devices"):
        return False, "缺少必填字段：content.devices"
    if not content.get("deployType"):
        return False, "缺少必填字段：content.deployType"
    if not content.get("creator"):
        return False, "缺少必填字段：content.creator"
    return True, ""
