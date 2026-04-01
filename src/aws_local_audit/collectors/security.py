from __future__ import annotations

from botocore.exceptions import BotoCoreError, ClientError

from aws_local_audit.collectors.base import BaseCollector, CollectionResult


def _normalize_error(exc: Exception) -> CollectionResult:
    return CollectionResult(
        status="error",
        summary=str(exc),
        payload={"error": str(exc)},
    )


class IAMPasswordPolicyCollector(BaseCollector):
    key = "iam.password_policy"

    def collect(self, session, region_name: str) -> CollectionResult:
        client = session.client("iam")
        try:
            response = client.get_account_password_policy()
            policy = response.get("PasswordPolicy", {})
            minimum_length = policy.get("MinimumPasswordLength", 0)
            passed = minimum_length >= 14 and policy.get("RequireSymbols", False) and policy.get("RequireNumbers", False)
            return CollectionResult(
                status="pass" if passed else "fail",
                summary=f"Password policy minimum length is {minimum_length}",
                payload=policy,
            )
        except (ClientError, BotoCoreError) as exc:
            return _normalize_error(exc)


class CloudTrailCollector(BaseCollector):
    key = "cloudtrail.multi_region_trail"

    def collect(self, session, region_name: str) -> CollectionResult:
        client = session.client("cloudtrail", region_name=region_name)
        try:
            trails = client.describe_trails(includeShadowTrails=False).get("trailList", [])
            multi_region = [trail for trail in trails if trail.get("IsMultiRegionTrail")]
            return CollectionResult(
                status="pass" if multi_region else "fail",
                summary=f"Found {len(multi_region)} multi-region CloudTrail trail(s)",
                payload={"trails": trails},
            )
        except (ClientError, BotoCoreError) as exc:
            return _normalize_error(exc)


class ConfigRecorderCollector(BaseCollector):
    key = "config.recorder"

    def collect(self, session, region_name: str) -> CollectionResult:
        client = session.client("config", region_name=region_name)
        try:
            recorders = client.describe_configuration_recorders().get("ConfigurationRecorders", [])
            status = client.describe_configuration_recorder_status().get("ConfigurationRecordersStatus", [])
            running = any(item.get("recording") for item in status)
            return CollectionResult(
                status="pass" if recorders and running else "fail",
                summary=f"Found {len(recorders)} configuration recorder(s); running={running}",
                payload={"recorders": recorders, "status": status},
            )
        except (ClientError, BotoCoreError) as exc:
            return _normalize_error(exc)


class GuardDutyCollector(BaseCollector):
    key = "guardduty.enabled"

    def collect(self, session, region_name: str) -> CollectionResult:
        client = session.client("guardduty", region_name=region_name)
        try:
            detector_ids = client.list_detectors().get("DetectorIds", [])
            return CollectionResult(
                status="pass" if detector_ids else "fail",
                summary=f"Found {len(detector_ids)} GuardDuty detector(s)",
                payload={"detector_ids": detector_ids},
            )
        except (ClientError, BotoCoreError) as exc:
            return _normalize_error(exc)


class SecurityHubCollector(BaseCollector):
    key = "securityhub.enabled"

    def collect(self, session, region_name: str) -> CollectionResult:
        client = session.client("securityhub", region_name=region_name)
        try:
            hubs = client.describe_hub()
            return CollectionResult(
                status="pass",
                summary="Security Hub is enabled",
                payload=hubs,
            )
        except (ClientError, BotoCoreError) as exc:
            return _normalize_error(exc)


class S3BucketEncryptionCollector(BaseCollector):
    key = "s3.bucket_encryption"

    def collect(self, session, region_name: str) -> CollectionResult:
        client = session.client("s3", region_name=region_name)
        try:
            buckets = client.list_buckets().get("Buckets", [])
            encrypted = []
            unencrypted = []
            for bucket in buckets:
                name = bucket["Name"]
                try:
                    client.get_bucket_encryption(Bucket=name)
                    encrypted.append(name)
                except ClientError:
                    unencrypted.append(name)
            passed = not unencrypted
            return CollectionResult(
                status="pass" if passed else "fail",
                summary=f"{len(encrypted)} encrypted bucket(s), {len(unencrypted)} bucket(s) without default encryption",
                payload={"encrypted": encrypted, "unencrypted": unencrypted},
            )
        except (ClientError, BotoCoreError) as exc:
            return _normalize_error(exc)


class EbsEncryptionCollector(BaseCollector):
    key = "ec2.ebs_default_encryption"

    def collect(self, session, region_name: str) -> CollectionResult:
        client = session.client("ec2", region_name=region_name)
        try:
            response = client.get_ebs_encryption_by_default()
            enabled = response.get("EbsEncryptionByDefault", False)
            return CollectionResult(
                status="pass" if enabled else "fail",
                summary=f"EBS default encryption enabled={enabled}",
                payload=response,
            )
        except (ClientError, BotoCoreError) as exc:
            return _normalize_error(exc)


COLLECTORS = {
    IAMPasswordPolicyCollector.key: IAMPasswordPolicyCollector(),
    CloudTrailCollector.key: CloudTrailCollector(),
    ConfigRecorderCollector.key: ConfigRecorderCollector(),
    GuardDutyCollector.key: GuardDutyCollector(),
    SecurityHubCollector.key: SecurityHubCollector(),
    S3BucketEncryptionCollector.key: S3BucketEncryptionCollector(),
    EbsEncryptionCollector.key: EbsEncryptionCollector(),
}

