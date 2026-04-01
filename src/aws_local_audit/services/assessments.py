from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from aws_local_audit.config import settings
from aws_local_audit.integrations.confluence import ConfluenceClient
from aws_local_audit.models import (
    AssessmentRun,
    AssessmentRunItem,
    AssessmentSchedule,
    ControlImplementation,
    Framework,
    OrganizationFrameworkBinding,
    Product,
    ProductFlavor,
    SystemSetting,
    UnifiedControlMapping,
)
from aws_local_audit.services.evidence import EvidenceService
from aws_local_audit.services.lifecycle import LifecycleService


CADENCE_MONTHS = {
    "monthly": 1,
    "quarterly": 3,
    "yearly": 12,
}
SCHEDULE_LOCK_TIMEOUT = timedelta(hours=2)


def add_months(dt: datetime, months: int) -> datetime:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(
        dt.day,
        [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1],
    )
    return dt.replace(year=year, month=month, day=day)


class AssessmentService:
    def __init__(self, session):
        self.session = session
        self.lifecycle = LifecycleService(session)

    def run_assessment(self, framework_code: str) -> AssessmentRun:
        framework = self.session.scalar(
            select(Framework).options(selectinload(Framework.controls)).where(Framework.code == framework_code)
        )
        if framework is None:
            raise ValueError(f"Framework not found: {framework_code}")

        evidence_service = EvidenceService(self.session)
        if not self._offline_mode_enabled():
            evidence_service.collect_for_framework(framework_code)
        latest = evidence_service.latest_for_framework(framework.id, self.session)
        return self._build_run(
            framework=framework,
            latest=latest,
        )

    def run_binding_assessment(
        self,
        binding_code: str,
        product_code: str | None = None,
        product_flavor_code: str | None = None,
    ) -> AssessmentRun:
        binding = self.session.scalar(
            select(OrganizationFrameworkBinding)
            .options(
                selectinload(OrganizationFrameworkBinding.framework),
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

        evidence_service = EvidenceService(self.session)
        if not self._offline_mode_enabled():
            evidence_service.collect_for_binding(
                binding_code=binding_code,
                product_code=product_code,
                product_flavor_code=product_flavor_code,
            )
        latest = evidence_service.latest_for_framework(
            binding.framework_id,
            self.session,
            organization_id=binding.organization_id,
            product_id=product.id if product else None,
            product_flavor_id=flavor.id if flavor else None,
        )
        return self._build_run(
            framework=binding.framework,
            latest=latest,
            organization_id=binding.organization_id,
            product_id=product.id if product else None,
            product_flavor_id=flavor.id if flavor else None,
            confluence_parent_page_id=binding.confluence_parent_page_id,
            confluence=ConfluenceClient(
                self.session,
                binding.confluence_connection.name if binding.confluence_connection else None,
            ),
        )

    def _build_run(
        self,
        framework: Framework,
        latest,
        organization_id: int | None = None,
        product_id: int | None = None,
        product_flavor_id: int | None = None,
        confluence_parent_page_id: str | None = None,
        confluence: ConfluenceClient | None = None,
    ) -> AssessmentRun:
        total = len(latest)
        passed = sum(1 for item in latest if item.status == "pass")
        pending_evidence_reviews = sum(1 for item in latest if item.lifecycle_status == "pending_review")
        unresolved_evidence = sum(
            1 for item in latest if item.status not in {"pass", "fail", "not_applicable", "inherited"}
        )
        score = round((passed / total) * 100) if total else 0
        summary = f"{passed}/{total} controls passed"
        run = AssessmentRun(
            organization_id=organization_id,
            product_id=product_id,
            product_flavor_id=product_flavor_id,
            framework_id=framework.id,
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            status="completed",
            review_status="pending_review",
            assurance_status=(
                "needs_evidence"
                if unresolved_evidence
                else ("needs_attention" if pending_evidence_reviews else "assessed")
            ),
            score=score,
            summary=self._run_summary(
                summary=summary,
                unresolved_evidence=unresolved_evidence,
                pending_evidence_reviews=pending_evidence_reviews,
            ),
        )
        self.session.add(run)
        self.session.flush()

        for item in latest:
            unified_control_id = self._find_unified_control_id(item.control_id)
            control_implementation_id = self._find_control_implementation_id(
                organization_id=organization_id,
                product_id=product_id,
                product_flavor_id=product_flavor_id,
                unified_control_id=unified_control_id,
                control_id=item.control_id,
            )
            self.session.add(
                AssessmentRunItem(
                    assessment_run_id=run.id,
                    framework_id=framework.id,
                    control_id=item.control_id,
                    unified_control_id=unified_control_id,
                    control_implementation_id=control_implementation_id,
                    evidence_item_id=item.id,
                    status=item.status,
                    score=100 if item.status == "pass" else 0,
                    summary=item.summary,
                    payload_json=json.dumps(
                        {
                            "evidence_item_id": item.id,
                            "confluence_page_id": item.confluence_page_id,
                            "collected_at": item.collected_at.isoformat() if item.collected_at else None,
                        },
                        indent=2,
                    ),
                )
            )

        confluence_client = confluence or ConfluenceClient(self.session)
        if confluence_client.configured():
            try:
                page = confluence_client.create_page(
                    title=f"Assessment {framework.code} {datetime.utcnow():%Y-%m-%d}",
                    body_html=self._assessment_body(framework.name, framework.code, latest, score, run.summary),
                    parent_page_id=confluence_parent_page_id,
                )
                run.confluence_page_id = page.page_id
            except Exception as exc:
                run.summary = f"{run.summary} | Confluence publish warning: {exc}"
        self.lifecycle.record_event(
            entity_type="assessment_run",
            entity_id=run.id,
            lifecycle_name="audit_lifecycle",
            to_state=run.status,
            actor="assessment_service",
            payload={
                "framework": framework.code,
                "organization_id": organization_id,
                "product_id": product_id,
                "product_flavor_id": product_flavor_id,
                "score": run.score,
                "review_status": run.review_status,
                "assurance_status": run.assurance_status,
            },
        )
        return run

    def run_assessments(self, framework_codes: list[str]) -> list[AssessmentRun]:
        runs = []
        for framework_code in framework_codes:
            runs.append(self.run_assessment(framework_code))
        return runs

    def create_schedule(
        self,
        framework_codes: list[str],
        name: str,
        cadence: str,
        binding_code: str | None = None,
        product_code: str | None = None,
        product_flavor_code: str | None = None,
        execution_mode: str = "assisted",
        notes: str = "",
    ) -> AssessmentSchedule:
        if cadence not in CADENCE_MONTHS:
            raise ValueError("Cadence must be one of: monthly, quarterly, yearly")
        binding = None
        product = None
        flavor = None
        if (product_code or product_flavor_code) and not binding_code:
            raise ValueError("Product and flavor scoped schedules require a framework binding.")
        if binding_code:
            binding = self.session.scalar(
                select(OrganizationFrameworkBinding)
                .options(selectinload(OrganizationFrameworkBinding.framework))
                .where(OrganizationFrameworkBinding.binding_code == binding_code)
            )
            if binding is None:
                raise ValueError(f"Framework binding not found: {binding_code}")
            if not framework_codes:
                framework_codes = [binding.framework.code]
            elif set(framework_codes) != {binding.framework.code}:
                raise ValueError("Binding-scoped schedules can only target the framework attached to that binding.")
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

        if not framework_codes:
            raise ValueError("At least one framework code is required")
        frameworks = self.session.scalars(select(Framework).where(Framework.code.in_(framework_codes))).all()
        found_codes = {framework.code for framework in frameworks}
        missing = sorted(set(framework_codes) - found_codes)
        if missing:
            raise ValueError(f"Frameworks not found: {', '.join(missing)}")
        schedule = AssessmentSchedule(
            organization_id=binding.organization_id if binding else None,
            framework_binding_id=binding.id if binding else None,
            product_id=product.id if product else None,
            product_flavor_id=flavor.id if flavor else None,
            framework_id=frameworks[0].id if len(frameworks) == 1 else None,
            framework_codes=",".join(framework_codes),
            name=name,
            cadence=cadence,
            execution_mode=execution_mode,
            next_run_at=add_months(datetime.utcnow(), CADENCE_MONTHS[cadence]),
            notes=notes,
        )
        self.session.add(schedule)
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="assessment_schedule",
            entity_id=schedule.id,
            lifecycle_name="audit_lifecycle",
            to_state="scheduled",
            actor="assessment_service",
            payload={
                "name": schedule.name,
                "cadence": schedule.cadence,
                "framework_codes": schedule.framework_codes,
                "binding_code": binding.binding_code if binding else "",
                "product_code": product.code if product else "",
                "product_flavor_code": flavor.code if flavor else "",
                "execution_mode": schedule.execution_mode,
            },
        )
        return schedule

    def run_due_schedules(self) -> list[AssessmentRun]:
        schedules = self.session.scalars(
            select(AssessmentSchedule)
            .options(
                selectinload(AssessmentSchedule.framework),
                selectinload(AssessmentSchedule.framework_binding).selectinload(OrganizationFrameworkBinding.framework),
                selectinload(AssessmentSchedule.product),
                selectinload(AssessmentSchedule.product_flavor),
            )
            .where(
                AssessmentSchedule.enabled.is_(True),
                AssessmentSchedule.next_run_at <= datetime.utcnow(),
            )
        ).all()
        runs: list[AssessmentRun] = []
        for schedule in schedules:
            try:
                runs.extend(self.run_schedule(schedule.id))
            except Exception as exc:
                schedule.last_run_at = datetime.utcnow()
                schedule.last_run_status = "error"
                schedule.last_run_message = str(exc)
                self.lifecycle.record_event(
                    entity_type="assessment_schedule",
                    entity_id=schedule.id,
                    lifecycle_name="audit_lifecycle",
                    from_state="scheduled",
                    to_state="error",
                    actor="assessment_service",
                    payload={
                        "name": schedule.name,
                        "error": str(exc),
                    },
                )
        return runs

    def run_schedule(self, schedule_id: int) -> list[AssessmentRun]:
        schedule = self.session.scalar(
            select(AssessmentSchedule)
            .options(
                selectinload(AssessmentSchedule.framework),
                selectinload(AssessmentSchedule.framework_binding).selectinload(OrganizationFrameworkBinding.framework),
                selectinload(AssessmentSchedule.product),
                selectinload(AssessmentSchedule.product_flavor),
            )
            .where(AssessmentSchedule.id == schedule_id)
        )
        if schedule is None:
            raise ValueError(f"Assessment schedule not found: {schedule_id}")
        lock = self._acquire_schedule_lock(schedule)
        try:
            runs: list[AssessmentRun] = []
            if schedule.framework_binding is not None:
                run = self.run_binding_assessment(
                    binding_code=schedule.framework_binding.binding_code,
                    product_code=schedule.product.code if schedule.product else None,
                    product_flavor_code=schedule.product_flavor.code if schedule.product_flavor else None,
                )
                runs.append(run)
            else:
                framework_codes = self._schedule_framework_codes(schedule)
                runs.extend(self.run_assessments(framework_codes))
            schedule.last_run_at = datetime.utcnow()
            schedule.last_run_status = "completed"
            schedule.last_run_message = "Scheduled assessment run completed."
            schedule.next_run_at = add_months(schedule.next_run_at, CADENCE_MONTHS[schedule.cadence])
            self.lifecycle.record_event(
                entity_type="assessment_schedule",
                entity_id=schedule.id,
                lifecycle_name="audit_lifecycle",
                from_state="scheduled",
                to_state="completed",
                actor="assessment_service",
                payload={
                    "name": schedule.name,
                    "last_run_at": schedule.last_run_at.isoformat(),
                    "framework_codes": schedule.framework_codes,
                },
            )
            return runs
        finally:
            self._release_schedule_lock(lock)

    def review_run(
        self,
        run_id: int,
        review_status: str,
        assurance_status: str | None = None,
        actor: str = "assessment_service",
        rationale: str = "",
    ) -> AssessmentRun:
        run = self.session.get(AssessmentRun, run_id)
        if run is None:
            raise ValueError(f"Assessment run not found: {run_id}")
        if review_status == "approved":
            blocking = self._blocking_review_items(run)
            if blocking:
                raise ValueError(
                    "Assessment cannot be approved while evidence remains unresolved: "
                    + "; ".join(blocking[:5])
                )
        previous_review_status = run.review_status
        previous_assurance_status = run.assurance_status
        self.lifecycle.ensure_transition(
            entity_type="assessment_run",
            lifecycle_name="audit_lifecycle",
            from_state=previous_review_status,
            to_state=review_status,
        )
        run.review_status = review_status
        if assurance_status is not None:
            run.assurance_status = assurance_status
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="assessment_run",
            entity_id=run.id,
            lifecycle_name="audit_lifecycle",
            from_state=previous_review_status,
            to_state=run.review_status,
            actor=actor,
            rationale=rationale,
            payload={
                "framework": run.framework.code if run.framework else "",
                "score": run.score,
                "assurance_from": previous_assurance_status,
                "assurance_to": run.assurance_status,
            },
        )
        return run

    @staticmethod
    def _run_summary(summary: str, unresolved_evidence: int, pending_evidence_reviews: int) -> str:
        parts = [summary]
        if unresolved_evidence:
            parts.append(f"{unresolved_evidence} control(s) still need evidence collection or automation support")
        if pending_evidence_reviews:
            parts.append(f"{pending_evidence_reviews} evidence item(s) are pending review")
        return "; ".join(parts)

    def _acquire_schedule_lock(self, schedule: AssessmentSchedule) -> SystemSetting:
        lock_key = f"assessment_schedule_lock::{schedule.id}"
        now = datetime.utcnow()
        lock = self.session.scalar(select(SystemSetting).where(SystemSetting.setting_key == lock_key))
        if lock is None:
            lock = SystemSetting(setting_key=lock_key, description=f"Runtime lock for schedule {schedule.id}")
            self.session.add(lock)
        elif lock.setting_value:
            try:
                payload = json.loads(lock.setting_value)
                started_at = datetime.fromisoformat(payload.get("started_at", ""))
            except (TypeError, ValueError, json.JSONDecodeError):
                started_at = None
            if started_at and started_at >= now - SCHEDULE_LOCK_TIMEOUT:
                raise ValueError(
                    f"Schedule {schedule.id} is already running or was started recently at {started_at.isoformat()}."
                )
        lock.setting_value = json.dumps({"started_at": now.isoformat(), "schedule_id": schedule.id})
        self.session.flush()
        return lock

    def _release_schedule_lock(self, lock: SystemSetting) -> None:
        lock.setting_value = ""
        self.session.flush()

    @staticmethod
    def _blocking_review_items(run: AssessmentRun) -> list[str]:
        blocking: list[str] = []
        for item in run.run_items:
            evidence = item.evidence_item
            control_label = item.control.control_id if item.control else str(item.control_id)
            if evidence is None:
                blocking.append(f"{control_label} has no linked evidence item")
                continue
            if evidence.lifecycle_status in {"pending_review", "rejected", "collection_error", "collector_missing", "awaiting_collection"}:
                blocking.append(f"{control_label} is {evidence.lifecycle_status}")
        return blocking

    def _offline_mode_enabled(self) -> bool:
        if settings.offline_mode:
            return True
        setting = self.session.scalar(
            select(SystemSetting).where(SystemSetting.setting_key == "runtime.offline_mode")
        )
        if setting is None:
            return False
        return setting.setting_value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _schedule_framework_codes(schedule: AssessmentSchedule) -> list[str]:
        if schedule.framework_codes:
            return [item.strip() for item in schedule.framework_codes.split(",") if item.strip()]
        if schedule.framework:
            return [schedule.framework.code]
        return []

    def _find_unified_control_id(self, control_id: int) -> int | None:
        mapping = self.session.scalar(
            select(UnifiedControlMapping)
            .where(
                UnifiedControlMapping.control_id == control_id,
                UnifiedControlMapping.approval_status == "approved",
            )
            .order_by(UnifiedControlMapping.confidence.desc())
        )
        return mapping.unified_control_id if mapping else None

    def _find_control_implementation_id(
        self,
        organization_id: int | None,
        product_id: int | None,
        product_flavor_id: int | None,
        unified_control_id: int | None,
        control_id: int,
    ) -> int | None:
        if organization_id is None:
            return None

        query = select(ControlImplementation).where(
            ControlImplementation.organization_id == organization_id,
            ControlImplementation.product_id == product_id,
            ControlImplementation.product_flavor_id == product_flavor_id,
        )
        if unified_control_id is not None:
            query = query.where(
                (ControlImplementation.control_id == control_id)
                | (ControlImplementation.unified_control_id == unified_control_id)
            )
        else:
            query = query.where(ControlImplementation.control_id == control_id)

        implementation = self.session.scalar(query.order_by(ControlImplementation.updated_at.desc()))
        if implementation is not None or product_flavor_id is None:
            return implementation.id if implementation else None

        fallback_query = select(ControlImplementation).where(
            ControlImplementation.organization_id == organization_id,
            ControlImplementation.product_id == product_id,
            ControlImplementation.product_flavor_id.is_(None),
        )
        if unified_control_id is not None:
            fallback_query = fallback_query.where(
                (ControlImplementation.control_id == control_id)
                | (ControlImplementation.unified_control_id == unified_control_id)
            )
        else:
            fallback_query = fallback_query.where(ControlImplementation.control_id == control_id)
        implementation = self.session.scalar(fallback_query.order_by(ControlImplementation.updated_at.desc()))
        return implementation.id if implementation else None

    @staticmethod
    def _assessment_body(framework_name: str, framework_code: str, evidence_items, score: int, summary: str) -> str:
        rows = "".join(
            f"<tr><td>{item.control.control_id}</td><td>{item.control.title}</td><td>{item.status}</td><td>{item.summary}</td></tr>"
            for item in evidence_items
        )
        return (
            f"<h1>{framework_name} Assessment</h1>"
            f"<p><strong>Framework:</strong> {framework_code}</p>"
            f"<p><strong>Score:</strong> {score}%</p>"
            f"<p><strong>Summary:</strong> {summary}</p>"
            "<table><tbody>"
            "<tr><th>Control</th><th>Title</th><th>Status</th><th>Summary</th></tr>"
            f"{rows}</tbody></table>"
        )
