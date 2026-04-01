from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url

from aws_local_audit.config import settings
from aws_local_audit.logging_utils import audit_event, metric_event
from aws_local_audit.services.validation import validate_backup_label


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class BackupRestoreService:
    def __init__(self, *, root: Path | None = None):
        self.root = root or Path(__file__).resolve().parents[3]

    def backup_directory(self) -> Path:
        directory = Path(settings.backup_dir)
        if not directory.is_absolute():
            directory = self.root / directory
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def database_path(self) -> Path:
        url = make_url(settings.database_url)
        if url.drivername != "sqlite":
            raise ValueError("Backup and restore support currently targets SQLite databases only.")
        if not url.database:
            raise ValueError("SQLite database path is not configured.")
        return Path(url.database)

    def create_backup(self, *, label: str = "manual", actor: str = "platform_cli") -> dict:
        normalized_label = validate_backup_label(label)
        source = self.database_path()
        if not source.exists():
            raise FileNotFoundError(f"Database file not found: {source}")
        backup_dir = self.backup_directory()
        backup_name = f"{_utc_timestamp()}_{normalized_label}.sqlite3"
        backup_path = backup_dir / backup_name
        shutil.copy2(source, backup_path)
        checksum = self._sha256(backup_path)
        manifest = {
            "backup_name": backup_name,
            "label": normalized_label,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_database": str(source),
            "backup_path": str(backup_path),
            "sha256": checksum,
            "size_bytes": backup_path.stat().st_size,
        }
        manifest_path = backup_path.with_suffix(".json")
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        audit_event(
            action="database_backup_created",
            actor=actor,
            target_type="database_backup",
            target_id=backup_name,
            status="success",
            details={"backup_path": str(backup_path), "sha256": checksum},
        )
        metric_event(name="database_backup_created_total", tags={"label": normalized_label})
        return manifest

    def list_backups(self) -> list[dict]:
        backup_dir = self.backup_directory()
        items = []
        for manifest_path in sorted(backup_dir.glob("*.json"), reverse=True):
            try:
                items.append(json.loads(manifest_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return items

    def verify_backup(self, backup_name: str) -> dict:
        manifest = self._manifest(backup_name)
        backup_path = Path(manifest["backup_path"])
        if not backup_path.exists():
            return {"status": "error", "detail": f"Backup file is missing: {backup_path}"}
        actual = self._sha256(backup_path)
        if actual != manifest["sha256"]:
            return {"status": "error", "detail": "Backup checksum does not match the manifest.", "backup_name": backup_name}
        return {"status": "pass", "detail": "Backup checksum matches the manifest.", "backup_name": backup_name}

    def restore_backup(self, backup_name: str, *, actor: str = "platform_cli") -> dict:
        manifest = self._manifest(backup_name)
        verification = self.verify_backup(backup_name)
        if verification["status"] != "pass":
            raise ValueError(verification["detail"])
        source = self.database_path()
        current_backup = self.create_backup(label="pre-restore", actor=actor)
        backup_path = Path(manifest["backup_path"])
        shutil.copy2(backup_path, source)
        audit_event(
            action="database_backup_restored",
            actor=actor,
            target_type="database_backup",
            target_id=backup_name,
            status="success",
            details={"restored_from": str(backup_path), "pre_restore_backup": current_backup["backup_name"]},
        )
        metric_event(name="database_restore_total", tags={"backup_name": backup_name})
        return {"restored": backup_name, "pre_restore_backup": current_backup["backup_name"], "database_path": str(source)}

    def run_restore_drill(self, *, actor: str = "platform_cli") -> dict:
        manifest = self.create_backup(label="recovery-drill", actor=actor)
        verification = self.verify_backup(manifest["backup_name"])
        if verification["status"] != "pass":
            raise ValueError(verification["detail"])
        drill_dir = self.backup_directory() / "drills"
        drill_dir.mkdir(parents=True, exist_ok=True)
        source_path = Path(manifest["backup_path"])
        drill_path = drill_dir / source_path.name
        shutil.copy2(source_path, drill_path)
        engine = create_engine(f"sqlite:///{drill_path.as_posix()}", future=True)
        try:
            inspector = inspect(engine)
            tables = sorted(inspector.get_table_names())
        finally:
            engine.dispose()
            drill_path.unlink(missing_ok=True)
        audit_event(
            action="database_recovery_drill",
            actor=actor,
            target_type="database_backup",
            target_id=manifest["backup_name"],
            status="success",
            details={"verified_tables": tables[:25], "table_count": len(tables)},
        )
        metric_event(name="database_recovery_drill_total", tags={"backup_name": manifest["backup_name"]})
        return {
            "status": "pass",
            "backup_name": manifest["backup_name"],
            "table_count": len(tables),
            "tables": tables,
        }

    def health_summary(self) -> dict:
        backups = self.list_backups()
        if not backups:
            return {"status": "warn", "detail": "No database backups are registered yet."}
        latest = backups[0]
        verification = self.verify_backup(latest["backup_name"])
        if verification["status"] != "pass":
            return {"status": "error", "detail": verification["detail"]}
        return {
            "status": "pass",
            "detail": f"{len(backups)} backup(s) available. Latest verified backup: {latest['backup_name']}.",
        }

    def _manifest(self, backup_name: str) -> dict:
        manifest_path = self.backup_directory() / f"{backup_name.removesuffix('.sqlite3')}.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Backup manifest not found for `{backup_name}`.")
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
