from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from aws_local_audit.config import settings


class ObservabilityService:
    def __init__(self, *, root: Path | None = None):
        self.root = root or Path(__file__).resolve().parents[3]

    def runtime_summary(self, *, limit: int = 2000) -> dict:
        metrics = self.metrics_summary(limit=limit)
        traces = self.trace_summary(limit=limit)
        log_dir = self.log_directory()
        status = "pass" if metrics["entries"] or traces["entries"] else "warn"
        if traces["error_count"] > 0:
            status = "warn"
        return {
            "status": status,
            "detail": f"{metrics['entries']} metric event(s), {traces['entries']} trace event(s), {traces['error_count']} trace error event(s).",
            "log_dir": str(log_dir),
            "metrics": metrics,
            "traces": traces,
        }

    def metrics_summary(self, *, limit: int = 2000) -> dict:
        rows = self._read_json_lines(self.log_directory() / settings.metrics_log_file, limit=limit)
        by_metric = defaultdict(float)
        counts = Counter()
        for item in rows:
            metric_name = item.get("metric", "unknown")
            counts[metric_name] += 1
            try:
                by_metric[metric_name] += float(item.get("value", 0.0))
            except (TypeError, ValueError):
                continue
        return {
            "entries": len(rows),
            "metrics": [
                {"metric": name, "events": counts[name], "value_sum": round(by_metric[name], 2)}
                for name in sorted(counts)
            ],
        }

    def trace_summary(self, *, limit: int = 2000) -> dict:
        rows = self._read_json_lines(self.log_directory() / settings.trace_log_file, limit=limit)
        counts = Counter()
        error_count = 0
        for item in rows:
            counts[item.get("name", "unknown")] += 1
            if item.get("status") == "error":
                error_count += 1
        return {
            "entries": len(rows),
            "error_count": error_count,
            "spans": [{"name": name, "events": counts[name]} for name in sorted(counts)],
        }

    def log_directory(self) -> Path:
        directory = Path(settings.log_dir)
        if not directory.is_absolute():
            directory = self.root / directory
        return directory

    @staticmethod
    def _read_json_lines(path: Path, *, limit: int) -> list[dict]:
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
        rows = []
        for line in lines:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows
