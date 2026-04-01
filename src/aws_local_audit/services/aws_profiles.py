from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from aws_local_audit.aws_session import build_session
from aws_local_audit.models import AwsCliProfile
from aws_local_audit.services.lifecycle import LifecycleService


def _normalize_profile_name(value: str) -> str:
    return value.strip()


class AwsProfileService:
    def __init__(self, session):
        self.session = session
        self.lifecycle = LifecycleService(session)

    def upsert_profile(
        self,
        profile_name: str,
        sso_start_url: str,
        sso_region: str,
        sso_account_id: str = "",
        sso_role_name: str = "",
        default_region: str = "",
        output_format: str = "json",
        sso_session_name: str | None = None,
        registration_mode: str = "manual",
        config_scope: str = "wsl_local",
        status: str = "active",
        notes: str = "",
    ) -> AwsCliProfile:
        resolved_name = _normalize_profile_name(profile_name)
        profile = self.session.scalar(
            select(AwsCliProfile).where(AwsCliProfile.profile_name == resolved_name)
        )
        if profile is None:
            profile = AwsCliProfile(profile_name=resolved_name)
            self.session.add(profile)
        profile.sso_session_name = sso_session_name or f"{resolved_name}-session"
        profile.sso_start_url = sso_start_url
        profile.sso_region = sso_region
        profile.sso_account_id = sso_account_id
        profile.sso_role_name = sso_role_name
        profile.default_region = default_region
        profile.output_format = output_format
        profile.registration_mode = registration_mode
        profile.config_scope = config_scope
        profile.status = status
        profile.notes = notes
        self.session.flush()
        return profile

    def list_profiles(self) -> list[AwsCliProfile]:
        return list(self.session.scalars(select(AwsCliProfile).order_by(AwsCliProfile.profile_name)))

    def get_profile(self, profile_name: str) -> AwsCliProfile:
        profile = self.session.scalar(
            select(AwsCliProfile).where(AwsCliProfile.profile_name == _normalize_profile_name(profile_name))
        )
        if profile is None:
            raise ValueError(f"AWS CLI profile not found: {profile_name}")
        return profile

    @staticmethod
    def login_command(profile_name: str) -> str:
        return f"aws sso login --profile {profile_name}"

    def render_config_block(self, profile_name: str) -> str:
        profile = self.get_profile(profile_name)
        return (
            f"[profile {profile.profile_name}]\n"
            f"sso_session = {profile.sso_session_name}\n"
            f"sso_account_id = {profile.sso_account_id}\n"
            f"sso_role_name = {profile.sso_role_name}\n"
            f"region = {profile.default_region}\n"
            f"output = {profile.output_format}\n\n"
            f"[sso-session {profile.sso_session_name}]\n"
            f"sso_start_url = {profile.sso_start_url}\n"
            f"sso_region = {profile.sso_region}\n"
            "sso_registration_scopes = sso:account:access\n"
        )

    def render_all_config_blocks(self) -> str:
        profiles = self.list_profiles()
        return "\n".join(self.render_config_block(item.profile_name).strip() for item in profiles if item.status == "active")

    def validate_profile(self, profile_name: str) -> dict:
        profile = self.get_profile(profile_name)
        region_name = profile.default_region or profile.sso_region or "eu-west-1"
        previous_status = profile.last_validation_status or ""
        try:
            session = build_session(profile.profile_name, region_name)
            identity = session.client("sts", region_name=region_name).get_caller_identity()
            profile.last_validated_at = datetime.utcnow()
            profile.last_validation_status = "pass"
            profile.last_validation_message = "AWS profile validated through sts:GetCallerIdentity."
            profile.detected_account_id = identity.get("Account", "")
            profile.detected_arn = identity.get("Arn", "")
            self.session.flush()
            self.lifecycle.record_event(
                entity_type="aws_cli_profile",
                entity_id=profile.id,
                lifecycle_name="aws_profile_validation",
                from_state=previous_status,
                to_state=profile.last_validation_status,
                actor="aws_profile_service",
                payload={
                    "profile_name": profile.profile_name,
                    "detected_account_id": profile.detected_account_id,
                    "detected_arn": profile.detected_arn,
                    "region": region_name,
                },
            )
            return {
                "status": "pass",
                "message": profile.last_validation_message,
                "account_id": profile.detected_account_id,
                "arn": profile.detected_arn,
                "region": region_name,
            }
        except Exception as exc:
            profile.last_validated_at = datetime.utcnow()
            profile.last_validation_status = "error"
            profile.last_validation_message = (
                f"Validation failed. Run `aws sso login --profile {profile.profile_name}` and retry. {exc}"
            )
            self.session.flush()
            self.lifecycle.record_event(
                entity_type="aws_cli_profile",
                entity_id=profile.id,
                lifecycle_name="aws_profile_validation",
                from_state=previous_status,
                to_state=profile.last_validation_status,
                actor="aws_profile_service",
                payload={
                    "profile_name": profile.profile_name,
                    "region": region_name,
                    "error": str(exc),
                },
            )
            return {
                "status": "error",
                "message": profile.last_validation_message,
                "account_id": profile.detected_account_id,
                "arn": profile.detected_arn,
                "region": region_name,
            }
