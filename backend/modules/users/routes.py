from flask import Blueprint, jsonify

from . import service


users_bp = Blueprint("users", __name__)


@users_bp.get("/list")
def list_users():
    # 查询用户列表，后续接入 sys_user 表并支持角色、状态筛选。
    return jsonify(service.list_users())
