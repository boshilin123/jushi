from . import repository
from .schema import validate_port_payload


def list_ports() -> dict:
    # 查询封闭端口列表。
    return {"items": repository.list_port_rules()}


def add_port(payload: dict) -> tuple[dict, int]:
    # 新增封闭端口，先校验再写入。
    valid, message = validate_port_payload(payload)
    if not valid:
        return {"is_success": False, "msg": message}, 400

    rule, error = repository.add_port_rule(payload)
    # 重复端口由数据库唯一索引兜底，这里统一翻译成前端可识别的 409。
    if error:
        return {"is_success": False, "msg": error}, 409

    return {"is_success": True, **rule}, 200


def update_port(item_id: str, payload: dict) -> tuple[dict, int]:
    # 更新封闭端口，保持端口范围校验一致。
    valid, message = validate_port_payload(payload)
    if not valid:
        return {"is_success": False, "msg": message}, 400

    rule, error = repository.update_port_rule(item_id, payload)
    # 更新接口需要区分“不存在”和“端口重复”，方便页面给出不同提示。
    if error == "封闭端口不存在":
        return {"is_success": False, "msg": error}, 404
    if error:
        return {"is_success": False, "msg": error}, 409

    return {"is_success": True, **rule}, 200


def delete_port(item_id: str) -> tuple[dict, int]:
    # 删除封闭端口。
    result, error = repository.delete_port_rule(item_id)
    if error:
        return {"is_success": False, "msg": error}, 404

    return {"is_success": True, **result}, 200


def resolve_ports() -> dict:
    # 输出端口避让快照。
    return repository.resolve_blocked_ports()
