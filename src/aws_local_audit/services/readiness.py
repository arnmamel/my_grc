from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import false, select
from sqlalchemy.orm import selectinload

from aws_local_audit.collectors import COLLECTORS
from aws_local_audit.models import (
    EvidenceCollectionPlan,
    Framework,
    OrganizationFrameworkBinding,
    Product,
    ProductFlavor,
    UnifiedControlMapping,
)
from aws_local_audit.services.evidence import EvidenceService
from aws_local_audit.services.governance import GovernanceService
from aws_local_audit.services.script_modules import ScriptModuleService


class OperationalReadinessService:
    def __init__(self, session):
        self.session = session

    def assess_binding(
        self,
        binding_code: str,
        product_code: str | None = None,
        product_flavor_code: str | None = None,
    ) -> dict:
        binding = self.session.scalar(
            select(OrganizationFrameworkBinding)
            .options(
                selectinload(OrganizationFrameworkBinding.framework).selectinload(Framework.controls),
                selectinload(OrganizationFrameworkBinding.confluence_connection),
            )
            .where(OrganizationFrameworkBinding.binding_code == binding_code)
        )
        if binding is None:
            raise ValueError(f"Framework binding not found: {binding_code}")

        product = None
        flavor = None
        if product_code:
            product = self.session.scalar(
                select(Product).where(Product.organization_id == binding.organization_id, Product.code == product_code)
            )
            if product is None:
                raise ValueError(f"Product not found for binding {binding_code}: {product_code}")
        if product_flavor_code:
            if product is None:
                raise ValueError("A product is required when a product flavor is provided.")
            flavor = self.session.scalar(
                select(ProductFlavor).where(ProductFlavor.product_id == product.id, ProductFlavor.code == product_flavor_code)
            )
            if flavor is None:
                raise ValueError(f"Product flavor not found for binding {binding_code}: {product_flavor_code}")

        governance = GovernanceService(self.session)
        evidence_service = EvidenceService(self.session)
        collection_plan = evidence_service.build_collection_plan_for_binding(
            binding_code=binding_code,
            product_code=product_code,
            product_flavor_code=product_flavor_code,
        )
        latest_evidence = evidence_service.latest_for_framework(
            binding.framework_id,
            self.session,
            organization_id=binding.organization_id,
            product_id=product.id if product else None,
            product_flavor_id=flavor.id if flavor else None,
        )
        latest_by_control_id = {item.control_id: item for item in latest_evidence}
        unified_by_control = {
            item.control_id: item.unified_control_id
            for item in self.session.scalars(
                select(UnifiedControlMapping).where(
                    UnifiedControlMapping.framework_id == binding.framework_id,
                    UnifiedControlMapping.approval_status == "approved",
                )
            ).all()
        }
        evidence_plans = self._load_evidence_plans(
            framework_id=binding.framework_id,
            unified_control_ids={item for item in unified_by_control.values() if item is not None},
        )

        control_index = {item.control_id: item for item in binding.framework.controls}
        applicable_controls = [
            item for item in collection_plan["controls"] if item["applicability_status"] not in {"not_applicable", "inherited"}
        ]

        profile_report = self._assess_profiles(
            profiles=collection_plan["profiles"],
            offline_mode=governance.offline_mode_enabled(),
        )
        control_report = self._assess_controls(
            controls=applicable_controls,
            control_index=control_index,
            latest_by_control_id=latest_by_control_id,
            unified_by_control=unified_by_control,
            evidence_plans=evidence_plans,
            organization_id=binding.organization_id,
            framework_binding_id=binding.id,
            product_id=product.id if product else None,
            product_flavor_id=flavor.id if flavor else None,
        )
        confluence_report = self._assess_confluence(binding)

        areas = [
            {
                "area": "AWS Profile Operations",
                "score": profile_report["score"],
                "target": 4.0,
                "summary": profile_report["summary"],
            },
            {
                "area": "Evidence Plan Coverage",
                "score": control_report["plan_score"],
                "target": 4.0,
                "summary": control_report["plan_summary"],
            },
            {
                "area": "Collection Execution",
                "score": control_report["execution_score"],
                "target": 4.0,
                "summary": control_report["execution_summary"],
            },
            {
                "area": "Evidence Freshness",
                "score": control_report["freshness_score"],
                "target": 4.0,
                "summary": control_report["freshness_summary"],
            },
            {
                "area": "Confluence Publishing",
                "score": confluence_report["score"],
                "target": 4.0,
                "summary": confluence_report["summary"],
            },
        ]
        overall_score = round(sum(item["score"] for item in areas) / len(areas), 1) if areas else 0.0
        blockers = [
            *profile_report["blockers"],
            *control_report["blockers"],
            *confluence_report["blockers"],
        ]
        warnings = [
            *profile_report["warnings"],
            *control_report["warnings"],
            *confluence_report["warnings"],
        ]

        return {
            "binding_code": binding.binding_code,
            "framework_code": binding.framework.code,
            "organization_code": binding.organization.code,
            "product_code": product.code if product else "",
            "product_flavor_code": flavor.code if flavor else "",
            "offline_mode": governance.offline_mode_enabled(),
            "overall_score": overall_score,
            "readiness_status": self._status_for_score(overall_score, blockers),
            "areas": areas,
            "profiles": profile_report["profiles"],
            "controls": control_report["controls"],
            "blockers": blockers,
            "warnings": warnings,
            "counts": {
                "applicable_controls": len(applicable_controls),
                "fresh_controls": control_report["fresh_controls"],
                "stale_controls": control_report["stale_controls"],
                "missing_controls": control_report["missing_controls"],
                "review_pending_controls": control_report["review_pending_controls"],
                "controls_with_plans": control_report["controls_with_plans"],
                "controls_without_plans": control_report["controls_without_plans"],
                "profiles_required": len(collection_plan["profiles"]),
                "profiles_validated": profile_report["validated_profiles"],
            },
            "confluence": confluence_report,
        }

    def _load_evidence_plans(self, framework_id: int, unified_control_ids: set[int]) -> list[EvidenceCollectionPlan]:
        query = select(EvidenceCollectionPlan).where(EvidenceCollectionPlan.lifecycle_status.not_in(["retired", "archived"]))
        query = query.where(
            (EvidenceCollectionPlan.framework_id == framework_id)
            | (
                EvidenceCollectionPlan.unified_control_id.in_(sorted(unified_control_ids))
                if unified_control_ids
                else false()
            )
        )
        return list(self.session.scalars(query))

    def _assess_profiles(self, profiles: list[dict], offline_mode: bool) -> dict:
        blockers: list[str] = []
        warnings: list[str] = []
        validated_profiles = 0
        aligned_profiles = 0
        rows: list[dict] = []

        for item in profiles:
            validation_status = item.get("last_validation_status", "")
            account_alignment = item.get("account_alignment", "unknown")
            if validation_status == "pass":
                validated_profiles += 1
            if account_alignment in {"matched", "unknown", "unverified"}:
                aligned_profiles += 1

            if not item["registered_in_app"]:
                blockers.append(f"AWS profile `{item['aws_profile']}` is required but not registered in the app.")
            elif not offline_mode and validation_status != "pass":
                blockers.append(
                    f"AWS profile `{item['aws_profile']}` is not validated. Complete `aws sso login` and validate it."
                )
            elif account_alignment == "mismatch":
                blockers.append(
                    f"AWS profile `{item['aws_profile']}` resolved to account `{item['detected_account_id']}` instead of the expected scope."
                )

            if item["registered_in_app"] and validation_status != "pass":
                warnings.append(
                    f"AWS profile `{item['aws_profile']}` has no passing validation yet."
                )

            rows.append(
                {
                    "aws_profile": item["aws_profile"],
                    "registered_in_app": item["registered_in_app"],
                    "last_validation_status": validation_status or "unknown",
                    "last_validated_at": item.get("last_validated_at", ""),
                    "detected_account_id": item.get("detected_account_id", ""),
                    "account_alignment": account_alignment,
                    "controls": len(item["controls"]),
                    "regions": ", ".join(item["regions"]),
                }
            )

        total = len(profiles)
        if total == 0:
            score = 4.0
            summary = "No AWS profiles are required for the selected scope."
        elif offline_mode:
            score = 3.5
            summary = f"Offline mode is enabled; {total} profile requirement(s) are deferred."
        else:
            registration_ratio = sum(1 for item in profiles if item["registered_in_app"]) / total
            validation_ratio = validated_profiles / total
            alignment_ratio = aligned_profiles / total
            score = round(((registration_ratio + validation_ratio + alignment_ratio) / 3) * 4, 1)
            summary = f"{validated_profiles}/{total} required profile(s) are validated for live AWS execution."

        return {
            "score": score,
            "summary": summary,
            "profiles": rows,
            "validated_profiles": validated_profiles,
            "blockers": self._dedupe(blockers),
            "warnings": self._dedupe(warnings),
        }

    def _assess_controls(
        self,
        controls: list[dict],
        control_index: dict[str, object],
        latest_by_control_id: dict[int, object],
        unified_by_control: dict[int, int | None],
        evidence_plans: list[EvidenceCollectionPlan],
        organization_id: int | None = None,
        framework_binding_id: int | None = None,
        product_id: int | None = None,
        product_flavor_id: int | None = None,
    ) -> dict:
        blockers: list[str] = []
        warnings: list[str] = []
        rows: list[dict] = []
        controls_with_plans = 0
        plan_ready_controls = 0
        executable_controls = 0
        fresh_controls = 0
        stale_controls = 0
        missing_controls = 0
        review_pending_controls = 0
        script_modules = ScriptModuleService(self.session)

        for item in controls:
            control = control_index[item["control_id"]]
            unified_control_id = unified_by_control.get(control.id)
            plan = self._best_plan_for_control(
                framework_id=control.framework_id,
                control_id=control.id,
                unified_control_id=unified_control_id,
                evidence_plans=evidence_plans,
            )
            latest = latest_by_control_id.get(control.id)
            freshness_days = plan.minimum_freshness_days if plan else 30
            evidence_state = self._evidence_state(latest, freshness_days)
            collector_available = control.evidence_query in COLLECTORS
            script_ready = {"ready": False, "module_code": "", "binding_code": "", "entrypoint_exists": False}
            if plan and plan.collector_key.startswith(("script:", "script-binding:")):
                try:
                    script_ready = script_modules.collector_ready(
                        plan.collector_key,
                        organization_id=organization_id,
                        framework_binding_id=framework_binding_id,
                        product_id=product_id,
                        product_flavor_id=product_flavor_id,
                        framework_id=control.framework_id,
                        control_id=control.id,
                        unified_control_id=unified_control_id,
                        evidence_plan_id=plan.id,
                    )
                except ValueError as exc:
                    script_ready = {"ready": False, "module_code": "", "binding_code": "", "error": str(exc)}
            execution_mode = plan.execution_mode if plan else ("automated" if collector_available else "manual")
            plan_state = plan.lifecycle_status if plan else "missing"
            plan_ready = plan is not None and plan.lifecycle_status in {"approved", "active", "ready", "published"}

            if plan is not None:
                controls_with_plans += 1
                if plan_ready:
                    plan_ready_controls += 1
                else:
                    warnings.append(
                        f"Evidence plan `{plan.plan_code}` for control `{control.control_id}` is still `{plan.lifecycle_status}`."
                    )
            else:
                blockers.append(f"Control `{control.control_id}` has no evidence collection plan.")

            if not plan_ready:
                pass
            elif execution_mode in {"manual", "assisted"} or collector_available or script_ready["ready"]:
                executable_controls += 1
            else:
                if plan and plan.collector_key.startswith(("script:", "script-binding:")):
                    blockers.append(
                        f"Control `{control.control_id}` depends on script collector `{plan.collector_key}` but the module or scoped binding is not ready."
                    )
                else:
                    blockers.append(
                        f"Control `{control.control_id}` expects `{execution_mode}` execution but no collector is registered for `{control.evidence_query}`."
                    )

            if evidence_state == "fresh":
                fresh_controls += 1
            elif evidence_state == "review_pending":
                review_pending_controls += 1
                warnings.append(f"Control `{control.control_id}` has evidence that still requires reviewer approval.")
            elif evidence_state == "missing":
                missing_controls += 1
                warnings.append(f"Control `{control.control_id}` has no recent evidence in local storage.")
            else:
                stale_controls += 1
                warnings.append(
                    f"Control `{control.control_id}` has evidence state `{evidence_state}` against a freshness target of {freshness_days} day(s)."
                )

            rows.append(
                {
                    "control_id": control.control_id,
                    "title": control.title,
                    "evidence_query": control.evidence_query,
                    "plan_code": plan.plan_code if plan else "",
                    "plan_status": plan_state,
                    "execution_mode": execution_mode,
                    "collector_available": collector_available,
                    "script_module": script_ready.get("module_code", ""),
                    "script_binding": script_ready.get("binding_code", ""),
                    "script_ready": script_ready.get("ready", False),
                    "evidence_state": evidence_state,
                    "freshness_days": freshness_days,
                }
            )

        total = len(controls) or 1
        plan_score = round(((plan_ready_controls / total) + (controls_with_plans / total)) / 2 * 4, 1)
        execution_score = round((executable_controls / total) * 4, 1)
        freshness_score = round((fresh_controls / total) * 4, 1)

        return {
            "plan_score": plan_score,
            "plan_summary": f"{controls_with_plans}/{len(controls)} applicable control(s) have an evidence plan; {plan_ready_controls} are approved, ready, or active.",
            "execution_score": execution_score,
            "execution_summary": f"{executable_controls}/{len(controls)} applicable control(s) can be executed with approved plans and the current manual or automated logic.",
            "freshness_score": freshness_score,
            "freshness_summary": f"{fresh_controls}/{len(controls)} applicable control(s) have fresh pass/fail evidence available locally.",
            "controls": rows,
            "controls_with_plans": controls_with_plans,
            "controls_without_plans": max(len(controls) - controls_with_plans, 0),
            "fresh_controls": fresh_controls,
            "stale_controls": stale_controls,
            "missing_controls": missing_controls,
            "review_pending_controls": review_pending_controls,
            "blockers": self._dedupe(blockers),
            "warnings": self._dedupe(warnings),
        }

    @staticmethod
    def _assess_confluence(binding: OrganizationFrameworkBinding) -> dict:
        connection = binding.confluence_connection
        if connection is None:
            return {
                "score": 2.5,
                "summary": "No Confluence connection is bound to this framework scope.",
                "status": "not_configured",
                "blockers": [],
                "warnings": ["No Confluence connection is configured for evidence or assessment publishing."],
            }
        if connection.last_test_status == "pass":
            return {
                "score": 4.0,
                "summary": f"Confluence connection `{connection.name}` last passed health checks.",
                "status": "pass",
                "blockers": [],
                "warnings": [],
            }
        if connection.last_test_status == "error":
            return {
                "score": 1.0,
                "summary": f"Confluence connection `{connection.name}` last failed health checks.",
                "status": "error",
                "blockers": [
                    f"Confluence connection `{connection.name}` failed its last health check: {connection.last_test_message}"
                ],
                "warnings": [],
            }
        return {
            "score": 2.0,
            "summary": f"Confluence connection `{connection.name}` is configured but has not been tested yet.",
            "status": "untested",
            "blockers": [],
            "warnings": [f"Confluence connection `{connection.name}` should be health-checked before operational publishing."],
        }

    @staticmethod
    def _best_plan_for_control(
        framework_id: int,
        control_id: int,
        unified_control_id: int | None,
        evidence_plans: list[EvidenceCollectionPlan],
    ) -> EvidenceCollectionPlan | None:
        def _weight(plan: EvidenceCollectionPlan) -> tuple[int, int]:
            specificity = 0
            if plan.control_id == control_id:
                specificity = 3
            elif unified_control_id is not None and plan.unified_control_id == unified_control_id:
                specificity = 2
            elif plan.framework_id is not None:
                specificity = 1
            state_weight = 1 if plan.lifecycle_status in {"approved", "active", "ready", "published"} else 0
            return specificity, state_weight

        candidates = [
            plan
            for plan in evidence_plans
            if plan.control_id == control_id
            or (unified_control_id is not None and plan.unified_control_id == unified_control_id)
            or (plan.control_id is None and plan.unified_control_id is None and plan.framework_id == framework_id)
        ]
        if not candidates:
            return None
        return max(candidates, key=_weight)

    @staticmethod
    def _evidence_state(evidence_item, freshness_days: int) -> str:
        if evidence_item is None:
            return "missing"
        if evidence_item.lifecycle_status == "pending_review":
            return "review_pending"
        if evidence_item.status not in {"pass", "fail"}:
            return "insufficient"
        if evidence_item.collected_at >= datetime.utcnow() - timedelta(days=freshness_days):
            return "fresh"
        return "stale"

    @staticmethod
    def _status_for_score(score: float, blockers: list[str]) -> str:
        if blockers:
            return "blocked"
        if score >= 3.5:
            return "ready"
        if score >= 2.5:
            return "partial"
        return "early"

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in values:
            if item in seen:
                continue
            seen.add(item)
            ordered.append(item)
        return ordered
