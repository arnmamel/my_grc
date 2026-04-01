from __future__ import annotations

from pathlib import Path

import yaml


def template_directory() -> Path:
    return Path(__file__).parent / "templates" / "ai_packs"


def load_templates() -> list[dict]:
    packs = []
    for path in sorted(template_directory().glob("*.yaml")):
        packs.append(yaml.safe_load(path.read_text(encoding="utf-8")))
    return packs


def load_template_by_code(pack_code: str) -> dict:
    normalized = (pack_code or "").strip().upper()
    for item in load_templates():
        if item.get("pack_code", "").strip().upper() == normalized:
            return item
    raise ValueError(f"AI knowledge pack template not found: {pack_code}")
