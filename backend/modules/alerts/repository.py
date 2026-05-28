from datetime import datetime

try:
    from backend.db.mysql import get_connection
except ModuleNotFoundError:
    from db.mysql import get_connection


def _fmt_dt(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val)


def _row_to_alert(row: dict) -> dict:
    return {
        "id": str(row.get("id")),
        "alert_type": row.get("alert_type"),
        "alert_level": row.get("alert_level"),
        "level": row.get("alert_level"),
        "title": row.get("title"),
        "message": row.get("message"),
        "description": row.get("message"),
        "source": row.get("source"),
        "category": row.get("source"),
        "target_name": row.get("target_name"),
        "target": row.get("target_name"),
        "status": row.get("status"),
        "created_at": _fmt_dt(row.get("created_at")),
        "resolved_at": _fmt_dt(row.get("resolved_at")),
        "resolver": row.get("resolver"),
    }


def list_alerts(query: dict):
    conditions = []
    params = []
    level = query.get("level")
    if level and level != "all":
        conditions.append("alert_level = %s")
        params.append(level)
    if query.get("status"):
        conditions.append("status = %s")
        params.append(query["status"])
    if query.get("source"):
        conditions.append("source = %s")
        params.append(query["source"])

    page = max(int(query.get("page") or 1), 1)
    page_size = max(min(int(query.get("page_size") or query.get("limit") or 20), 100), 1)
    offset = (page - 1) * page_size
    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS total FROM alert_event {where_sql}", tuple(params))
            total = (cur.fetchone() or {}).get("total", 0)
            cur.execute(
                f"""
                SELECT *
                FROM alert_event
                {where_sql}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                tuple(params + [page_size, offset]),
            )
            rows = cur.fetchall() or []

    return {
        "items": [_row_to_alert(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def create_alert(payload: dict):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alert_event
                    (alert_type, alert_level, title, message, source, target_name, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    payload.get("alert_type", ""),
                    payload.get("alert_level", "low"),
                    payload.get("title", ""),
                    payload.get("message", ""),
                    payload.get("source", ""),
                    payload.get("target_name", ""),
                    payload.get("status") or "open",
                ),
            )
            alert_id = cur.lastrowid
    return {"is_success": True, "id": str(alert_id)}


def update_alert_status(payload: dict, status: str):
    alert_id = payload.get("id")
    resolver = payload.get("resolver", "")
    if not alert_id:
        return {"is_success": False, "msg": "id 不能为空"}

    resolved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "resolved" else None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE alert_event
                SET status = %s, resolver = %s, resolved_at = %s
                WHERE id = %s
                """,
                (status, resolver, resolved_at, alert_id),
            )
            affected_rows = cur.rowcount

    if affected_rows <= 0:
        return {"is_success": False, "msg": "告警不存在", "id": str(alert_id)}
    return {"is_success": True, "id": str(alert_id), "status": status}
