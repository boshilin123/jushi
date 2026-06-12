AUDIT_PATHS = {
    "/api/audits/list": {
        "post": {
            "tags": ["Audits"],
            "summary": "操作审计列表",
            "requestBody": {"$ref": "#/components/requestBodies/AuditListBody"},
            "responses": {"200": {"description": "审计列表"}},
        }
    },
    "/api/audits/export": {
        "post": {
            "tags": ["Audits"],
            "summary": "导出操作审计",
            "requestBody": {"$ref": "#/components/requestBodies/AuditExportBody"},
            "responses": {"200": {"description": "JSON or Excel file download"}},
        }
    },
}
