"""
Deep research agent that synthesizes document/contextual signals into insights.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class DeepResearchFinding:
    """Single insight surfaced by the deep research agent."""

    insight: str
    source: str = "knowledge_base"
    confidence: str = "medium"
    detail: Optional[str] = None

    def to_row(self) -> List[str]:
        return [self.insight, self.source, self.confidence]


@dataclass
class DeepResearchResult:
    """Aggregated result returned by the deep research agent."""

    question: str
    synthesis: str
    findings: List[DeepResearchFinding] = field(default_factory=list)
    follow_ups: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "synthesis": self.synthesis,
            "findings": [
                {
                    "insight": finding.insight,
                    "source": finding.source,
                    "confidence": finding.confidence,
                    "detail": finding.detail,
                }
                for finding in self.findings
            ],
            "follow_ups": list(self.follow_ups),
        }

    def to_tabular(self) -> Dict[str, Any]:
        """Coerce findings into the tabular payload format expected by consumers."""

        if not self.findings:
            return {
                "columns": ["insight"],
                "rows": [[self.synthesis]],
            }

        return {
            "columns": ["insight", "source", "confidence"],
            "rows": [finding.to_row() for finding in self.findings],
        }


class DeepResearchAgent:
    """
    Basic deep research agent that reformats contextual snippets into synthesised insights.
    """

    def __init__(self, *, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    async def research_async(
        self,
        question: str,
        *,
        context: Optional[Dict[str, Any]] = None,
        timebox_seconds: int = 30,
    ) -> DeepResearchResult:
        """
        Gather and synthesise findings from the provided context.
        """

        # The current implementation is synchronous; run it in a worker to keep the interface async-ready.
        return await asyncio.to_thread(
            self._run_research,
            question,
            context or {},
            timebox_seconds,
        )

    # The synchronous research implementation is split out for easier testing.
    def _run_research(
        self,
        question: str,
        context: Dict[str, Any],
        timebox_seconds: int,
    ) -> DeepResearchResult:
        documents = self._extract_documents(context)
        findings = self._build_findings(question, documents)
        synthesis = self._compose_synthesis(question, findings, timebox_seconds, documents)
        follow_ups = self._suggest_follow_ups(question, findings)

        self.logger.info(
            "DeepResearchAgent synthesised %s finding(s) for question '%s'",
            len(findings),
            question,
        )

        return DeepResearchResult(
            question=question,
            synthesis=synthesis,
            findings=findings,
            follow_ups=follow_ups,
        )

    def _extract_documents(self, context: Dict[str, Any]) -> Sequence[Dict[str, Any]]:
        documents = context.get("documents") or context.get("sources") or context.get("notes") or []
        if isinstance(documents, dict):
            return [documents]
        if not isinstance(documents, Sequence):
            return []
        normalised: List[Dict[str, Any]] = []
        for doc in documents:
            if isinstance(doc, dict):
                normalised.append(doc)
        return normalised

    def _build_findings(
        self,
        question: str,
        documents: Sequence[Dict[str, Any]],
    ) -> List[DeepResearchFinding]:
        findings: List[DeepResearchFinding] = []
        for doc in documents[:5]:
            title = str(doc.get("title") or doc.get("name") or "Document").strip()
            snippet = str(doc.get("summary") or doc.get("snippet") or doc.get("content") or "").strip()
            source = str(doc.get("source") or doc.get("url") or title or "document").strip()
            insight = snippet or f"Referenced {title} for '{question}'."
            findings.append(
                DeepResearchFinding(
                    insight=insight,
                    source=source,
                    confidence=str(doc.get("confidence", "medium")).lower(),
                    detail=title,
                )
            )

        if not findings:
            findings.append(
                DeepResearchFinding(
                    insight=f"No documents provided; focusing on strategic analysis of '{question}'.",
                    source="knowledge_base",
                    confidence="low",
                )
            )

        return findings

    def _compose_synthesis(
        self,
        question: str,
        findings: Sequence[DeepResearchFinding],
        timebox_seconds: int,
        documents: Sequence[Dict[str, Any]],
    ) -> str:
        doc_count = len(documents)
        lead_in = f"Reviewed {doc_count} document{'s' if doc_count != 1 else ''} within a {timebox_seconds}s window."
        highlights = "; ".join(finding.insight for finding in findings[:2])
        if highlights:
            return f"{lead_in} Key takeaways for '{question}': {highlights}"
        return f"{lead_in} No high-signal findings available for '{question}'."

    def _suggest_follow_ups(
        self,
        question: str,
        findings: Sequence[DeepResearchFinding],
    ) -> List[str]:
        follow_ups = [
            f"Validate the qualitative claims about '{question}' with supporting metrics.",
            "Collect additional source material if more depth is required.",
        ]
        if findings and all(finding.source == "knowledge_base" for finding in findings):
            follow_ups.append("Provide representative documents to improve synthesis fidelity.")
        return follow_ups


__all__ = ["DeepResearchAgent", "DeepResearchFinding", "DeepResearchResult"]
