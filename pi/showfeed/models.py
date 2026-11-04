from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    APPROVED = "approved"
    HOLD = "hold"


@dataclass
class TriageResult:
    decision: Decision
    reason: str
