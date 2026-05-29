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
_DATA_FILE = os.path.join(_DATA_DIR, "operation_logs.json")


def _db_available():
    try:
        conn = get_connection()
        conn.close()
        return True
    except Exception:
        return False


def _next_id():
    with _MEMORY_LOCK:
        if not _MEMORY_STORE:
            return 1
        return max(r.get("id", 0) for r in _MEMORY_STORE) + 1


def save_operation_log(record: dict):
    if _db_available():
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO operation_log
                       (operation_type, operator, operator_ip, target_type, target_name,
                        request_payload, response_payload, http_status_code, is_success, error_message)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        record.get("operation_type", ""),
                        record.get("operator", ""),
                        record.get("operator_ip", ""),
                        record.get("target_type", ""),
                        record.get("target_name", ""),
                        record.get("request_payload", ""),
                        record.get("response_payload", ""),
                        record.get("http_status_code", 0),
                        record.get("is_success", 0),
                        record.get("error_message", ""),
                    ),
                )
            return {"is_success": True}
        finally:
            conn.close()

    entry = dict(record)
    entry["id"] = _next_id()
    entry["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _MEMORY_LOCK:
        _MEMORY_STORE.append(entry)
    _save_file(_MEMORY_STORE)
    return {"is_success": True}


def list_operation_logs(query: dict):
    if _db_available():
        conn = get_connection()
        try:
            where_clauses = ["1=1"]
            params = []
            if query.get("operator"):
                where_clauses.append("operator = %s")
                params.append(query["operator"])
            if query.get("operation_type"):
                where_clauses.append("operation_type = %s")
                params.append(query["operation_type"])
            if query.get("keyword"):
                where_clauses.append("(target_name LIKE %s OR error_message LIKE %s)")
                kw = f"%{query['keyword']}%"
                params.extend([kw, kw])

            where_sql = " AND ".join(where_clauses)

            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS total FROM operation_log WHERE {where_sql}",
                    params,
                )
                total = cur.fetchone()["total"]

                page = query.get("page", 1)
                page_size = query.get("page_size", 20)
                offset = (page - 1) * page_size
                cur.execute(
                    f"SELECT * FROM operation_log WHERE {where_sql} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    params + [page_size, offset],
                )
                rows = cur.fetchall()
                for row in rows:
                    row["created_at"] = _fmt_dt(row.get("created_at"))
                return {"items": rows, "total": total}
        finally:
            conn.close()

    items = _load_file()
    if not items:
        with _MEMORY_LOCK:
            items = list(_MEMORY_STORE)

    if query.get("operator"):
        items = [r for r in items if r.get("operator") == query["operator"]]
    if query.get("operation_type"):
        items = [r for r in items if r.get("operation_type") == query["operation_type"]]
    if query.get("keyword"):
        kw = query["keyword"]
        items = [
            r for r in items
            if kw in str(r.get("target_name", "")) or kw in str(r.get("error_message", ""))
        ]

    items = sorted(items, key=lambda r: r.get("created_at", ""), reverse=True)
    total = len(items)
    page = query.get("page", 1)
    page_size = query.get("page_size", 20)
    offset = (page - 1) * page_size
    return {"items": items[offset:offset + page_size], "total": total}


def export_operation_logs(query: dict):
    if _db_available():
        conn = get_connection()
        try:
            where_clauses = ["1=1"]
            params = []
            if query.get("operator"):
                where_clauses.append("operator = %s")
                params.append(query["operator"])
            if query.get("operation_type"):
                where_clauses.append("operation_type = %s")
                params.append(query["operation_type"])
            if query.get("keyword"):
                where_clauses.append("(target_name LIKE %s OR error_message LIKE %s)")
                kw = f"%{query['keyword']}%"
                params.extend([kw, kw])

            where_sql = " AND ".join(where_clauses)

            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM operation_log WHERE {where_sql} ORDER BY created_at DESC",
                    params,
                )
                rows = cur.fetchall()
                for row in rows:
                    row["created_at"] = _fmt_dt(row.get("created_at"))
                return rows
        finally:
            conn.close()

    items = _load_file()
    if not items:
        with _MEMORY_LOCK:
            items = list(_MEMORY_STORE)

    if query.get("operator"):
        items = [r for r in items if r.get("operator") == query["operator"]]
    if query.get("operation_type"):
        items = [r for r in items if r.get("operation_type") == query["operation_type"]]
    if query.get("keyword"):
        kw = query["keyword"]
        items = [
            r for r in items
            if kw in str(r.get("target_name", "")) or kw in str(r.get("error_message", ""))
        ]
    return sorted(items, key=lambda r: r.get("created_at", ""), reverse=True)


def list_audit_envelope(query: dict):
    page = int(query.get("page", 1) or 1)
    page_size = int(query.get("page_size", 20) or 20)
    result = list_operation_logs({
        "operator": query.get("operator", ""),
        "operation_type": query.get("operation_type", ""),
        "keyword": query.get("keyword", ""),
        "page": page,
        "page_size": page_size,
    })
    return {
        "list": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size,
    }


def _load_file():
    try:
        with open(_DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_file(items: list):
    os.makedirs(_DATA_DIR, exist_ok=True)
    safe = [{k: _fmt_val(v) for k, v in r.items()} for r in items]
    with open(_DATA_FILE, "w") as f:
        json.dump(safe, f, ensure_ascii=False, indent=2, default=str)


def _fmt_dt(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val)


def _fmt_val(val):
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return val
