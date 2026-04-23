from langbridge.runtime.services.agent_run_tool_factory import _SemanticScopeExecutor


def test_semantic_scope_executor_marks_binder_type_failures_as_scope_fallback_eligible() -> None:
    failure = _SemanticScopeExecutor._semantic_failure(
        RuntimeError(
            "Binder Error: Cannot compare values of type VARCHAR and type DATE - an explicit cast is required"
        )
    )

    assert failure.stage.value == "execution"
    assert failure.recoverable is False
    assert failure.metadata["scope_fallback_eligible"] is True
    assert failure.metadata["semantic_failure_kind"] == "semantic_runtime_type_mismatch"
