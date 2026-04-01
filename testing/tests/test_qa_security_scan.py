from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from testing.qa.security_scan import scan_project


class QaSecurityScanTests(unittest.TestCase):
    def test_scan_project_flags_eval_and_shell_true(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "sample.py").write_text(
                "import subprocess\nvalue = eval('1+1')\nsubprocess.run('echo hi', shell=True)\n",
                encoding="utf-8",
            )
            result = scan_project(root)
        self.assertEqual(result["status"], "fail")
        rule_ids = {item["rule_id"] for item in result["issues"]}
        self.assertIn("AST001", rule_ids)
        self.assertIn("AST003", rule_ids)

    def test_scan_project_passes_clean_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "sample.py").write_text("print('hello')\n", encoding="utf-8")
            result = scan_project(root)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["summary"]["total"], 0)

    def test_scan_project_ignores_bom_and_venv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "clean.py").write_text("\ufeffprint('ok')\n", encoding="utf-8")
            venv_dir = root / "venv" / "lib"
            venv_dir.mkdir(parents=True)
            (venv_dir / "ignored.py").write_text("eval('2+2')\n", encoding="utf-8")
            result = scan_project(root)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["summary"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
