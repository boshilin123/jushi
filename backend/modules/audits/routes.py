import json

from flask import Blueprint, Response, jsonify, request

from . import service
from .schema import normalize_audit_export, normalize_audit_list

audits_bp = Blueprint("audits", __name__)


@audits_bp.post("/list")
def list_audits():
    payload = request.get_json(silent=True) or {}
    query = normalize_audit_list(payload)
    data = service.list_audit_logs(query)

    return jsonify({
        "msg_id": f"{payload.get('msg_id', '')}_Resp".replace("_Resp_Resp", "_Resp"),
        "serial": payload.get("serial", ""),
        "context": payload.get("context", ""),
        "http_status_code": 200,
        "is_success": True,
        "content": {
            "list": data.get("list", []),
            "total": data.get("total", 0),
            "page": data.get("page", 1),
            "page_size": data.get("page_size", 20),
        },
    })


@audits_bp.post("/export")
def export_audits():
    payload = request.get_json(silent=True) or {}
    query = normalize_audit_export(payload)
    records = service.export_audit_logs(query)

    json_str = json.dumps(records, ensure_ascii=False, indent=2, default=str)
    return Response(
        json_str,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=audit_logs.json"},
    )
