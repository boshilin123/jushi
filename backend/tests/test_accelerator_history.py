import unittest
from datetime import datetime
from unittest.mock import patch

from backend.modules.resources import accelerator_collector


def _instant_row(labels, value):
    return {"metric": labels, "value": [100, str(value)]}


def _matrix_row(labels, values):
    return {
        "metric": labels,
        "values": [[timestamp, str(value)] for timestamp, value in values],
    }


class _InstantClient:
    def query(self, promql):
        labels = {
            "node": "worker-1",
            "UUID": "gpu-a",
            "gpu": "0",
            "device": "nvidia0",
            "modelName": "NVIDIA Test",
        }
        if "DCGM_FI_DEV_FB_TOTAL" in promql:
            return [_instant_row(labels, 24576)], None
        if "DCGM_FI_DEV_FB_USED" in promql:
            return [_instant_row(labels, 6144)], None
        return [], None


class _RangeClient:
    def query_range(self, promql, start, end, step):
        labels = {
            "node": "worker-1",
            "UUID": "gpu-a",
            "gpu": "0",
            "device": "nvidia0",
            "modelName": "NVIDIA Test",
        }
        values = [(start, 24576), (start + step, 24576)]
        if "DCGM_FI_DEV_FB_USED" in promql:
            values = [(start, 6144), (start + step, 12288)]
        if "DCGM" in promql:
            return [_matrix_row(labels, values)], None
        return [], None


class AcceleratorHistoryTests(unittest.TestCase):
    def test_instant_collection_merges_used_and_total(self):
        samples, diagnostics = accelerator_collector.collect_accelerator_samples(
            _InstantClient(),
            end_timestamp=1000,
            interval_seconds=60,
            cluster_name="test-cluster",
        )

        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["sampled_at"], datetime.fromtimestamp(960))
        self.assertEqual(samples[0]["cluster_name"], "test-cluster")
        self.assertEqual(samples[0]["node_name"], "worker-1")
        self.assertEqual(samples[0]["card_id"], "gpu-a")
        self.assertEqual(samples[0]["memory_used_mib"], 6144)
        self.assertEqual(samples[0]["memory_total_mib"], 24576)
        self.assertEqual(samples[0]["memory_utilization_percent"], 25)
        self.assertEqual(diagnostics["failed_queries"], [])

    def test_range_collection_produces_one_row_per_card_and_timestamp(self):
        samples, diagnostics = accelerator_collector.collect_accelerator_samples(
            _RangeClient(),
            start_timestamp=600,
            end_timestamp=720,
            interval_seconds=60,
            cluster_name="test-cluster",
        )

        self.assertEqual(len(samples), 2)
        self.assertEqual(
            [item["memory_utilization_percent"] for item in samples],
            [25, 50],
        )
        self.assertEqual(diagnostics["skipped_identity_rows"], 0)

    def test_missing_node_identity_is_skipped_instead_of_misattributed(self):
        class MissingNodeClient:
            def query(self, promql):
                labels = {"UUID": "gpu-a", "gpu": "0"}
                return [_instant_row(labels, 1)], None

        samples, diagnostics = accelerator_collector.collect_accelerator_samples(
            MissingNodeClient(),
            end_timestamp=1000,
            interval_seconds=60,
        )

        self.assertEqual(samples, [])
        self.assertGreater(diagnostics["skipped_identity_rows"], 0)

    @patch.object(accelerator_collector, "save_accelerator_samples")
    def test_collect_and_save_reports_repository_error(self, save_samples):
        save_samples.return_value = (0, "table missing")

        result = accelerator_collector.collect_and_save_once(
            _InstantClient(),
            now_timestamp=1000,
        )

        self.assertEqual(result["sample_count"], 1)
        self.assertEqual(result["saved_count"], 0)
        self.assertEqual(result["save_error"], "table missing")


if __name__ == "__main__":
    unittest.main()
