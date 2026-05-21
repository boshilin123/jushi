def list_users():
    # 查询用户列表，后续接入 sys_user 表。
    return []


def create_user(data: dict):
    # 新增用户记录，后续写入 sys_user 表并加密密码。
    return {"id": None, **data}


def update_user(user_id: int, data: dict):
    # 更新用户记录，后续按 user_id 修改 sys_user 表。
    return {"id": user_id, **data}


def delete_user(user_id: int):
    # 删除或禁用用户，一期建议优先做逻辑禁用。
    return {"id": user_id, "is_success": True}
