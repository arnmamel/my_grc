from __future__ import annotations

from contextlib import contextmanager
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from aws_local_audit.config import settings
from aws_local_audit.logging_utils import get_logger
from aws_local_audit.migrations import upgrade_to_head


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
LOGGER = get_logger("db")
_INIT_LOCK = Lock()
_INITIALIZED = False


def init_database() -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    with _INIT_LOCK:
        if _INITIALIZED:
            return
        migrated = upgrade_to_head()
        if not migrated:
            Base.metadata.create_all(bind=engine, checkfirst=True)
            LOGGER.info("Database initialized via SQLAlchemy metadata bootstrap.")
        else:
            LOGGER.info("Database initialized via Alembic migrations.")
        from aws_local_audit.services.access_control import AccessControlService
        from aws_local_audit.services.platform_foundation import FeatureFlagService

        session = SessionLocal()
        try:
            FeatureFlagService(session).seed_defaults()
            AccessControlService(session).seed_default_roles()
            session.commit()
        except Exception:
            session.rollback()
            LOGGER.exception("Platform bootstrap failed during database initialization.")
        finally:
            session.close()
        _INITIALIZED = True


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        LOGGER.exception("Database session rolled back because an exception occurred.")
        raise
    finally:
        session.close()
