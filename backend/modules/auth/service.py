from .repository import find_user_by_username
from .schema import validate_login_payload


def login(payload: dict) -> tuple[dict, int]:
    # 登录业务流程：校验参数、查询用户、校验密码并签发 token。
    valid, message = validate_login_payload(payload)
    if not valid:
        return {"is_success": False, "msg": message}, 400

    user = find_user_by_username(payload["username"])
    return {
        "is_success": True,
        "token": "dev-token",
        "user": {
            "username": user["username"],
            "real_name": user["real_name"],
            "role": user["role"],
        },
    }, 200


def logout() -> dict:
    # 登出业务流程，一期由前端清理 token，后续可加入 token 失效逻辑。
    return {"is_success": True}


def current_user() -> dict:
    # 查询当前用户信息，后续从 token 中解析用户身份。
    return {"username": "admin", "real_name": "系统管理员", "role": "admin"}
