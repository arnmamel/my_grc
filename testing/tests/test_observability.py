from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aws_local_audit.config import settings
from aws_local_audit.services.observability import ObservabilityService


class ObservabilityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.logs = self.root / "logs"
        self.logs.mkdir(parents=True, exist_ok=True)
        self.original_log_dir = settings.log_dir
        self.original_metrics = settings.metrics_log_file
        self.original_traces = settings.trace_log_file
        settings.log_dir = str(self.logs)
        settings.metrics_log_file = "metrics.log"
        settings.trace_log_file = "traces.log"
        (self.logs / "metrics.log").write_text(
            "\n".join(
                [
                    json.dumps({"metric": "workspace_auth_success_total", "value": 1, "type": "counter"}),
                    json.dumps({"metric": "database_backup_created_total", "value": 1, "type": "counter"}),
                ]
            ),
            encoding="utf-8",
        )
        (self.logs / "traces.log").write_text(
            "\n".join(
                [
                    json.dumps({"name": "workspace_authenticate", "status": "started"}),
                    json.dumps({"name": "workspace_authenticate", "status": "completed"}),
                ]
            ),
            encoding="utf-8",
        )
        self.service = ObservabilityService(root=self.root)

    def tearDown(self) -> None:
        settings.log_dir = self.original_log_dir
        settings.metrics_log_file = self.original_metrics
        settings.trace_log_file = self.original_traces
        self.tempdir.cleanup()

    def test_runtime_summary_aggregates_metric_and_trace_logs(self) -> None:
        report = self.service.runtime_summary()

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["metrics"]["entries"], 2)
        self.assertEqual(report["traces"]["entries"], 2)
        self.assertEqual(report["traces"]["error_count"], 0)


if __name__ == "__main__":
    unittest.main()
