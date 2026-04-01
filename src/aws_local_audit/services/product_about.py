from __future__ import annotations

import tomllib
from pathlib import Path

import yaml
from sqlalchemy import select

from aws_local_audit.models import UserFeedbackMessage
from aws_local_audit.services.delivery_readiness import DeliveryReadinessAssessmentService
from aws_local_audit.services.validation import validate_feedback_payload


class ProductAboutService:
    def __init__(self, session, *, root: Path | None = None):
        self.session = session
        self.root = root or Path(__file__).resolve().parents[3]
        self.docs_root = self.root / "documentation"
        self.assessment_root = self.docs_root / "assessment"
        self.releases_path = self.docs_root / "releases" / "CHANGELOG.yaml"
        self.history_path = self.assessment_root / "MATURITY_HISTORY.yaml"
        self.qa_report_path = self.root / "testing" / "qa" / "reports" / "latest.json"

    def about_payload(self) -> dict:
        readiness = DeliveryReadinessAssessmentService(self.session, root=self.root).assess()
        releases = self.release_history()
        history = self.maturity_history()
        documents = self.assessment_documents()
        current_version = readiness["version"]
        current_release = next((item for item in releases if item["version"] == current_version), releases[0] if releases else None)
        return {
            "product_name": readiness["product_name"],
            "version": current_version,
            "current_release": current_release,
            "delivery_readiness": readiness,
            "release_history": releases,
            "maturity_history": history,
            "assessment_documents": documents,
            "feedback": self.list_feedback(limit=100),
        }

    def product_metadata(self) -> dict:
        payload = tomllib.loads((self.root / "pyproject.toml").read_text(encoding="utf-8"))
        project = payload.get("project", {})
        return {
            "name": project.get("name", "my_grc"),
            "version": project.get("version", "0.0.0"),
            "description": project.get("description", ""),
        }

    def release_history(self) -> list[dict]:
        payload = self._load_yaml(self.releases_path)
        releases = payload.get("releases", [])
        return list(releases)

    def maturity_history(self) -> list[dict]:
        payload = self._load_yaml(self.history_path)
        assessments = list(payload.get("assessments", []))
        known_docs = {item.get("document") for item in assessments}
        for document in self.assessment_documents():
            if document["path"] in known_docs:
                continue
            assessments.append(
                {
                    "recorded_on": "",
                    "title": document["title"],
                    "document": document["path"],
                    "model": "document_only",
                    "confidence": "Low",
                    "scope": "Historical assessment artifact",
                    "scores": {},
                    "measurement_basis": "Document present, but no centralized numeric score was captured for this entry.",
                }
            )
        assessments.sort(key=lambda item: (item.get("recorded_on", ""), item.get("title", "")), reverse=True)
        return assessments

    def assessment_documents(self) -> list[dict]:
        if not self.assessment_root.exists():
            return []
        documents = []
        for path in sorted(self.assessment_root.glob("*.md"), reverse=True):
            title = path.stem.replace("_", " ").title()
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    stripped = line.strip()
                    if stripped.startswith("# "):
                        title = stripped[2:].strip()
                        break
            except OSError:
                pass
            documents.append(
                {
                    "title": title,
                    "path": str(path.relative_to(self.root)).replace("\\", "/"),
                    "file_name": path.name,
                }
            )
        return documents

    def submit_feedback(
        self,
        *,
        subject: str,
        message: str,
        area: str = "",
        page_context: str = "",
        reporter_name: str = "",
        reporter_role: str = "",
        contact: str = "",
        version_label: str = "",
    ) -> UserFeedbackMessage:
        validate_feedback_payload(subject=subject, message=message)
        item = UserFeedbackMessage(
            version_label=version_label or self.product_metadata()["version"],
            reporter_name=reporter_name.strip(),
            reporter_role=reporter_role.strip(),
            contact=contact.strip(),
            area=area.strip(),
            page_context=page_context.strip(),
            subject=subject.strip(),
            message=message.strip(),
            status="new",
        )
        self.session.add(item)
        self.session.flush()
        return item

    def update_feedback_status(self, feedback_id: int, status: str) -> UserFeedbackMessage:
        item = self.session.get(UserFeedbackMessage, feedback_id)
        if item is None:
            raise ValueError(f"Feedback message not found: {feedback_id}")
        item.status = status.strip() or item.status
        self.session.flush()
        return item

    def list_feedback(self, *, limit: int = 50) -> list[dict]:
        query = select(UserFeedbackMessage).order_by(UserFeedbackMessage.created_at.desc(), UserFeedbackMessage.id.desc())
        items = self.session.scalars(query.limit(limit)).all()
        return [
            {
                "id": item.id,
                "version_label": item.version_label,
                "reporter_name": item.reporter_name,
                "reporter_role": item.reporter_role,
                "contact": item.contact,
                "area": item.area,
                "page_context": item.page_context,
                "subject": item.subject,
                "message": item.message,
                "status": item.status,
                "created_at": item.created_at.isoformat() if item.created_at else "",
                "updated_at": item.updated_at.isoformat() if item.updated_at else "",
            }
            for item in items
        ]

    @staticmethod
    def _load_yaml(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError:
            return {}
        return payload or {}
