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


def _public_user(row: dict) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "real_name": row.get("real_name"),
        "role": row["role"],
        "status": row["status"],
        "created_at": _format_datetime(row.get("created_at")),
        "updated_at": _format_datetime(row.get("updated_at")),
    }


def list_users(query: dict):
    where_parts = []
    params = []

    if query.get("keyword"):
        where_parts.append("(username LIKE %s OR real_name LIKE %s)")
        keyword = f"%{query['keyword']}%"
        params.extend([keyword, keyword])

    if query.get("role"):
        where_parts.append("role = %s")
        params.append(query["role"])

    if query.get("status"):
        where_parts.append("status = %s")
        params.append(query["status"])

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM sys_user
        {where_sql}
    """

    list_sql = f"""
        SELECT id, username, real_name, role, status, created_at, updated_at
        FROM sys_user
        {where_sql}
        ORDER BY created_at DESC, id DESC
        LIMIT %s OFFSET %s
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(count_sql, tuple(params))
            total = cursor.fetchone()["total"]

            cursor.execute(
                list_sql,
                tuple(params + [query["page_size"], query["offset"]]),
            )
            rows = cursor.fetchall()

    return {
        "items": [_public_user(row) for row in rows],
        "total": total,
    }


def create_user(data: dict):
    # 新增用户记录，当前阶段按 init.sql 约定保存明文密码，返回时只返回脱敏信息。
    sql = """
        INSERT INTO sys_user (username, password, real_name, role, status)
        VALUES (%s, %s, %s, %s, %s)
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        data["username"],
                        data["password"],
                        data.get("real_name"),
                        data["role"],
                        data["status"],
                    ),
                )
                user_id = cursor.lastrowid
    except IntegrityError:
        return None, "用户名已存在"

    return find_user_by_id(user_id), None


def update_user(user_id: int, data: dict):
    # 更新用户基础信息，只允许修改 real_name、role、status。
    if not find_user_by_id(user_id):
        return None, "用户不存在"

    set_parts = []
    params = []
    for key in ("real_name", "role", "status"):
        if key in data:
            set_parts.append(f"{key} = %s")
            params.append(data[key])

    sql = f"""
        UPDATE sys_user
        SET {", ".join(set_parts)}
        WHERE id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, tuple(params + [user_id]))

    return find_user_by_id(user_id), None


def delete_user(user_id: int):
    # 按需求执行物理删除，直接从 sys_user 表移除该用户记录。
    user = find_user_by_id(user_id)
    if not user:
        return None, "用户不存在"

    sql = """
        DELETE FROM sys_user
        WHERE id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (user_id,))

    return user, None


def reset_password(user_id: int, password: str):
    # 重置密码只更新 password 字段，响应不返回密码本身。
    if not find_user_by_id(user_id):
        return None, "用户不存在"

    sql = """
        UPDATE sys_user
        SET password = %s
        WHERE id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (password, user_id))

    return find_user_by_id(user_id), None


def find_user_by_id(user_id: int):
    # 按 ID 查询脱敏用户信息，供增删改和重置密码后返回最新状态。
    sql = """
        SELECT id, username, real_name, role, status, created_at, updated_at
        FROM sys_user
        WHERE id = %s
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (user_id,))
            row = cursor.fetchone()

    return _public_user(row) if row else None
