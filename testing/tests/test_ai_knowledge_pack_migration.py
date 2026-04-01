from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class AIKnowledgePackMigrationTests(unittest.TestCase):
    def _migration_env(self, db_path: Path) -> dict[str, str]:
        env = os.environ.copy()
        env["ALA_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
        env["PYTHONPATH"] = str(ROOT / "src")
        return env

    def _upgrade(self, db_path: Path, revision: str) -> subprocess.CompletedProcess[str]:
        code = textwrap.dedent(
            f"""
            from alembic import command
            from alembic.config import Config
            from pathlib import Path

            root = Path.cwd()
            config = Config(str(root / "alembic.ini"))
            config.set_main_option("script_location", str(root / "alembic"))
            command.upgrade(config, "{revision}")
            """
        )
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=self._migration_env(db_path),
            capture_output=True,
            text=True,
            check=False,
        )

    def _table_names(self, connection: sqlite3.Connection) -> set[str]:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        return {row[0] for row in rows}

    def _column_names(self, connection: sqlite3.Connection, table_name: str) -> set[str]:
        rows = connection.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        return {row[1] for row in rows}

    def _index_names(self, connection: sqlite3.Connection, table_name: str) -> set[str]:
        rows = connection.execute(f"PRAGMA index_list('{table_name}')").fetchall()
        return {row[1] for row in rows}

    def test_sqlite_upgrade_reaches_head_from_access_governance_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "migration.db"

            base_upgrade = self._upgrade(db_path, "20260317_0004")
            self.assertEqual(base_upgrade.returncode, 0, msg=base_upgrade.stdout + base_upgrade.stderr)

            head_upgrade = self._upgrade(db_path, "head")
            self.assertEqual(head_upgrade.returncode, 0, msg=head_upgrade.stdout + head_upgrade.stderr)

            with sqlite3.connect(db_path) as connection:
                tables = self._table_names(connection)
                self.assertIn("ai_knowledge_packs", tables)
                self.assertIn("ai_knowledge_pack_versions", tables)
                self.assertIn("ai_knowledge_pack_tasks", tables)
                self.assertIn("ai_knowledge_pack_references", tables)
                self.assertIn("ai_knowledge_pack_eval_cases", tables)
                self.assertTrue(
                    {"knowledge_pack_version_id", "task_key", "citations_json"}.issubset(
                        self._column_names(connection, "ai_suggestions")
                    )
                )

    def test_sqlite_upgrade_recovers_from_partial_ai_suggestions_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "migration.db"

            base_upgrade = self._upgrade(db_path, "20260317_0004")
            self.assertEqual(base_upgrade.returncode, 0, msg=base_upgrade.stdout + base_upgrade.stderr)

            with sqlite3.connect(db_path) as connection:
                columns = self._column_names(connection, "ai_suggestions")
                if "knowledge_pack_version_id" not in columns:
                    connection.execute("ALTER TABLE ai_suggestions ADD COLUMN knowledge_pack_version_id INTEGER")
                indexes = self._index_names(connection, "ai_suggestions")
                if "ix_ai_suggestions_knowledge_pack_version_id" not in indexes:
                    connection.execute(
                        "CREATE INDEX ix_ai_suggestions_knowledge_pack_version_id ON ai_suggestions (knowledge_pack_version_id)"
                    )
                connection.commit()

            head_upgrade = self._upgrade(db_path, "head")
            self.assertEqual(head_upgrade.returncode, 0, msg=head_upgrade.stdout + head_upgrade.stderr)

            with sqlite3.connect(db_path) as connection:
                columns = self._column_names(connection, "ai_suggestions")
                indexes = self._index_names(connection, "ai_suggestions")
                self.assertIn("knowledge_pack_version_id", columns)
                self.assertIn("task_key", columns)
                self.assertIn("citations_json", columns)
                self.assertIn("ix_ai_suggestions_knowledge_pack_version_id", indexes)


if __name__ == "__main__":
    unittest.main()
