from __future__ import annotations

import tempfile
import unittest
import sqlite3
from pathlib import Path

from aws_local_audit.config import settings
from aws_local_audit.services.backup_restore import BackupRestoreService


class BackupRestoreServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "audit.db"
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("CREATE TABLE sample_records (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("INSERT INTO sample_records (value) VALUES ('version-one')")
            connection.commit()
        finally:
            connection.close()
        self.original_database_url = settings.database_url
        self.original_backup_dir = settings.backup_dir
        settings.database_url = f"sqlite:///{self.database_path.as_posix()}"
        settings.backup_dir = "backups"
        self.service = BackupRestoreService(root=self.root)

    def tearDown(self) -> None:
        settings.database_url = self.original_database_url
        settings.backup_dir = self.original_backup_dir
        self.tempdir.cleanup()

    def test_create_and_verify_backup(self) -> None:
        manifest = self.service.create_backup(label="daily")
        verification = self.service.verify_backup(manifest["backup_name"])

        self.assertEqual(verification["status"], "pass")
        self.assertTrue((self.root / "backups" / manifest["backup_name"]).exists())

    def test_restore_backup_recovers_previous_content(self) -> None:
        manifest = self.service.create_backup(label="baseline")
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DELETE FROM sample_records")
            connection.execute("INSERT INTO sample_records (value) VALUES ('version-two')")
            connection.commit()
        finally:
            connection.close()

        report = self.service.restore_backup(manifest["backup_name"])
        connection = sqlite3.connect(self.database_path)
        try:
            restored = connection.execute("SELECT value FROM sample_records ORDER BY id ASC LIMIT 1").fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(restored, "version-one")
        self.assertEqual(report["restored"], manifest["backup_name"])

    def test_recovery_drill_verifies_restored_copy(self) -> None:
        self.service.create_backup(label="baseline")

        report = self.service.run_restore_drill()

        self.assertEqual(report["status"], "pass")
        self.assertIn("sample_records", report["tables"])
        self.assertGreaterEqual(report["table_count"], 1)


if __name__ == "__main__":
    unittest.main()
