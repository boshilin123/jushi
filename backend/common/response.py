from flask import jsonify


def success(data=None, **extra):
    # 统一成功响应格式，后续所有接口优先从这里返回。
    payload = {"is_success": True}
    if data is not None:
        payload.update(data if isinstance(data, dict) else {"data": data})
    payload.update(extra)
    return jsonify(payload)


def fail(message: str, http_status_code: int = 400, **extra):
    # 统一失败响应格式，便于前端和 Swagger 对错误结构形成稳定预期。
    payload = {
        "is_success": False,
        "msg": message,
        "http_status_code": http_status_code,
    }
    payload.update(extra)
    return jsonify(payload), http_status_code
