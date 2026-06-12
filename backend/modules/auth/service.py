try:
    from backend.common.auth import create_token, parse_token
except ModuleNotFoundError:
    from common.auth import create_token, parse_token
from .repository import find_user_by_id, find_user_by_username
from .schema import validate_login_payload


def _public_user(user: dict) -> dict:
    # 对外返回用户信息时不带 password，避免明文密码出现在接口响应里。
    return {
        "id": user["id"],
        "username": user["username"],
        "real_name": user.get("real_name"),
        "role": user["role"],
        "status": user["status"],
    }


def login(payload: dict) -> tuple[dict, int]:
    # 登录主流程：参数校验 -> 查库 -> 状态校验 -> 明文密码比对 -> 签发 token。
    valid, message = validate_login_payload(payload)
    if not valid:
        return {"is_success": False, "msg": message}, 400

    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")

    user = find_user_by_username(username)
    if not user:
        return {"is_success": False, "msg": "用户名或密码错误"}, 401

    if user.get("status") != "active":
        return {"is_success": False, "msg": "用户已被禁用"}, 403

    if user.get("password") != password:
        return {"is_success": False, "msg": "用户名或密码错误"}, 401

    token = create_token(user)
    return {
        "is_success": True,
        "token": token,
        "user": _public_user(user),
    }, 200


def logout(token: str) -> tuple[dict, int]:
    # 当前 token 是无状态签名 token，一期登出由前端删除本地 token 即可。
    payload, error = parse_token(token)
    if error:
        return {"is_success": False, "msg": error}, 401

    return {
        "is_success": True,
        "msg": "登出成功"
    }, 200


def current_user_from_token(token: str) -> tuple[dict, int]:
    # 通过 Authorization Bearer token 恢复当前登录用户。
    payload, error = parse_token(token)
    if error:
        return {"is_success": False, "msg": error}, 401

    user = find_user_by_id(payload["id"])
    if not user:
        return {"is_success": False, "msg": "用户不存在"}, 401

    if user.get("status") != "active":
        return {"is_success": False, "msg": "用户已被禁用"}, 403

    return {"is_success": True, "user": _public_user(user)}, 200
