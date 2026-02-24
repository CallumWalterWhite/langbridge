import asyncio
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace

if "pandas" not in sys.modules:
    pandas_stub = SimpleNamespace(
        DataFrame=type("DataFrame", (), {}),
        api=SimpleNamespace(
            types=SimpleNamespace(
                is_numeric_dtype=lambda _series: False,
                is_object_dtype=lambda _series: False,
                is_categorical_dtype=lambda _series: False,
            )
        ),
    )
    sys.modules["pandas"] = pandas_stub

if "trino" not in sys.modules:
    trino_stub = ModuleType("trino")
    trino_stub.dbapi = SimpleNamespace(connect=lambda *args, **kwargs: None)
    trino_auth_stub = ModuleType("trino.auth")
    trino_auth_stub.BasicAuthentication = lambda *args, **kwargs: None
    sys.modules["trino"] = trino_stub
    sys.modules["trino.auth"] = trino_auth_stub

REPO_ROOT = Path(__file__).resolve().parents[4]
PACKAGE_ROOT = REPO_ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from langbridge.packages.orchestrator.langbridge_orchestrator.agents.supervisor.clarification_manager import (  # noqa: E402
    ClarificationManager,
)
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.supervisor.entity_resolver import (  # noqa: E402
    EntityResolver,
)
from langbridge.packages.orchestrator.langbridge_orchestrator.agents.supervisor.question_classifier import (  # noqa: E402
    QuestionClassifier,
)


def test_question_classifier_routes_analytical_query_to_analyst() -> None:
    classifier = QuestionClassifier()
    result = asyncio.run(classifier.classify_async("Fund performance by region for 2024 Q1"))

    assert result.route_hint == "SimpleAnalyst"
    assert result.intent == "analytical"


def test_entity_resolver_extracts_core_slots() -> None:
    resolver = EntityResolver()
    entities = asyncio.run(resolver.resolve_async("Fund performance by region for 2024 Q1"))

    assert entities.region == "by region"
    assert entities.time_period == "2024 Q1"
    assert entities.metric == "performance"
    assert entities.fund is None


def test_clarification_manager_dedupes_repeated_question() -> None:
    classifier = QuestionClassifier()
    resolver = EntityResolver()
    manager = ClarificationManager(default_max_turns=2)

    question = "Fund performance by region for 2024 Q1"
    classification = asyncio.run(classifier.classify_async(question))
    entities = asyncio.run(resolver.resolve_async(question, classification=classification))

    first = manager.decide(
        question=question,
        classification=classification,
        entities=entities,
        prior_state=None,
    )
    assert first.requires_clarification is True
    assert first.clarifying_question is not None

    second = manager.decide(
        question=question,
        classification=classification,
        entities=entities,
        prior_state=first.updated_state,
    )

    assert second.requires_clarification is False
    assert any("Assuming all funds" in entry for entry in second.assumptions)


def test_regression_fund_performance_query_no_repeat_and_correct_route() -> None:
    classifier = QuestionClassifier()
    resolver = EntityResolver()
    manager = ClarificationManager(default_max_turns=2)

    question = "fund performance by region for 2024 Q1"
    classification = asyncio.run(classifier.classify_async(question))
    entities = asyncio.run(resolver.resolve_async(question, classification=classification))

    assert classification.route_hint == "SimpleAnalyst"

    first = manager.decide(
        question=question,
        classification=classification,
        entities=entities,
        prior_state=None,
    )
    assert first.requires_clarification is True

    second = manager.decide(
        question=question,
        classification=classification,
        entities=entities,
        prior_state=first.updated_state,
    )
    assert second.requires_clarification is False
    assert second.updated_state.turn_count == first.updated_state.turn_count
