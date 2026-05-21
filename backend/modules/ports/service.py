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
    return repository.add_port_rule(payload), 200


def update_port(item_id: str, payload: dict) -> tuple[dict, int]:
    # 更新封闭端口，保持端口范围校验一致。
    valid, message = validate_port_payload(payload)
    if not valid:
        return {"is_success": False, "msg": message}, 400
    return repository.update_port_rule(item_id, payload), 200


def delete_port(item_id: str) -> dict:
    # 删除封闭端口。
    return repository.delete_port_rule(item_id)


def resolve_ports() -> dict:
    # 输出端口避让快照。
    return repository.resolve_blocked_ports()
