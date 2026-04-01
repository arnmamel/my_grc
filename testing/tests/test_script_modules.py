from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.models import (
    AssessmentScriptRun,
    Control,
    EvidenceCollectionPlan,
    Framework,
    Organization,
    OrganizationFrameworkBinding,
)
from aws_local_audit.services.script_modules import ScriptModuleService


class ScriptModuleServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

        self.organization = Organization(code="ACME", name="Acme")
        self.framework = Framework(code="ISO27001_2022", name="ISO 27001", version="2022")
        self.control = Control(
            framework=self.framework,
            control_id="A.5.1",
            title="Policies",
            description="Policies are defined and approved.",
            evidence_query="manual_review",
        )
        self.binding = OrganizationFrameworkBinding(
            organization=self.organization,
            framework=self.framework,
            binding_code="ACME_ISO27001",
            name="Acme ISO 27001",
            aws_profile="prod-sso",
            aws_region="eu-west-1",
        )
        self.session.add_all([self.organization, self.framework, self.control, self.binding])
        self.session.flush()
        self.plan = EvidenceCollectionPlan(
            plan_code="SCRIPT_PLAN_A_5_1",
            name="Scripted policy evidence",
            framework_id=self.framework.id,
            control_id=self.control.id,
            scope_type="binding",
            execution_mode="autonomous",
            collector_key="script:IDENTITY_ACCESS",
            evidence_type="artifact_bundle",
            instructions="Run the imported external script.",
            lifecycle_status="ready",
        )
        self.session.add(self.plan)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()

    def test_script_module_executes_and_records_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            script_path = temp_path / "collector.py"
            script_path.write_text(
                "import argparse, json\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--context-file')\n"
                "args = parser.parse_args()\n"
                "context = json.loads(Path(args.context_file).read_text(encoding='utf-8'))\n"
                "artifact = Path(args.context_file).with_suffix('.txt')\n"
                "artifact.write_text(context['control_id'], encoding='utf-8')\n"
                "print(json.dumps({'status': 'pass', 'summary': f\"Validated {context['control_id']}\", "
                "'payload': {'framework': context['framework_code']}, "
                "'artifacts': [{'path': str(artifact), 'content_type': 'text/plain'}]}))\n",
                encoding="utf-8",
            )

            service = ScriptModuleService(self.session)
            service.register_module(
                module_code="IDENTITY_ACCESS",
                name="Identity Access",
                entrypoint_ref="collector.py",
                entrypoint_type="python_file",
                interpreter=sys.executable,
                working_directory=temp_dir,
                context_argument_name="--context-file",
            )
            service.upsert_binding(
                module_code="IDENTITY_ACCESS",
                name="Identity Access for ACME ISO",
                framework_binding_code="ACME_ISO27001",
                framework_code="ISO27001_2022",
                control_id="A.5.1",
                evidence_plan_code="SCRIPT_PLAN_A_5_1",
            )

            result = service.execute_for_evidence(
                "script:IDENTITY_ACCESS",
                framework=self.framework,
                control=self.control,
                plan=self.plan,
                collection_targets=[
                    {
                        "target_code": "PRIMARY",
                        "name": "Primary",
                        "aws_profile": "prod-sso",
                        "aws_account_id": "111111111111",
                        "role_name": "AuditRole",
                        "regions": ["eu-west-1"],
                    }
                ],
                organization_id=self.organization.id,
                framework_binding_id=self.binding.id,
            )

            self.assertEqual(result["status"], "pass")
            self.assertEqual(len(result["artifacts"]), 1)
            self.assertTrue(Path(result["artifacts"][0]["path"]).exists())

            runs = self.session.scalars(select(AssessmentScriptRun)).all()
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].status, "completed")
            self.assertIn("Validated A.5.1", runs[0].summary)


if __name__ == "__main__":
    unittest.main()
