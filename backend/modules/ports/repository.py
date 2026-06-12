try:
    from backend.db.mysql import get_connection
except ModuleNotFoundError:
    from db.mysql import get_connection
from pymysql.err import IntegrityError


def _format_datetime(value):
    if not value:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _format_rule(row: dict) -> dict:
    # 数据库 id 是数字，接口文档中 item_id 按字符串传递；这里统一转成字符串返回。
    return {
        "id": str(row["id"]),
        "port": row["port"],
        "remark": row.get("remark"),
        "created_at": _format_datetime(row.get("created_at")),
        "updated_at": _format_datetime(row.get("updated_at")),
    }


def _normalize_rule_payload(payload: dict) -> dict:
    # service 层已经校验过端口范围；repository 只做入库前字段清洗。
    remark = str(payload.get("remark") or "").strip()
    return {
        "port": int(payload.get("port")),
        "remark": remark or None,
    }


def _parse_rule_id(item_id: str) -> int | None:
    try:
        rule_id = int(item_id)
    except (TypeError, ValueError):
        return None
    return rule_id if rule_id > 0 else None


def find_port_rule_by_id(item_id: str | int):
    # 更新和删除前先查一次，避免把不存在的 id 静默当作成功。
    rule_id = _parse_rule_id(str(item_id))
    if rule_id is None:
        return None

    sql = """
        SELECT id, port, remark, created_at, updated_at
        FROM port_block_rule
        WHERE id = %s
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (rule_id,))
            row = cursor.fetchone()

    return _format_rule(row) if row else None


def list_port_rules():
    # 查询封闭端口规则，供管理页面展示。
    sql = """
        SELECT id, port, remark, created_at, updated_at
        FROM port_block_rule
        ORDER BY port ASC, id ASC
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()

    return [_format_rule(row) for row in rows]


def add_port_rule(payload: dict):
    # 新增封闭端口规则，port_block_rule.port 唯一约束负责并发场景下的最终去重。
    data = _normalize_rule_payload(payload)
    sql = """
        INSERT INTO port_block_rule (port, remark)
        VALUES (%s, %s)
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (data["port"], data["remark"]))
                rule_id = cursor.lastrowid
    except IntegrityError:
        return None, "端口已存在"

    return find_port_rule_by_id(rule_id), None


def update_port_rule(item_id: str, payload: dict):
    # 更新封闭端口规则，允许修改端口和备注。
    rule_id = _parse_rule_id(item_id)
    if rule_id is None or not find_port_rule_by_id(rule_id):
        return None, "封闭端口不存在"

    data = _normalize_rule_payload(payload)
    sql = """
        UPDATE port_block_rule
        SET port = %s, remark = %s
        WHERE id = %s
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (data["port"], data["remark"], rule_id))
    except IntegrityError:
        return None, "端口已存在"

    return find_port_rule_by_id(rule_id), None


def delete_port_rule(item_id: str):
    # 删除封闭端口规则。
    rule_id = _parse_rule_id(item_id)
    if rule_id is None or not find_port_rule_by_id(rule_id):
        return None, "封闭端口不存在"

    sql = """
        DELETE FROM port_block_rule
        WHERE id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (rule_id,))

    return {"id": str(rule_id)}, None


def resolve_blocked_ports():
    # 生成端口避让快照，后续创建 Deployment 随机 NodePort 前会直接读取这个列表。
    sql = """
        SELECT port
        FROM port_block_rule
        ORDER BY port ASC
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()

    ports = sorted({int(row["port"]) for row in rows})
    return {"blocked_ports": ports, "blocked_singles": ports}
