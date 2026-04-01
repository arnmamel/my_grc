from __future__ import annotations

from pathlib import Path

import yaml


def template_directory() -> Path:
    return Path(__file__).parent / "templates" / "frameworks"


def load_templates() -> list[dict]:
    frameworks = []
    for path in sorted(template_directory().glob("*.yaml")):
        frameworks.append(yaml.safe_load(path.read_text(encoding="utf-8")))
    return frameworks


def load_template_by_code(code: str) -> dict:
    for item in load_templates():
        if item["code"] == code:
            return item
    raise ValueError(f"Framework template not found: {code}")
