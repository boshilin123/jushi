from . import repository
from .schema import (
    parse_user_list_query,
    validate_create_payload,
    validate_delete_payload,
    validate_reset_password_payload,
    validate_update_payload,
)


def list_users(args=None) -> dict:
    # 用户列表业务，后续可加入角色、状态、关键词筛选。
    query = parse_user_list_query(args or {})
    result = repository.list_users(query)

    return {
        "is_success": True,
        "items": result["items"],
        "total": result["total"],
        "page": query["page"],
        "page_size": query["page_size"],
    }


def create_user(payload: dict) -> tuple[dict, int]:
    # 创建用户业务：校验入参、写入 sys_user，并返回脱敏后的用户信息。
    data, error = validate_create_payload(payload)
    if error:
        return {"is_success": False, "msg": error}, 400

    user, error = repository.create_user(data)
    if error:
        return {"is_success": False, "msg": error}, 409

    return {"is_success": True, "user": user, "id": user["id"]}, 200


def update_user(payload: dict) -> tuple[dict, int]:
    # 更新用户业务：只允许修改真实姓名、角色和状态。
    user_id, data, error = validate_update_payload(payload)
    if error:
        return {"is_success": False, "msg": error}, 400

    user, error = repository.update_user(user_id, data)
    if error:
        return {"is_success": False, "msg": error}, 404

    return {"is_success": True, "user": user}, 200


def delete_user(payload: dict) -> tuple[dict, int]:
    # 删除用户业务：按需求执行物理删除，返回被删除用户的脱敏快照。
    user_id, error = validate_delete_payload(payload)
    if error:
        return {"is_success": False, "msg": error}, 400

    user, error = repository.delete_user(user_id)
    if error:
        return {"is_success": False, "msg": error}, 404

    return {"is_success": True, "user": user}, 200


def reset_password(payload: dict) -> tuple[dict, int]:
    # 重置密码业务：当前阶段明文保存，但响应中不回显密码。
    user_id, password, error = validate_reset_password_payload(payload)
    if error:
        return {"is_success": False, "msg": error}, 400

    user, error = repository.reset_password(user_id, password)
    if error:
        return {"is_success": False, "msg": error}, 404

    return {"is_success": True, "user": user}, 200
