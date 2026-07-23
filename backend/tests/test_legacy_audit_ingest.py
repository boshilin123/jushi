import json
import unittest
import uuid
from datetime import datetime
from unittest.mock import patch

from flask import Flask

from backend import app as app_module
from backend.config import Config
from backend.modules.logs import internal_audit_bp
from backend.modules.logs import internal_routes, repository, service
from backend.modules.logs.schema import normalize_legacy_audit_event


def _valid_payload():
    return {
        "event_id": str(uuid.uuid4()),
        "source": "app_x86_195_bs",
        "path": "/api/deploy/create-default",
        "method": "POST",
        "operator": "admin",
        "operator_ip": "192.168.10.20",
        "target_name": "nvidia-cuda-test",
        "http_status_code": 200,
        "is_success": True,
        "error_message": "",
        "request_payload": {"content": {"creator": "admin"}},
        "response_payload": {"status": 0},
        "occurred_at": "2026-07-23 16:30:00",
    }


class _Cursor:
    def __init__(self, affected):
        self.affected = affected
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.statements.append((sql, list(params or [])))
        return self.affected


class _Connection:
    def __init__(self, affected):
        self.cursor_instance = _Cursor(affected)

    def cursor(self):
        return self.cursor_instance

    def close(self):
        return None


class LegacyAuditIngestTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(internal_audit_bp, url_prefix="/api/internal")
        self.client = app.test_client()

    def test_internal_endpoint_rejects_invalid_key(self):
        with (
            patch.object(Config, "AUDIT_INGEST_KEY", "correct-key"),
            patch.object(internal_routes.service, "ingest_legacy_audit_event") as ingest,
        ):
            response = self.client.post(
                "/api/internal/audit-events",
                headers={"X-Audit-Key": "wrong-key"},
                json=_valid_payload(),
            )

        self.assertEqual(response.status_code, 401)
        ingest.assert_not_called()

    def test_internal_endpoint_accepts_and_normalizes_valid_event(self):
        with (
            patch.object(Config, "AUDIT_INGEST_KEY", "correct-key"),
            patch.object(
                internal_routes.service,
                "ingest_legacy_audit_event",
                return_value={"is_success": True, "duplicate": False},
            ) as ingest,
        ):
            response = self.client.post(
                "/api/internal/audit-events",
                headers={"X-Audit-Key": "correct-key"},
                json=_valid_payload(),
            )

        self.assertEqual(response.status_code, 201)
        event = ingest.call_args.args[0]
        self.assertEqual(event["path"], "/api/deploy/create-default")
        self.assertEqual(event["source"], "app_x86_195_bs")
        self.assertEqual(event["occurred_at"], datetime(2026, 7, 23, 16, 30, 0))

    def test_internal_endpoint_returns_success_for_duplicate_event(self):
        with (
            patch.object(Config, "AUDIT_INGEST_KEY", "correct-key"),
            patch.object(
                internal_routes.service,
                "ingest_legacy_audit_event",
                return_value={"is_success": True, "duplicate": True},
            ),
        ):
            response = self.client.post(
                "/api/internal/audit-events",
                headers={"X-Audit-Key": "correct-key"},
                json=_valid_payload(),
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["duplicate"])

    def test_application_auth_interceptor_allows_key_protected_internal_endpoint(self):
        with (
            patch.object(Config, "AUDIT_INGEST_KEY", "correct-key"),
            patch.object(
                internal_routes.service,
                "ingest_legacy_audit_event",
                return_value={"is_success": True, "duplicate": False},
            ),
            patch.object(
                app_module,
                "start_resource_snapshot_collector",
                return_value=False,
            ),
            patch.object(
                app_module,
                "start_resource_trend_cache_refresher",
                return_value=False,
            ),
            patch.object(
                app_module,
                "start_accelerator_metric_collector",
                return_value=False,
            ),
        ):
            app = app_module.create_app()
            response = app.test_client().post(
                "/api/internal/audit-events",
                headers={"X-Audit-Key": "correct-key"},
                json=_valid_payload(),
            )

        self.assertEqual(response.status_code, 201)

    def test_schema_rejects_paths_outside_six_deploy_endpoints(self):
        payload = _valid_payload()
        payload["path"] = "/api/deploy/unsupported"

        event, error = normalize_legacy_audit_event(payload)

        self.assertIsNone(event)
        self.assertIn("six supported deploy endpoints", error)

    def test_service_maps_operation_and_redacts_sensitive_values(self):
        payload = _valid_payload()
        payload["request_payload"] = {
            "token": "secret-token",
            "content": {"password": "secret-password", "name": "safe-name"},
        }
        event, error = normalize_legacy_audit_event(payload)
        self.assertIsNone(error)

        with patch.object(
            repository,
            "save_external_operation_log",
            return_value={"is_success": True, "duplicate": False},
        ) as save:
            service.ingest_legacy_audit_event(event)

        record = save.call_args.args[0]
        request_payload = json.loads(record["request_payload"])
        self.assertEqual(record["operation_type"], "create")
        self.assertEqual(record["source"], "app_x86_195_bs")
        self.assertEqual(request_payload["token"], "[REDACTED]")
        self.assertEqual(request_payload["content"]["password"], "[REDACTED]")
        self.assertEqual(request_payload["content"]["name"], "safe-name")

    def test_repository_uses_event_id_for_database_deduplication(self):
        connection = _Connection(affected=0)
        record = {
            "event_id": str(uuid.uuid4()),
            "source": "app_x86_195_bs",
            "operation_type": "list",
            "operator": "admin",
            "http_status_code": 200,
            "is_success": True,
        }
        with (
            patch.object(repository, "_db_available", return_value=True),
            patch.object(repository, "get_connection", return_value=connection),
        ):
            result = repository.save_external_operation_log(record)

        sql, params = connection.cursor_instance.statements[0]
        self.assertIn("ON DUPLICATE KEY UPDATE", sql)
        self.assertEqual(params[0], record["event_id"])
        self.assertEqual(params[1], "app_x86_195_bs")
        self.assertTrue(result["duplicate"])


if __name__ == "__main__":
    unittest.main()
