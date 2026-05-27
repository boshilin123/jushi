import json
import os
import threading
from datetime import datetime

try:
    from backend.db.mysql import get_connection
except ModuleNotFoundError:
    from db.mysql import get_connection


_MEMORY_STORE = []
_MEMORY_LOCK = threading.Lock()

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_DATA_FILE = os.path.join(_DATA_DIR, "alerts.json")


def _db_available():
    try:
        conn = get_connection()
        conn.close()
        return True
    except Exception:
        return False


def _read_memory():
    with _MEMORY_LOCK:
        return list(_MEMORY_STORE)


def _write_memory(alert: dict):
    with _MEMORY_LOCK:
        _MEMORY_STORE.append(alert)


def _update_memory(alert_id: int, status: str, resolver: str):
    with _MEMORY_LOCK:
        for a in _MEMORY_STORE:
            if a.get("id") == alert_id:
                a["status"] = status
                a["resolver"] = resolver
                if status == "resolved":
                    a["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return True
    return False


def _load_file():
    try:
        with open(_DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_file(alerts: list):
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_DATA_FILE, "w") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)


def list_alerts(query: dict):
    if _db_available():
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                sql = "SELECT * FROM alert_event ORDER BY created_at DESC"
                cur.execute(sql)
                rows = cur.fetchall()
                for row in rows:
                    row["created_at"] = _fmt_dt(row.get("created_at"))
                    row["resolved_at"] = _fmt_dt(row.get("resolved_at"))
                return rows
        finally:
            conn.close()

    # 内存 / 文件回退
    alerts = _load_file()
    if not alerts:
        alerts = _read_memory()
    return sorted(alerts, key=lambda a: a.get("created_at", ""), reverse=True)


def create_alert(payload: dict):
    if _db_available():
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO alert_event
                       (alert_type, alert_level, title, message, source, target_name, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        payload.get("alert_type", ""),
                        payload.get("alert_level", "low"),
                        payload.get("title", ""),
                        payload.get("message", ""),
                        payload.get("source", ""),
                        payload.get("target_name", ""),
                        "open",
                    ),
                )
                alert_id = cur.lastrowid
            conn.commit()
            return {"is_success": True, "id": alert_id}
        finally:
            conn.close()

    # 内存 / 文件回退
    alert = {
        "id": len(_read_memory()) + 1,
        "alert_type": payload.get("alert_type", ""),
        "alert_level": payload.get("alert_level", "low"),
        "title": payload.get("title", ""),
        "message": payload.get("message", ""),
        "source": payload.get("source", ""),
        "target_name": payload.get("target_name", ""),
        "status": "open",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "resolved_at": None,
        "resolver": None,
    }
    _write_memory(alert)
    _save_file(_read_memory())
    return {"is_success": True, "id": alert["id"]}


def update_alert_status(payload: dict, status: str):
    alert_id = payload.get("id")
    resolver = payload.get("resolver", "")
    if not alert_id:
        return {"is_success": False, "msg": "id 不能为空"}

    if _db_available():
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                resolved_at = (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if status == "resolved"
                    else None
                )
                cur.execute(
                    "UPDATE alert_event SET status=%s, resolver=%s, resolved_at=%s WHERE id=%s",
                    (status, resolver, resolved_at, alert_id),
                )
            conn.commit()
            return {"is_success": True, "id": alert_id, "status": status}
        finally:
            conn.close()

    # 内存 / 文件回退
    found = _update_memory(int(alert_id), status, resolver)
    _save_file(_read_memory())
    if found:
        return {"is_success": True, "id": alert_id, "status": status}
    return {"is_success": False, "msg": "告警不存在"}


def _fmt_dt(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val)
