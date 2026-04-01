from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class WorkspaceUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(__file__).resolve().parents[2]
        self.db_path = Path(self.tempdir.name) / "workspace-ui.db"
        self.log_dir = Path(self.tempdir.name) / "logs"
        self.backup_dir = Path(self.tempdir.name) / "backups"
        self.secret_dir = Path(self.tempdir.name) / "secrets"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.secret_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_workspace_bootstrap_auth_flow_completes_without_exceptions(self) -> None:
        app = AppTest.from_string(self._workspace_wrapper(auth_required=True), default_timeout=60)

        app.run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertGreaterEqual(len(app.text_input), 5)

        app.text_input[0].set_value("grc.lead")
        app.text_input[1].set_value("GRC Lead")
        app.text_input[2].set_value("lead@example.com")
        app.text_input[3].set_value("MyStr0ng!Password")
        app.text_input[4].set_value("MyStr0ng!Password")
        app.button[0].click()
        app.run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["workspace_principal_key"], "grc.lead")

    def test_workspace_renders_assistant_center_when_auth_is_disabled(self) -> None:
        app = AppTest.from_string(self._workspace_wrapper(auth_required=False), default_timeout=60)

        app.run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        markdown_values = [element.value for element in app.markdown]
        self.assertTrue(any("Assistant Center" in value or "Workspace Home" in value for value in markdown_values))

    def _workspace_wrapper(self, *, auth_required: bool) -> str:
        root = self.root.as_posix()
        db_url = f"sqlite:///{self.db_path.as_posix()}"
        log_dir = self.log_dir.as_posix()
        backup_dir = self.backup_dir.as_posix()
        secret_dir = self.secret_dir.as_posix()
        auth_literal = "True" if auth_required else "False"
        return f"""
import logging
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(r\"{root}\")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / \"src\"))
sys.path.insert(0, str(ROOT / \"workspace\"))

from aws_local_audit.config import settings
settings.database_url = r\"{db_url}\"
settings.log_dir = r\"{log_dir}\"
settings.backup_dir = r\"{backup_dir}\"
settings.secret_files_dir = r\"{secret_dir}\"
settings.workspace_auth_required = {auth_literal}

import aws_local_audit.logging_utils as logging_utils
for name in [\"my_grc\", \"my_grc.audit\", \"my_grc.metrics\", \"my_grc.traces\"]:
    logger = logging.getLogger(name)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
logging_utils._LOGGING_CONFIGURED = False

runpy.run_path(str(ROOT / \"workspace\" / \"app.py\"), run_name=\"__main__\")
"""


if __name__ == "__main__":
    unittest.main()
