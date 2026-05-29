try:
    from backend.modules.logs.repository import export_operation_logs, list_audit_envelope
except ModuleNotFoundError:
    from modules.logs.repository import export_operation_logs, list_audit_envelope


def list_audit_logs(query: dict) -> dict:
    return list_audit_envelope(query)


def export_audit_logs(query: dict) -> list:
    return export_operation_logs(query)
