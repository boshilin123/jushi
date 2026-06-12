try:
    from backend.db.mysql import get_connection
except ModuleNotFoundError:
    from db.mysql import get_connection


def find_user_by_username(username: str):
    # 登录时按用户名查用户。这里会取出 password，用于前期明文密码比对。
    sql = """
        SELECT id, username, password, real_name, role, status, created_at, updated_at
        FROM sys_user
        WHERE username = %s
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (username,))
            return cursor.fetchone()


def find_user_by_id(user_id: int):
    # token 校验通过后再按 user_id 查一次数据库，确保用户未被删除或禁用。
    sql = """
        SELECT id, username, real_name, role, status, created_at, updated_at
        FROM sys_user
        WHERE id = %s
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (user_id,))
            return cursor.fetchone()
