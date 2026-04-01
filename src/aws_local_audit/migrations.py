from __future__ import annotations

from pathlib import Path

try:
    from alembic import command
    from alembic.config import Config
except ImportError:  # pragma: no cover - dependency-managed at install time
    command = None
    Config = None

from aws_local_audit.config import settings
from aws_local_audit.logging_utils import get_logger

LOGGER = get_logger("migrations")


def migrations_available() -> bool:
    root = project_root()
    return command is not None and (root / "alembic.ini").exists() and (root / "alembic").exists()


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def upgrade_to_head() -> bool:
    if not migrations_available():
        LOGGER.info("Alembic migrations are not available. Falling back to metadata bootstrap if needed.")
        return False
    root = project_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
    LOGGER.info("Alembic upgrade completed to head.")
    return True
