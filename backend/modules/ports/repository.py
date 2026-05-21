def list_port_rules():
    # 查询封闭端口规则，后续接入 port_block_rule 表。
    return []


def add_port_rule(payload: dict):
    # 新增封闭端口规则，后续写入 port_block_rule 表。
    return {"is_success": True, **payload}


def update_port_rule(item_id: str, payload: dict):
    # 更新封闭端口规则。
    return {"id": item_id, "is_success": True, **payload}


def delete_port_rule(item_id: str):
    # 删除封闭端口规则。
    return {"id": item_id, "is_success": True}


def resolve_blocked_ports():
    # 生成端口避让快照，供创建实例前查询。
    return {"blocked_ports": [], "blocked_singles": []}
