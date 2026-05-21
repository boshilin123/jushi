from . import repository
from .schema import filter_user_payload


def list_users() -> dict:
    # 用户列表业务，后续可加入角色、状态、关键词筛选。
    return {"items": repository.list_users()}


def create_user(payload: dict) -> dict:
    # 创建用户业务，负责字段过滤、默认角色和密码初始化。
    return repository.create_user(filter_user_payload(payload))


def update_user(user_id: int, payload: dict) -> dict:
    # 更新用户业务，负责字段过滤和状态校验。
    return repository.update_user(user_id, filter_user_payload(payload))


def delete_user(user_id: int) -> dict:
    # 删除用户业务，后续默认改为禁用用户而不是物理删除。
    return repository.delete_user(user_id)
