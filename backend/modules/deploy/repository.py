import json
from contextlib import contextmanager

try:
    from backend.db.mysql import get_connection
except ModuleNotFoundError:
    from db.mysql import get_connection


class DeployCreateLockError(RuntimeError):
    pass


@contextmanager
def deploy_create_lock(timeout_seconds: int = 10):
    # 使用 MySQL 连接级 GET_LOCK，保证多 API 副本下创建链路仍然串行。
    conn = get_connection()
    lock_name = "jushi_deploy_create"
    acquired = False
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, %s) AS acquired", (lock_name, timeout_seconds))
            row = cursor.fetchone() or {}
            acquired = row.get("acquired") == 1
        if not acquired:
            raise DeployCreateLockError("当前有部署正在创建，请稍后重试")
        yield
    finally:
        if acquired:
            with conn.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
        conn.close()


def save_deploy_instance(record: dict):
    # 保存部署实例记录，创建成功后写入 deploy_instance 表。
    node_ports = record.get("node_ports")
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM deploy_instance LIKE 'instance_name'")
            has_instance_name = cursor.fetchone() is not None

    instance_columns = "instance_name,\n            " if has_instance_name else ""
    instance_values = "%s, " if has_instance_name else ""
    sql = """
        INSERT INTO deploy_instance (
            {instance_columns}
            deployment_name,
            gpu_vendor,
            gpu_type,
            gpu_count,
            deploy_type,
            creator,
            status,
            node_ports,
            log_path
        )
        VALUES ({instance_values}%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """.format(instance_columns=instance_columns, instance_values=instance_values)
    params = []
    if has_instance_name:
        params.append(record.get("instance_name"))
    params.extend(
        [
            record["deployment_name"],
            record["gpu_vendor"],
            record["gpu_type"],
            record["gpu_count"],
            record["deploy_type"],
            record["creator"],
            record.get("status", "running"),
            json.dumps(node_ports, ensure_ascii=False) if node_ports is not None else None,
            record.get("log_path"),
        ]
    )
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, tuple(params))
            record["id"] = cursor.lastrowid
    return record


def list_deploy_instances():
    # 查询部署实例列表，后续优先从 deploy_instance 表读取并补充实时状态。
    return []


def update_deploy_status(name: str, status: str):
    # 更新部署实例状态，如 created、running、released、failed。
    return {"deployment_name": name, "status": status}
