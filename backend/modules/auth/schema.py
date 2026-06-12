LOGIN_REQUIRED_FIELDS = ("username", "password")


def validate_login_payload(payload: dict) -> tuple[bool, str]:
    # 校验登录请求的必要字段，后续可扩展验证码、登录来源等字段。
    for field in LOGIN_REQUIRED_FIELDS:
        if not payload.get(field):
            return False, f"缺少必填字段：{field}"
    return True, ""
