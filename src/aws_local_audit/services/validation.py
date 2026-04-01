from __future__ import annotations

import re


class ValidationError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


def validate_feedback_payload(*, subject: str, message: str) -> None:
    issues = []
    if len(subject.strip()) < 4:
        issues.append("Subject must contain at least 4 characters.")
    if len(message.strip()) < 12:
        issues.append("Suggestion or issue body must contain at least 12 characters.")
    if issues:
        raise ValidationError(issues)


def validate_workspace_password(password: str, *, minimum_length: int = 12) -> None:
    issues = []
    if len(password) < minimum_length:
        issues.append(f"Password must contain at least {minimum_length} characters.")
    if password.lower() == password or password.upper() == password:
        issues.append("Password must mix upper and lower case characters.")
    if not any(character.isdigit() for character in password):
        issues.append("Password must include at least one number.")
    if not any(not character.isalnum() for character in password):
        issues.append("Password must include at least one symbol.")
    if issues:
        raise ValidationError(issues)


def validate_principal_key(principal_key: str) -> str:
    normalized = principal_key.strip().lower()
    if not normalized:
        raise ValidationError(["Principal key is required."])
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,149}", normalized):
        raise ValidationError(
            ["Principal key must start with a letter or number and then use only lowercase letters, digits, `.`, `_`, or `-`."]
        )
    return normalized


def validate_backup_label(label: str) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "-", label.strip().lower()).strip("-")
    if not normalized:
        raise ValidationError(["Backup label is required."])
    if len(normalized) > 64:
        raise ValidationError(["Backup label must not exceed 64 characters after normalization."])
    return normalized
