def get_content(payload: dict) -> dict:
    # 读取统一请求包中的 content 字段。
    return payload.get("content", {}) or {}


def get_deploy_name(payload: dict) -> str:
    # 从统一请求包中提取部署名称。
    return str(get_content(payload).get("name") or "").strip()


DEPLOY_ENVELOPE_RULES = {
    "check": {
        "prefix": "check-",
        "context": "check deploy available",
    },
    "create": {
        "prefix": "create-",
        "context": "create inference instance",
    },
    "retrieve": {
        "prefix": "retrieve-",
        "context": "retrieve deploy",
    },
    "list": {
        "prefix": "list-",
        "context": "list deploy",
    },
    "release": {
        "prefix": "release-",
        "context": "release deploy",
    },
    "reset": {
        "prefix": "reset-",
        "context": "restart deploy",
    },
    "stop": {
        "prefix": "stop-",
        "context": "stop deploy",
    },
    "logs": {
        "prefix": "logs-",
        "context": "deploy logs",
    },
}


def validate_deploy_envelope(payload: dict, action: str) -> tuple[bool, str]:
    # 部署类接口按动作约束 msg_id / serial / context，避免前端混用创建、查询等请求流水。
    rule = DEPLOY_ENVELOPE_RULES[action]
    if not isinstance(payload, dict):
        return False, "请求体必须是 JSON 对象"
    if not isinstance(payload.get("content"), dict):
        return False, "缺少必填字段：content"

    prefix = rule["prefix"]
    for field in ("msg_id", "serial"):
        value = str(payload.get(field) or "").strip()
        if not value:
            return False, f"缺少必填字段：{field}"
        if not value.startswith(prefix):
            return False, f"{field} 必须以 {prefix} 开头"

    context = str(payload.get("context") or "").strip()
    if not context:
        return False, "缺少必填字段：context"
    if context != rule["context"]:
        return False, f"context 必须为 {rule['context']}"
    return True, ""


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
