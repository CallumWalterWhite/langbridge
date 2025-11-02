from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List

from .models import PlannerRequest


@dataclass(slots=True)
class PolicyNotes:
    """Non-blocking policy annotations surfaced with the plan."""

    risks: List[str] = field(default_factory=list)


_PII_PATTERNS: Iterable[re.Pattern[str]] = (
    re.compile(r"\b(ssn|social\s+security|national\s+insurance)\b", re.IGNORECASE),
    re.compile(r"\b(passport|driver'?s?\s+license)\b", re.IGNORECASE),
    re.compile(r"\b(credit\s*card|cvv|iban|routing\s+number)\b", re.IGNORECASE),
)

_CREDENTIAL_PATTERNS: Iterable[re.Pattern[str]] = (
    re.compile(r"\b(api|access|secret)\s*(key|token)\b", re.IGNORECASE),
    re.compile(r"\b(password|passphrase|login)\b", re.IGNORECASE),
)

_UNSAFE_SQL_PATTERNS: Iterable[re.Pattern[str]] = (
    re.compile(r"\bdrop\s+table\b", re.IGNORECASE),
    re.compile(r"\btruncate\s+table\b", re.IGNORECASE),
    re.compile(r"\bdelete\s+from\b", re.IGNORECASE),
)


def _collect_matches(question: str, patterns: Iterable[re.Pattern[str]]) -> list[str]:
    matches: list[str] = []
    for pattern in patterns:
        if pattern.search(question):
            matches.append(pattern.pattern)
    return matches


def check_policies(request: PlannerRequest) -> PolicyNotes:
    """
    Lightweight guardrails that annotate possible risks.

    The planner remains advisory: policy findings are returned as metadata
    without blocking plan generation. Downstream supervisors can escalate
    according to organisational policies.
    """

    text = request.question
    lower_question = text.lower()
    risks: list[str] = []

    if _pii := _collect_matches(lower_question, _PII_PATTERNS):
        risks.append("Possible PII detected; double-check before running downstream tools.")
    if _creds := _collect_matches(lower_question, _CREDENTIAL_PATTERNS):
        risks.append("User may be requesting credentials or secrets.")
    if _unsafe_sql := _collect_matches(lower_question, _UNSAFE_SQL_PATTERNS):
        risks.append("Potentially destructive SQL operation mentioned.")

    # Heuristic: highlight if the user explicitly requests raw SQL editing.
    if "raw sql" in lower_question and "explain" not in lower_question:
        risks.append("User requested raw SQL; verify permissions before execution.")

    return PolicyNotes(risks=risks)


__all__ = ["PolicyNotes", "check_policies"]

