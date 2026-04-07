import asyncio
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from langbridge.orchestrator.definitions import GuardrailConfig, OutputFormat, OutputSchema, PromptContract, ResponseMode  # noqa: E402
from langbridge.orchestrator.runtime import analysis_grounding  # noqa: E402
from langbridge.orchestrator.runtime.response_formatter import ResponseFormatter, ResponsePresentation  # noqa: E402
from langbridge.orchestrator.tools.sql_analyst.interfaces import (  # noqa: E402
    AnalystExecutionOutcome,
    AnalystOutcomeStage,
    AnalystOutcomeStatus,
    AnalystQueryResponse,
    QueryResult,
)


class _FailingProvider:
    async def ainvoke(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("fallback")


def _analyst_result(*, columns: list[str], rows: list[tuple[object, ...]]) -> AnalystQueryResponse:
    return AnalystQueryResponse(
        analysis_path="dataset",
        execution_mode="federated",
        asset_type="dataset",
        asset_id="sales_dataset",
        asset_name="sales",
        sql_canonical="select 1",
        sql_executable="select 1",
        dialect="postgres",
        result=QueryResult(
            columns=columns,
            rows=rows,
            rowcount=len(rows),
            elapsed_ms=12,
            source_sql="select 1",
        ),
        outcome=AnalystExecutionOutcome(
            status=AnalystOutcomeStatus.success if rows else AnalystOutcomeStatus.empty_result,
            stage=AnalystOutcomeStage.result,
            message=None if rows else "No rows matched the query.",
            recoverable=False,
            terminal=True,
        ),
    )


def _presentation(mode: ResponseMode) -> ResponsePresentation:
    return ResponsePresentation(
        prompt_contract=PromptContract(system_prompt="System prompt"),
        output_schema=OutputSchema(format=OutputFormat.text),
        guardrails=GuardrailConfig(),
        response_mode=mode,
    )


def test_analyst_summary_answers_direct_question_with_ranked_findings() -> None:
    payload = {"columns": ["region", "revenue"], "rows": [("US", 2200), ("EMEA", 1200), ("APAC", 800)]}
    summary = asyncio.run(
        ResponseFormatter().summarize_response(
            _FailingProvider(),  # type: ignore[arg-type]
            "Which region had the highest revenue?",
            {"analyst_result": _analyst_result(columns=payload["columns"], rows=payload["rows"]), "result": payload},
            presentation=_presentation(ResponseMode.analyst),
        )
    )

    assert "US" in summary
    assert "highest revenue" in summary.lower()
    assert "Found 3 rows across 2 columns" not in summary


def test_analyst_summary_calls_out_sparse_or_empty_results() -> None:
    payload = {"columns": ["region", "revenue"], "rows": []}
    summary = asyncio.run(
        ResponseFormatter().summarize_response(
            _FailingProvider(),  # type: ignore[arg-type]
            "Which region had the highest revenue?",
            {"analyst_result": _analyst_result(columns=payload["columns"], rows=[]), "result": payload},
            presentation=_presentation(ResponseMode.analyst),
        )
    )

    assert "No rows matched the query" in summary
    assert "grounded analytical" in summary


def test_non_analyst_modes_preserve_simple_summary_shape() -> None:
    payload = {"columns": ["region", "revenue"], "rows": [("US", 2200), ("EMEA", 1200), ("APAC", 800)]}
    summary = asyncio.run(
        ResponseFormatter().summarize_response(
            _FailingProvider(),  # type: ignore[arg-type]
            "Which region had the highest revenue?",
            {"analyst_result": _analyst_result(columns=payload["columns"], rows=payload["rows"]), "result": payload},
            presentation=_presentation(ResponseMode.executive),
        )
    )

    assert summary == "Found 3 rows across 2 columns for 'Which region had the highest revenue?'."


def test_analyst_grounding_falls_back_instead_of_throwing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise TypeError("'NoneType' object is not callable")

    monkeypatch.setattr(analysis_grounding, "_build_analyst_grounding", _boom)

    grounding = analysis_grounding.build_analyst_grounding(
        "Which region had the highest revenue?",
        {"columns": ["region", "revenue"], "rows": [("US", 2200)]},
    )

    assert grounding["analysis_type"] == "fallback"
    assert grounding["caveats"]
