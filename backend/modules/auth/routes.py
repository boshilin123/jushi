from flask import Blueprint, jsonify, request

from . import service


auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    # 用户登录入口，后续改为校验 sys_user 表并签发真实 token。
    payload = request.get_json(silent=True) or {}
    result, status_code = service.login(payload)
    return jsonify(result), status_code


@auth_bp.post("/logout")
def logout():
    # 用户登出入口，一期可前端清理 token，后续可接 token 黑名单。
    return jsonify(service.logout())


@auth_bp.get("/me")
def me():
    # 查询当前登录用户信息，前端用于恢复登录态和页面权限判断。
    return jsonify(service.current_user())
