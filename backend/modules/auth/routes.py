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
    # 前端携带 Authorization: Bearer <token>，后端解析后返回当前用户。
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"is_success": False, "msg": "未登录"}), 401

    token = auth_header.removeprefix("Bearer ").strip()
    result, status_code = service.current_user_from_token(token)
    return jsonify(result), status_code
