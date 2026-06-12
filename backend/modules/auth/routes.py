from flask import Blueprint, g, jsonify, request

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
    # 登出接口的 token 校验已由全局拦截器完成，这里只处理登出业务语义。
    token = getattr(g, "auth_token", "")
    result, status_code = service.logout(token)
    return jsonify(result), status_code


@auth_bp.get("/me")
def me():
    # 当前用户由全局拦截器解析并挂到 g.current_user。
    return jsonify({"is_success": True, "user": getattr(g, "current_user", None)})
