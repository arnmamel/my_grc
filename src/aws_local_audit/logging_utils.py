from __future__ import annotations

import json
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from typing import Any

from aws_local_audit.config import settings

_LOGGING_LOCK = Lock()
_LOGGING_CONFIGURED = False


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_path(raw_value: str) -> Path:
    candidate = Path(raw_value)
    if candidate.is_absolute():
        return candidate
    return project_root() / candidate


def _log_directory() -> Path:
    directory = _resolve_path(settings.log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def configure_logging() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return
    with _LOGGING_LOCK:
        if _LOGGING_CONFIGURED:
            return

        log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
        directory = _log_directory()
        app_log_path = directory / settings.app_log_file
        audit_log_path = directory / settings.audit_log_file
        metrics_log_path = directory / settings.metrics_log_file
        trace_log_path = directory / settings.trace_log_file

        app_logger = logging.getLogger("my_grc")
        app_logger.setLevel(log_level)
        app_logger.propagate = False
        if not app_logger.handlers:
            app_handler = RotatingFileHandler(
                app_log_path,
                maxBytes=2_000_000,
                backupCount=5,
                encoding="utf-8",
            )
            app_handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
            )
            app_logger.addHandler(app_handler)

        audit_logger = logging.getLogger("my_grc.audit")
        audit_logger.setLevel(logging.INFO)
        audit_logger.propagate = False
        if not audit_logger.handlers:
            audit_handler = RotatingFileHandler(
                audit_log_path,
                maxBytes=2_000_000,
                backupCount=5,
                encoding="utf-8",
            )
            audit_handler.setFormatter(logging.Formatter("%(message)s"))
            audit_logger.addHandler(audit_handler)

        metrics_logger = logging.getLogger("my_grc.metrics")
        metrics_logger.setLevel(logging.INFO)
        metrics_logger.propagate = False
        if not metrics_logger.handlers:
            metrics_handler = RotatingFileHandler(
                metrics_log_path,
                maxBytes=2_000_000,
                backupCount=5,
                encoding="utf-8",
            )
            metrics_handler.setFormatter(logging.Formatter("%(message)s"))
            metrics_logger.addHandler(metrics_handler)

        trace_logger = logging.getLogger("my_grc.traces")
        trace_logger.setLevel(logging.INFO)
        trace_logger.propagate = False
        if not trace_logger.handlers:
            trace_handler = RotatingFileHandler(
                trace_log_path,
                maxBytes=2_000_000,
                backupCount=5,
                encoding="utf-8",
            )
            trace_handler.setFormatter(logging.Formatter("%(message)s"))
            trace_logger.addHandler(trace_handler)

        _LOGGING_CONFIGURED = True
        app_logger.info(
            "Logging initialized",
            extra={
                "log_dir": str(directory),
                "app_log_file": str(app_log_path),
                "audit_log_file": str(audit_log_path),
                "metrics_log_file": str(metrics_log_path),
                "trace_log_file": str(trace_log_path),
            },
        )


def get_logger(name: str = "") -> logging.Logger:
    configure_logging()
    return logging.getLogger("my_grc" if not name else f"my_grc.{name}")


def audit_event(
    *,
    action: str,
    actor: str = "system",
    target_type: str = "",
    target_id: Any = "",
    status: str = "success",
    details: dict[str, Any] | None = None,
) -> None:
    configure_logging()
    payload = {
        "timestamp": _utc_timestamp(),
        "action": action,
        "actor": actor,
        "target_type": target_type,
        "target_id": target_id,
        "status": status,
        "details": details or {},
    }
    logging.getLogger("my_grc.audit").info(json.dumps(payload, default=str, sort_keys=True))


def metric_event(
    *,
    name: str,
    value: float = 1.0,
    metric_type: str = "counter",
    tags: dict[str, Any] | None = None,
) -> None:
    configure_logging()
    payload = {
        "timestamp": _utc_timestamp(),
        "metric": name,
        "value": value,
        "type": metric_type,
        "tags": tags or {},
    }
    logging.getLogger("my_grc.metrics").info(json.dumps(payload, default=str, sort_keys=True))


def trace_event(
    *,
    trace_id: str,
    span_id: str,
    name: str,
    status: str = "ok",
    parent_span_id: str = "",
    details: dict[str, Any] | None = None,
) -> None:
    configure_logging()
    payload = {
        "timestamp": _utc_timestamp(),
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "name": name,
        "status": status,
        "details": details or {},
    }
    logging.getLogger("my_grc.traces").info(json.dumps(payload, default=str, sort_keys=True))


@contextmanager
def trace_span(name: str, parent_trace_id: str = "", parent_span_id: str = "", details: dict[str, Any] | None = None):
    trace_id = parent_trace_id or uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    trace_event(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        name=name,
        status="started",
        details=details or {},
    )
    try:
        yield {"trace_id": trace_id, "span_id": span_id}
        trace_event(trace_id=trace_id, span_id=span_id, parent_span_id=parent_span_id, name=name, status="completed")
    except Exception as exc:
        trace_event(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            status="error",
            details={"error": str(exc)},
        )
        raise
