from __future__ import annotations

from aws_local_audit.services.enterprise_maturity import EnterpriseMaturityService
from aws_local_audit.services.governance import GovernanceService
from aws_local_audit.services.phase1_maturity import Phase1MaturityService
from aws_local_audit.services.review_queue import ReviewQueueService
from aws_local_audit.services.asset_catalog import AssetCatalogService


class WorkspaceGuidanceService:
    def __init__(self, session):
        self.session = session

    def summary(self) -> dict:
        governance = GovernanceService(self.session)
        onboarding = governance.onboarding_status()
        phase1 = Phase1MaturityService(self.session).assess()
        enterprise = EnterpriseMaturityService(self.session).assess()
        review = ReviewQueueService(self.session).summary()
        inventory = AssetCatalogService(self.session).asset_types()
        return {
            "onboarding": onboarding,
            "phase1": phase1,
            "enterprise": enterprise,
            "review": review,
            "inventory": inventory,
            "actions": self._actions(onboarding, phase1, enterprise, review),
        }

    @staticmethod
    def _actions(onboarding: dict, phase1: dict, enterprise: dict, review: dict) -> list[dict]:
        actions = []
        if onboarding["progress"] < 1:
            actions.append(
                {
                    "title": "Complete onboarding foundations",
                    "priority": "high",
                    "area": "Assistant Center",
                    "detail": onboarding["steps"][0]["detail"] if onboarding["steps"] else "Set up the initial workspace assets.",
                }
            )
        if review["priorities"].get("critical", 0):
            actions.append(
                {
                    "title": "Resolve critical review items",
                    "priority": "critical",
                    "area": "Governance Center",
                    "detail": f"{review['priorities']['critical']} critical item(s) are blocking reliable operations.",
                }
            )
        for item in phase1["top_blockers"][:2]:
            area = "Workspace Home"
            if "scf pivot" in item.lower() or "annex a" in item.lower():
                area = "Wizards"
            elif "organization and product scope" in item.lower() or "product control profiles" in item.lower():
                area = "Portfolio"
            actions.append({"title": "Improve Phase 1 maturity", "priority": "medium", "area": area, "detail": item})
        for item in enterprise["top_blockers"][:3]:
            area = "Governance Center"
            if "implementation records" in item.lower() or "product control profiles" in item.lower():
                area = "Portfolio"
            actions.append({"title": "Reduce enterprise gaps", "priority": "medium", "area": area, "detail": item})
        if not actions:
            actions.append(
                {
                    "title": "Workspace is in a healthy state",
                    "priority": "low",
                    "area": "Workspace Home",
                    "detail": "No urgent blockers were detected. Focus on continuous improvement and deeper automation coverage.",
                }
            )
        return actions[:8]
