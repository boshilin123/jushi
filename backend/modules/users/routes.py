from flask import Blueprint, jsonify, request

from . import service


users_bp = Blueprint("users", __name__)


@users_bp.get("/list")
def list_users():
    # 查询用户列表，后续接入 sys_user 表并支持角色、状态筛选。
    return jsonify(service.list_users(request.args))


@users_bp.post("/create")
def create_user():
    # 创建用户，写入 sys_user 表并返回脱敏用户信息。
    payload = request.get_json(silent=True) or {}
    result, status_code = service.create_user(payload)
    return jsonify(result), status_code


@users_bp.post("/update")
def update_user():
    # 更新用户基础信息，不通过该接口修改密码。
    payload = request.get_json(silent=True) or {}
    result, status_code = service.update_user(payload)
    return jsonify(result), status_code


@users_bp.post("/delete")
def delete_user():
    # 删除用户采用物理删除，直接移除 sys_user 记录。
    payload = request.get_json(silent=True) or {}
    result, status_code = service.delete_user(payload)
    return jsonify(result), status_code


@users_bp.post("/reset-password")
def reset_password():
    # 重置用户密码，响应不会回显密码。
    payload = request.get_json(silent=True) or {}
    result, status_code = service.reset_password(payload)
    return jsonify(result), status_code
