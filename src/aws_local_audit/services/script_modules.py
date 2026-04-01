from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import yaml
from sqlalchemy import select

from aws_local_audit.config import settings
from aws_local_audit.models import (
    AssessmentScriptBinding,
    AssessmentScriptModule,
    AssessmentScriptRun,
    Control,
    EvidenceCollectionPlan,
    Framework,
    Organization,
    OrganizationFrameworkBinding,
    Product,
    ProductFlavor,
    UnifiedControl,
)
from aws_local_audit.services.lifecycle import LifecycleService


def _normalize_code(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value.strip().upper())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


class ScriptModuleService:
    def __init__(self, session):
        self.session = session
        self.lifecycle = LifecycleService(session)
        self.root = Path(__file__).resolve().parents[3]

    def register_module(
        self,
        *,
        module_code: str,
        name: str,
        entrypoint_ref: str,
        description: str = "",
        entrypoint_type: str = "python_file",
        interpreter: str = "",
        working_directory: str = "",
        context_argument_name: str = "",
        default_arguments_json: str = "[]",
        manifest_path: str = "",
        default_config_path: str = "",
        output_contract: str = "json_stdout",
        supported_actions_json: str = '["evidence_collection"]',
        supported_scopes_json: str = '["binding","product","product_flavor","control"]',
        timeout_seconds: int = 900,
        lifecycle_status: str = "active",
        notes: str = "",
    ) -> AssessmentScriptModule:
        resolved_code = _normalize_code(module_code)
        module = self.session.scalar(
            select(AssessmentScriptModule).where(AssessmentScriptModule.module_code == resolved_code)
        )
        created = module is None
        if module is None:
            module = AssessmentScriptModule(module_code=resolved_code, name=name)
            self.session.add(module)
        previous_state = module.lifecycle_status if not created else ""
        module.name = name
        module.description = description
        module.entrypoint_type = entrypoint_type
        module.entrypoint_ref = entrypoint_ref
        module.interpreter = interpreter
        module.working_directory = working_directory
        module.context_argument_name = context_argument_name
        module.default_arguments_json = default_arguments_json
        module.manifest_path = manifest_path
        module.default_config_path = default_config_path
        module.output_contract = output_contract
        module.supported_actions_json = supported_actions_json
        module.supported_scopes_json = supported_scopes_json
        module.timeout_seconds = timeout_seconds
        module.lifecycle_status = lifecycle_status
        module.notes = notes
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="assessment_script_module",
            entity_id=module.id,
            lifecycle_name="assurance_lifecycle",
            from_state=previous_state,
            to_state=module.lifecycle_status,
            actor="script_module_service",
            payload={"module_code": module.module_code, "entrypoint_ref": module.entrypoint_ref},
        )
        return module

    def register_module_from_manifest(self, manifest_path: str) -> AssessmentScriptModule:
        path = Path(manifest_path)
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError("The selected manifest must contain a top-level mapping/object.")
        module_code = str(payload.get("module_code", "")).strip()
        name = str(payload.get("name", "")).strip()
        entrypoint_ref = str(payload.get("entrypoint_ref", "")).strip()
        if not module_code or not name or not entrypoint_ref:
            raise ValueError("The manifest must define module_code, name, and entrypoint_ref.")
        return self.register_module(
            module_code=module_code,
            name=name,
            entrypoint_ref=entrypoint_ref,
            description=str(payload.get("description", "")),
            entrypoint_type=str(payload.get("entrypoint_type", "python_file")),
            interpreter=str(payload.get("interpreter", "")),
            working_directory=str(payload.get("working_directory", "")),
            context_argument_name=str(payload.get("context_argument_name", "")),
            default_arguments_json=json.dumps(payload.get("default_arguments", []), indent=2),
            manifest_path=str(path),
            default_config_path=str(payload.get("default_config_path", "")),
            output_contract=str(payload.get("output_contract", "json_stdout")),
            supported_actions_json=json.dumps(payload.get("supported_actions", ["evidence_collection"]), indent=2),
            supported_scopes_json=json.dumps(
                payload.get("supported_scopes", ["binding", "product", "product_flavor", "control"]),
                indent=2,
            ),
            timeout_seconds=int(payload.get("timeout_seconds", 900)),
            lifecycle_status=str(payload.get("lifecycle_status", "active")),
            notes=str(payload.get("notes", "")),
        )

    def list_modules(self) -> list[AssessmentScriptModule]:
        return list(self.session.scalars(select(AssessmentScriptModule).order_by(AssessmentScriptModule.module_code)))

    def upsert_binding(
        self,
        *,
        module_code: str,
        name: str,
        binding_code: str | None = None,
        action_type: str = "evidence_collection",
        organization_code: str | None = None,
        framework_binding_code: str | None = None,
        product_code: str | None = None,
        product_flavor_code: str | None = None,
        unified_control_code: str | None = None,
        framework_code: str | None = None,
        control_id: str | None = None,
        evidence_plan_code: str | None = None,
        config_path: str = "",
        config_json: str = "{}",
        arguments_json: str = "[]",
        expected_outputs_json: str = "[]",
        lifecycle_status: str = "active",
        notes: str = "",
    ) -> AssessmentScriptBinding:
        module = self._module_by_code(module_code)
        organization = self._organization_by_code(organization_code) if organization_code else None
        framework_binding = self._framework_binding_by_code(framework_binding_code) if framework_binding_code else None
        product = self._product_by_code(organization.id if organization else None, product_code) if product_code else None
        flavor = (
            self._product_flavor_by_code(product.id if product else None, product_flavor_code)
            if product_flavor_code
            else None
        )
        unified_control = self._unified_control_by_code(unified_control_code) if unified_control_code else None
        framework = self._framework_by_code(framework_code) if framework_code else None
        control = self._control_by_key(framework.id if framework else None, control_id) if control_id else None
        evidence_plan = self._plan_by_code(evidence_plan_code) if evidence_plan_code else None
        resolved_code = _normalize_code(
            binding_code
            or "_".join(
                filter(
                    None,
                    [
                        module.module_code,
                        framework_binding.binding_code if framework_binding else "",
                        product.code if product else "",
                        flavor.code if flavor else "",
                        control.control_id if control else "",
                    ],
                )
            )
        )
        binding = self.session.scalar(
            select(AssessmentScriptBinding).where(AssessmentScriptBinding.binding_code == resolved_code)
        )
        created = binding is None
        previous_state = binding.lifecycle_status if binding else ""
        if binding is None:
            binding = AssessmentScriptBinding(module_id=module.id, binding_code=resolved_code, name=name)
            self.session.add(binding)
        binding.name = name
        binding.module_id = module.id
        binding.organization_id = organization.id if organization else None
        binding.framework_binding_id = framework_binding.id if framework_binding else None
        binding.product_id = product.id if product else None
        binding.product_flavor_id = flavor.id if flavor else None
        binding.unified_control_id = unified_control.id if unified_control else None
        binding.framework_id = framework.id if framework else None
        binding.control_id = control.id if control else None
        binding.evidence_plan_id = evidence_plan.id if evidence_plan else None
        binding.action_type = action_type
        binding.config_path = config_path
        binding.config_json = config_json
        binding.arguments_json = arguments_json
        binding.expected_outputs_json = expected_outputs_json
        binding.lifecycle_status = lifecycle_status
        binding.notes = notes
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="assessment_script_binding",
            entity_id=binding.id,
            lifecycle_name="assurance_lifecycle",
            from_state=previous_state,
            to_state=binding.lifecycle_status,
            actor="script_module_service",
            payload={"binding_code": binding.binding_code, "module_code": module.module_code, "created": created},
        )
        return binding

    def list_bindings(self, module_code: str | None = None) -> list[AssessmentScriptBinding]:
        query = select(AssessmentScriptBinding).order_by(AssessmentScriptBinding.binding_code)
        if module_code:
            module = self._module_by_code(module_code)
            query = query.where(AssessmentScriptBinding.module_id == module.id)
        return list(self.session.scalars(query))

    def collector_ready(
        self,
        collector_key: str,
        *,
        organization_id: int | None = None,
        framework_binding_id: int | None = None,
        product_id: int | None = None,
        product_flavor_id: int | None = None,
        framework_id: int | None = None,
        control_id: int | None = None,
        unified_control_id: int | None = None,
        evidence_plan_id: int | None = None,
    ) -> dict:
        module, binding = self._resolve_module_and_binding(
            collector_key=collector_key,
            organization_id=organization_id,
            framework_binding_id=framework_binding_id,
            product_id=product_id,
            product_flavor_id=product_flavor_id,
            framework_id=framework_id,
            control_id=control_id,
            unified_control_id=unified_control_id,
            evidence_plan_id=evidence_plan_id,
        )
        return {
            "ready": self._entrypoint_ready(module)
            and module.lifecycle_status == "active"
            and (binding is None or binding.lifecycle_status == "active"),
            "module_code": module.module_code,
            "binding_code": binding.binding_code if binding else "",
            "entrypoint_exists": self._entrypoint_ready(module),
            "entrypoint": self._entrypoint_label(module),
        }

    def execute_for_evidence(
        self,
        collector_key: str,
        *,
        framework: Framework,
        control: Control,
        plan: EvidenceCollectionPlan,
        collection_targets: list[dict],
        organization_id: int | None = None,
        framework_binding_id: int | None = None,
        product_id: int | None = None,
        product_flavor_id: int | None = None,
        unified_control_id: int | None = None,
    ) -> dict:
        module, binding = self._resolve_module_and_binding(
            collector_key=collector_key,
            organization_id=organization_id,
            framework_binding_id=framework_binding_id,
            product_id=product_id,
            product_flavor_id=product_flavor_id,
            framework_id=framework.id,
            control_id=control.id,
            unified_control_id=unified_control_id,
            evidence_plan_id=plan.id,
        )
        context = self._build_context(
            module=module,
            binding=binding,
            framework=framework,
            control=control,
            plan=plan,
            collection_targets=collection_targets,
            organization_id=organization_id,
            framework_binding_id=framework_binding_id,
            product_id=product_id,
            product_flavor_id=product_flavor_id,
            unified_control_id=unified_control_id,
        )
        run = AssessmentScriptRun(
            module_id=module.id,
            binding_id=binding.id if binding else None,
            framework_id=framework.id,
            control_id=control.id,
            status="running",
            summary=f"Executing {module.module_code}",
            started_at=datetime.utcnow(),
        )
        self.session.add(run)
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="assessment_script_run",
            entity_id=run.id,
            lifecycle_name="assurance_lifecycle",
            to_state=run.status,
            actor="script_module_service",
            payload={"module_code": module.module_code, "binding_code": binding.binding_code if binding else ""},
        )

        command_line: list[str] = []
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as handle:
                json.dump(context, handle, indent=2)
                context_file = handle.name
            command_line = self._build_command(
                module=module,
                binding=binding,
                context=context,
                context_file=context_file,
            )
            completed = subprocess.run(
                command_line,
                cwd=str(self._working_directory(module)),
                capture_output=True,
                text=True,
                timeout=module.timeout_seconds,
                check=False,
            )
            payload = self._parse_output(module.output_contract, completed.stdout, completed.stderr)
            status = payload.get("status") or ("pass" if completed.returncode == 0 else "error")
            summary = payload.get("summary") or (
                f"{module.module_code} exited with code {completed.returncode}"
                if completed.returncode
                else f"{module.module_code} completed."
            )
            artifacts = self._normalize_artifacts(payload.pop("artifacts", []), module)
            run.status = "completed" if completed.returncode == 0 else "error"
            run.summary = summary
            run.exit_code = completed.returncode
            run.command_line = " ".join(command_line)
            run.result_json = json.dumps(
                {
                    "status": status,
                    "summary": summary,
                    "artifact_count": len(artifacts),
                    "stdout_present": bool(completed.stdout.strip()),
                    "stderr_excerpt": completed.stderr[:500],
                },
                indent=2,
            )
            run.finished_at = datetime.utcnow()
            self.lifecycle.record_event(
                entity_type="assessment_script_run",
                entity_id=run.id,
                lifecycle_name="assurance_lifecycle",
                from_state="running",
                to_state=run.status,
                actor="script_module_service",
                payload={"exit_code": completed.returncode, "module_code": module.module_code},
            )
            return {
                "status": status,
                "summary": summary,
                "payload": {
                    "module_code": module.module_code,
                    "binding_code": binding.binding_code if binding else "",
                    "run_id": run.id,
                    "result": payload,
                    "command_line": run.command_line,
                },
                "artifacts": artifacts,
            }
        except Exception as exc:
            run.status = "error"
            run.summary = str(exc)
            run.command_line = " ".join(command_line)
            run.result_json = json.dumps({"error": str(exc)}, indent=2)
            run.finished_at = datetime.utcnow()
            self.lifecycle.record_event(
                entity_type="assessment_script_run",
                entity_id=run.id,
                lifecycle_name="assurance_lifecycle",
                from_state="running",
                to_state=run.status,
                actor="script_module_service",
                payload={"module_code": module.module_code, "error": str(exc)},
            )
            return {
                "status": "error",
                "summary": str(exc),
                "payload": {
                    "module_code": module.module_code,
                    "binding_code": binding.binding_code if binding else "",
                    "run_id": run.id,
                    "error": str(exc),
                },
                "artifacts": [],
            }
        finally:
            if "context_file" in locals():
                Path(context_file).unlink(missing_ok=True)

    def _resolve_module_and_binding(
        self,
        *,
        collector_key: str,
        organization_id: int | None,
        framework_binding_id: int | None,
        product_id: int | None,
        product_flavor_id: int | None,
        framework_id: int | None,
        control_id: int | None,
        unified_control_id: int | None,
        evidence_plan_id: int | None,
    ) -> tuple[AssessmentScriptModule, AssessmentScriptBinding | None]:
        if collector_key.startswith("script-binding:"):
            binding_code = collector_key.split(":", 1)[1].strip()
            binding = self.session.scalar(
                select(AssessmentScriptBinding).where(AssessmentScriptBinding.binding_code == _normalize_code(binding_code))
            )
            if binding is None:
                raise ValueError(f"Script binding not found: {binding_code}")
            return binding.module, binding
        if not collector_key.startswith("script:"):
            raise ValueError(f"Unsupported script collector key: {collector_key}")
        module_code = collector_key.split(":", 1)[1].strip()
        module = self._module_by_code(module_code)
        binding = self._best_binding_for_scope(
            module_id=module.id,
            organization_id=organization_id,
            framework_binding_id=framework_binding_id,
            product_id=product_id,
            product_flavor_id=product_flavor_id,
            framework_id=framework_id,
            control_id=control_id,
            unified_control_id=unified_control_id,
            evidence_plan_id=evidence_plan_id,
        )
        return module, binding

    def _best_binding_for_scope(
        self,
        *,
        module_id: int,
        organization_id: int | None,
        framework_binding_id: int | None,
        product_id: int | None,
        product_flavor_id: int | None,
        framework_id: int | None,
        control_id: int | None,
        unified_control_id: int | None,
        evidence_plan_id: int | None,
    ) -> AssessmentScriptBinding | None:
        candidates = self.session.scalars(
            select(AssessmentScriptBinding).where(AssessmentScriptBinding.module_id == module_id)
        ).all()

        def _matches(binding: AssessmentScriptBinding) -> bool:
            if binding.lifecycle_status != "active":
                return False
            checks = [
                (binding.organization_id, organization_id),
                (binding.framework_binding_id, framework_binding_id),
                (binding.product_id, product_id),
                (binding.product_flavor_id, product_flavor_id),
                (binding.framework_id, framework_id),
                (binding.control_id, control_id),
                (binding.unified_control_id, unified_control_id),
                (binding.evidence_plan_id, evidence_plan_id),
            ]
            return all(expected is None or expected == actual for expected, actual in checks)

        scoped = [item for item in candidates if _matches(item)]
        if not scoped:
            return None
        return max(
            scoped,
            key=lambda item: sum(
                1
                for value in [
                    item.organization_id,
                    item.framework_binding_id,
                    item.product_id,
                    item.product_flavor_id,
                    item.framework_id,
                    item.control_id,
                    item.unified_control_id,
                    item.evidence_plan_id,
                ]
                if value is not None
            ),
        )

    def _build_context(
        self,
        *,
        module: AssessmentScriptModule,
        binding: AssessmentScriptBinding | None,
        framework: Framework,
        control: Control,
        plan: EvidenceCollectionPlan,
        collection_targets: list[dict],
        organization_id: int | None,
        framework_binding_id: int | None,
        product_id: int | None,
        product_flavor_id: int | None,
        unified_control_id: int | None,
    ) -> dict:
        organization = self.session.get(Organization, organization_id) if organization_id else None
        framework_binding = (
            self.session.get(OrganizationFrameworkBinding, framework_binding_id) if framework_binding_id else None
        )
        product = self.session.get(Product, product_id) if product_id else None
        flavor = self.session.get(ProductFlavor, product_flavor_id) if product_flavor_id else None
        unified_control = self.session.get(UnifiedControl, unified_control_id) if unified_control_id else None
        config_path = binding.config_path if binding and binding.config_path else module.default_config_path
        return {
            "module_code": module.module_code,
            "module_name": module.name,
            "binding_code": binding.binding_code if binding else "",
            "organization_code": organization.code if organization else "",
            "framework_binding_code": framework_binding.binding_code if framework_binding else "",
            "framework_code": framework.code,
            "control_id": control.control_id,
            "control_title": control.title,
            "product_code": product.code if product else "",
            "product_flavor_code": flavor.code if flavor else "",
            "unified_control_code": unified_control.code if unified_control else "",
            "evidence_plan": {
                "plan_code": plan.plan_code,
                "name": plan.name,
                "scope_type": plan.scope_type,
                "execution_mode": plan.execution_mode,
                "instructions": plan.instructions,
            },
            "config_path": str(self._resolve_path(config_path, module.working_directory)) if config_path else "",
            "config": json.loads(binding.config_json) if binding and binding.config_json else {},
            "collection_targets": collection_targets,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _build_command(
        self,
        *,
        module: AssessmentScriptModule,
        binding: AssessmentScriptBinding | None,
        context: dict,
        context_file: str,
    ) -> list[str]:
        if module.entrypoint_type == "python_file":
            entrypoint = self._resolve_path(module.entrypoint_ref, module.working_directory)
            if not entrypoint.exists():
                raise ValueError(f"Script entrypoint not found: {entrypoint}")
            interpreter = module.interpreter or sys.executable or "python3"
            command = [interpreter, str(entrypoint)]
        elif module.entrypoint_type == "module":
            interpreter = module.interpreter or sys.executable or "python3"
            command = [interpreter, "-m", module.entrypoint_ref]
        elif module.entrypoint_type == "command":
            entrypoint = self._resolve_path(module.entrypoint_ref, module.working_directory)
            if not entrypoint.exists():
                raise ValueError(f"Script entrypoint not found: {entrypoint}")
            command = [str(entrypoint)]
        else:
            raise ValueError(f"Unsupported script entrypoint_type: {module.entrypoint_type}")

        placeholders = {
            "context_file": context_file,
            "config_path": context.get("config_path", ""),
            "framework_code": context.get("framework_code", ""),
            "control_id": context.get("control_id", ""),
            "product_code": context.get("product_code", ""),
            "product_flavor_code": context.get("product_flavor_code", ""),
            "organization_code": context.get("organization_code", ""),
            "framework_binding_code": context.get("framework_binding_code", ""),
            "binding_code": context.get("binding_code", ""),
        }
        arguments = self._json_list(module.default_arguments_json)
        if binding:
            arguments.extend(self._json_list(binding.arguments_json))
        command.extend([self._apply_placeholders(str(item), placeholders) for item in arguments])
        if module.context_argument_name:
            command.extend([module.context_argument_name, context_file])
        return command

    def _parse_output(self, output_contract: str, stdout: str, stderr: str) -> dict:
        if output_contract == "json_stdout":
            text = stdout.strip()
            if not text:
                raise ValueError(f"The script did not return JSON output. Stderr: {stderr[:500]}")
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise ValueError("The script output must be a JSON object.")
            return payload
        return {"status": "pass", "summary": stdout.strip() or "Script completed.", "stdout": stdout, "stderr": stderr}

    def _normalize_artifacts(self, artifacts: list, module: AssessmentScriptModule) -> list[dict]:
        normalized = []
        for item in artifacts or []:
            if isinstance(item, str):
                path = self._resolve_path(item, module.working_directory)
                normalized.append({"path": str(path), "label": path.name, "content_type": "", "exists": path.exists()})
                continue
            if not isinstance(item, dict):
                continue
            raw_path = str(item.get("path", "")).strip()
            if not raw_path:
                continue
            path = self._resolve_path(raw_path, module.working_directory)
            normalized.append(
                {
                    "path": str(path),
                    "label": str(item.get("label", path.name)),
                    "content_type": str(item.get("content_type", "")),
                    "exists": path.exists(),
                }
            )
        return normalized

    def _resolve_path(self, value: str, working_directory: str | None = None) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        if working_directory:
            working_dir = Path(working_directory)
            if not working_dir.is_absolute():
                working_dir = self.root / working_dir
            return (working_dir / path).resolve()
        return (self.root / settings.external_modules_dir / path).resolve()

    def _working_directory(self, module: AssessmentScriptModule) -> Path:
        if module.working_directory:
            working_dir = Path(module.working_directory)
            if working_dir.is_absolute():
                return working_dir
            return (self.root / working_dir).resolve()
        return self.root

    def _entrypoint_ready(self, module: AssessmentScriptModule) -> bool:
        if module.entrypoint_type == "module":
            return bool(module.entrypoint_ref.strip())
        return self._resolve_path(module.entrypoint_ref, module.working_directory).exists()

    def _entrypoint_label(self, module: AssessmentScriptModule) -> str:
        if module.entrypoint_type == "module":
            return module.entrypoint_ref
        return str(self._resolve_path(module.entrypoint_ref, module.working_directory))

    @staticmethod
    def _apply_placeholders(raw: str, values: dict[str, str]) -> str:
        rendered = raw
        for key, value in values.items():
            rendered = rendered.replace("{" + key + "}", value)
        return rendered

    @staticmethod
    def _json_list(raw: str) -> list[str]:
        try:
            payload = json.loads(raw or "[]")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON list: {exc}") from exc
        if not isinstance(payload, list):
            raise ValueError("Expected a JSON array.")
        return [str(item) for item in payload]

    def _module_by_code(self, module_code: str) -> AssessmentScriptModule:
        module = self.session.scalar(
            select(AssessmentScriptModule).where(AssessmentScriptModule.module_code == _normalize_code(module_code))
        )
        if module is None:
            raise ValueError(f"Script module not found: {module_code}")
        return module

    def _organization_by_code(self, code: str | None) -> Organization | None:
        if not code:
            return None
        organization = self.session.scalar(select(Organization).where(Organization.code == _normalize_code(code)))
        if organization is None:
            raise ValueError(f"Organization not found: {code}")
        return organization

    def _framework_binding_by_code(self, code: str | None) -> OrganizationFrameworkBinding | None:
        if not code:
            return None
        binding = self.session.scalar(
            select(OrganizationFrameworkBinding).where(
                OrganizationFrameworkBinding.binding_code == _normalize_code(code)
            )
        )
        if binding is None:
            raise ValueError(f"Framework binding not found: {code}")
        return binding

    def _product_by_code(self, organization_id: int | None, code: str | None) -> Product | None:
        if not code:
            return None
        query = select(Product).where(Product.code == _normalize_code(code))
        if organization_id is not None:
            query = query.where(Product.organization_id == organization_id)
        product = self.session.scalar(query)
        if product is None:
            raise ValueError(f"Product not found: {code}")
        return product

    def _product_flavor_by_code(self, product_id: int | None, code: str | None) -> ProductFlavor | None:
        if not code:
            return None
        query = select(ProductFlavor).where(ProductFlavor.code == _normalize_code(code))
        if product_id is not None:
            query = query.where(ProductFlavor.product_id == product_id)
        flavor = self.session.scalar(query)
        if flavor is None:
            raise ValueError(f"Product flavor not found: {code}")
        return flavor

    def _framework_by_code(self, code: str | None) -> Framework | None:
        if not code:
            return None
        framework = self.session.scalar(select(Framework).where(Framework.code == _normalize_code(code)))
        if framework is None:
            raise ValueError(f"Framework not found: {code}")
        return framework

    def _control_by_key(self, framework_id: int | None, control_id: str | None) -> Control | None:
        if not control_id:
            return None
        query = select(Control).where(Control.control_id == control_id)
        if framework_id is not None:
            query = query.where(Control.framework_id == framework_id)
        control = self.session.scalar(query)
        if control is None:
            raise ValueError(f"Control not found: {control_id}")
        return control

    def _unified_control_by_code(self, code: str | None) -> UnifiedControl | None:
        if not code:
            return None
        unified_control = self.session.scalar(
            select(UnifiedControl).where(UnifiedControl.code == _normalize_code(code))
        )
        if unified_control is None:
            raise ValueError(f"Unified control not found: {code}")
        return unified_control

    def _plan_by_code(self, code: str | None) -> EvidenceCollectionPlan | None:
        if not code:
            return None
        plan = self.session.scalar(
            select(EvidenceCollectionPlan).where(EvidenceCollectionPlan.plan_code == _normalize_code(code))
        )
        if plan is None:
            raise ValueError(f"Evidence plan not found: {code}")
        return plan
