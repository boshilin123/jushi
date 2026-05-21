def find_user_by_username(username: str):
    # 查询用户基础信息，后续接入 sys_user 表。
    return {
        "id": 1,
        "username": username,
        "password_hash": "dev-password",
        "real_name": "系统管理员",
        "role": "admin",
        "status": "active",
    }
