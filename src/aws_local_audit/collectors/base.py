from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class CollectionResult:
    status: str
    summary: str
    payload: dict[str, Any]


class BaseCollector:
    key = ""

    def collect(self, session, region_name: str) -> CollectionResult:
        raise NotImplementedError

