import os
import time

try:
    from backend.db.mysql import get_connection
    from backend.modules.system.schema import (
        LOGO_CONFIG_KEY,
        LOGO_UPLOAD_DIR,
    )
    from backend.common.response import success, fail
except ModuleNotFoundError:
    from db.mysql import get_connection
    from modules.system.schema import (
        LOGO_CONFIG_KEY,
        LOGO_UPLOAD_DIR,
    )
    from common.response import success, fail


def get_logo() -> dict:
    """读取当前 logo 路径，返回前端可用的 URL。"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT config_value FROM sys_config WHERE config_key = %s",
                (LOGO_CONFIG_KEY,),
            )
            row = cursor.fetchone()
    finally:
        conn.close()

    logo_path = row["config_value"] if row else ""
    if not logo_path:
        return {"logo_url": ""}

    # 通过 API 路径返回图片，兼容 nginx 只代理 /api/* 的部署方式
    return {"logo_url": "/api/system/logo/file"}


def get_logo_file_path() -> str | None:
    """返回当前 logo 的磁盘绝对路径，不存在时返回 None。"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT config_value FROM sys_config WHERE config_key = %s",
                (LOGO_CONFIG_KEY,),
            )
            row = cursor.fetchone()
    finally:
        conn.close()

    path = row["config_value"] if row else ""
    if path and os.path.isfile(path):
        return path
    return None


def upload_logo(file_storage) -> tuple:
    """保存上传的 logo，更新数据库，返回 Flask 响应。"""
    # 1. 保存文件
    os.makedirs(LOGO_UPLOAD_DIR, exist_ok=True)
    _, ext = os.path.splitext(file_storage.filename)
    timestamp = int(time.time() * 1000)
    new_filename = f"logo_{timestamp}{ext.lower()}"
    new_path = os.path.join(LOGO_UPLOAD_DIR, new_filename)

    try:
        file_storage.save(new_path)
    except Exception as exc:
        return fail(f"保存文件失败：{exc}", 500)

    # 2. 读写数据库
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT config_value FROM sys_config WHERE config_key = %s",
                (LOGO_CONFIG_KEY,),
            )
            old_row = cursor.fetchone()
            old_path = old_row["config_value"] if old_row else ""

            cursor.execute(
                """INSERT INTO sys_config (config_key, config_value)
                   VALUES (%s, %s)
                   ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)""",
                (LOGO_CONFIG_KEY, new_path),
            )
    finally:
        conn.close()

    # 3. 删除旧文件
    if old_path and os.path.isfile(old_path):
        try:
            os.remove(old_path)
        except OSError:
            pass

    return success({"logo_url": "/api/system/logo/file"})
