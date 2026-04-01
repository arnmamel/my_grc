from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


@dataclass(slots=True)
class Settings:
    database_url: str = os.getenv("ALA_DATABASE_URL", "sqlite:///audit_manager.db")
    secret_namespace: str = os.getenv("ALA_SECRET_NAMESPACE", "my_grc")
    secret_files_dir: str = os.getenv("ALA_SECRET_FILES_DIR", "data/secrets")
    external_modules_dir: str = os.getenv("ALA_EXTERNAL_MODULES_DIR", "scripts")
    log_dir: str = os.getenv("ALA_LOG_DIR", "logs")
    log_level: str = os.getenv("ALA_LOG_LEVEL", "INFO")
    app_log_file: str = os.getenv("ALA_APP_LOG_FILE", "my_grc.log")
    audit_log_file: str = os.getenv("ALA_AUDIT_LOG_FILE", "my_grc-audit.log")
    metrics_log_file: str = os.getenv("ALA_METRICS_LOG_FILE", "my_grc-metrics.log")
    trace_log_file: str = os.getenv("ALA_TRACE_LOG_FILE", "my_grc-traces.log")
    backup_dir: str = os.getenv("ALA_BACKUP_DIR", "data/backups")
    workspace_auth_required: bool = os.getenv("ALA_WORKSPACE_AUTH_REQUIRED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    workspace_session_timeout_minutes: int = int(os.getenv("ALA_WORKSPACE_SESSION_TIMEOUT_MINUTES", "480"))
    offline_mode: bool = os.getenv("ALA_OFFLINE_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    allow_insecure_env_secrets: bool = os.getenv("ALA_ALLOW_INSECURE_ENV_SECRETS", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    confluence_base_url: str = os.getenv("ALA_CONFLUENCE_BASE_URL", "")
    confluence_space_key: str = os.getenv("ALA_CONFLUENCE_SPACE_KEY", "")
    confluence_parent_page_id: str = os.getenv("ALA_CONFLUENCE_PARENT_PAGE_ID", "")
    confluence_auth_mode: str = os.getenv("ALA_CONFLUENCE_AUTH_MODE", "basic")
    confluence_username: str = os.getenv("ALA_CONFLUENCE_USERNAME", "")
    confluence_api_token: str = os.getenv("ALA_CONFLUENCE_API_TOKEN", "")
    confluence_bearer_token: str = os.getenv("ALA_CONFLUENCE_BEARER_TOKEN", "")
    default_aws_region: str = os.getenv("ALA_DEFAULT_AWS_REGION", "eu-west-1")


settings = Settings()
