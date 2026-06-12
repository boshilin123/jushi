def validate_port_payload(payload: dict) -> tuple[bool, str]:
    # 校验封闭端口请求，端口范围先按 NodePort 规划限制。
    try:
        port = int(payload.get("port"))
    except (TypeError, ValueError):
        return False, "port 必须是整数"
    if port < 30000 or port > 59999:
        return False, "port 必须在 30000 到 59999 之间"
    return True, ""
