USER_MUTABLE_FIELDS = ("username", "real_name", "role", "status")


def filter_user_payload(payload: dict) -> dict:
    # 过滤用户可写字段，避免前端传入无关字段直接进入数据库。
    return {key: payload[key] for key in USER_MUTABLE_FIELDS if key in payload}
