from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class CliCommandTests(unittest.TestCase):
    def test_assessment_list_command_handles_empty_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "cli-test.db"
            env = os.environ.copy()
            env["ALA_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
            env["PYTHONPATH"] = str(Path.cwd() / "src")

            init_result = subprocess.run(
                [sys.executable, "src/aws_local_audit/cli.py", "init-db"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stdout + init_result.stderr)

            list_result = subprocess.run(
                [sys.executable, "src/aws_local_audit/cli.py", "assessment", "list"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(list_result.returncode, 0, msg=list_result.stdout + list_result.stderr)
            self.assertIn("Assessment Runs", list_result.stdout)

            recovery_result = subprocess.run(
                [sys.executable, "src/aws_local_audit/cli.py", "platform", "recovery-drill"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(recovery_result.returncode, 0, msg=recovery_result.stdout + recovery_result.stderr)
            self.assertIn("Recovery drill", recovery_result.stdout)

            privacy_result = subprocess.run(
                [sys.executable, "src/aws_local_audit/cli.py", "privacy", "report"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(privacy_result.returncode, 0, msg=privacy_result.stdout + privacy_result.stderr)
            self.assertIn("Privacy lifecycle report", privacy_result.stdout)


if __name__ == "__main__":
    unittest.main()
