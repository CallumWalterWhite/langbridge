from __future__ import annotations

import hashlib
from typing import Dict, List, Optional

from langbridge.packages.orchestrator.langbridge_orchestrator.agents.planner.models import RouteName

from .schemas import ClarificationDecision, ClarificationState, ClassifiedQuestion, ResolvedEntities


_ROUTE_BLOCKING_SLOTS: Dict[str, List[str]] = {
    RouteName.SIMPLE_ANALYST.value: ["fund", "region", "time_period", "metric"],
    RouteName.ANALYST_THEN_VISUAL.value: ["fund", "region", "time_period", "metric"],
}


class ClarificationManager:
    """Clarification state machine with dedupe + max-turn safeguards."""

    def __init__(self, *, default_max_turns: int = 2) -> None:
        self._default_max_turns = max(1, int(default_max_turns))

    def decide(
        self,
        *,
        question: str,
        classification: ClassifiedQuestion,
        entities: ResolvedEntities,
        prior_state: Optional[ClarificationState],
    ) -> ClarificationDecision:
        state = prior_state.model_copy(deep=True) if prior_state else ClarificationState()
        if state.max_turns < 1:
            state.max_turns = self._default_max_turns

        answered = entities.slot_values()
        if answered:
            state.answered_slots.update(answered)

        blocking_slots = self._blocking_slots_for_route(classification.route_hint)
        if not blocking_slots:
            state.pending_slots = []
            return ClarificationDecision(updated_state=state)

        missing_slots = [slot for slot in blocking_slots if not state.answered_slots.get(slot)]
        state.pending_slots = list(missing_slots)

        if not missing_slots:
            return ClarificationDecision(updated_state=state)

        unasked_missing = [slot for slot in missing_slots if slot not in state.asked_slots]
        should_ask = bool(unasked_missing) and state.turn_count < state.max_turns

        if should_ask:
            clarifying_question = self._build_question(unasked_missing, state)
            question_hash = self._question_hash(clarifying_question)
            if question_hash == state.last_question_hash or clarifying_question in state.asked_questions:
                assumptions = self._assumptions_for_slots(missing_slots)
                state.assumptions.extend([item for item in assumptions if item not in state.assumptions])
                return ClarificationDecision(
                    requires_clarification=False,
                    missing_blocking_slots=missing_slots,
                    assumptions=assumptions,
                    updated_state=state,
                )

            state.turn_count += 1
            state.asked_slots.extend([slot for slot in unasked_missing if slot not in state.asked_slots])
            state.asked_questions.append(clarifying_question)
            state.last_question_hash = question_hash
            return ClarificationDecision(
                requires_clarification=True,
                clarifying_question=clarifying_question,
                missing_blocking_slots=missing_slots,
                updated_state=state,
            )

        assumptions = self._assumptions_for_slots(missing_slots)
        state.assumptions.extend([item for item in assumptions if item not in state.assumptions])
        return ClarificationDecision(
            requires_clarification=False,
            missing_blocking_slots=missing_slots,
            assumptions=assumptions,
            updated_state=state,
        )

    @staticmethod
    def _question_hash(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _blocking_slots_for_route(route_hint: Optional[str]) -> List[str]:
        if not route_hint:
            return list(_ROUTE_BLOCKING_SLOTS[RouteName.SIMPLE_ANALYST.value])
        return list(_ROUTE_BLOCKING_SLOTS.get(route_hint, []))

    @staticmethod
    def _build_question(missing_slots: List[str], state: ClarificationState) -> str:
        labels: Dict[str, str] = {
            "fund": "the specific fund name or id",
            "region": "the region scope",
            "time_period": "the exact time period",
            "metric": "the performance metric (for example total return or net return)",
            "currency": "the reporting currency",
            "benchmark": "whether to include benchmark comparison",
        }
        missing_parts = [labels.get(slot, slot) for slot in missing_slots]
        prompt = "To proceed, please provide " + " and ".join(missing_parts) + "."

        if "fund" in missing_slots:
            prompt += " Example: 'for Global Equity Fund'."
        elif "time_period" in missing_slots:
            prompt += " Example: 'for 2024 Q1'."
        elif "metric" in missing_slots:
            prompt += " Example: 'use total return'."

        return prompt

    @staticmethod
    def _assumptions_for_slots(missing_slots: List[str]) -> List[str]:
        assumptions: List[str] = []
        for slot in missing_slots:
            if slot == "fund":
                assumptions.append("Assuming all funds because a specific fund was not provided.")
            elif slot == "region":
                assumptions.append("Assuming all regions.")
            elif slot == "time_period":
                assumptions.append("Assuming the most recent complete reporting period.")
            elif slot == "metric":
                assumptions.append("Assuming total return as the performance metric.")
            elif slot == "currency":
                assumptions.append("Assuming source-system base currency.")
            elif slot == "benchmark":
                assumptions.append("Assuming benchmark comparison is not required.")
        return assumptions


__all__ = ["ClarificationManager"]
