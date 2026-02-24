import pytest

from langbridge.apps.gateway.langbridge_gateway.config import UpstreamTarget
from langbridge.apps.gateway.langbridge_gateway import routing


def test_route_database_prefers_exact_tenant_source_key(monkeypatch: pytest.MonkeyPatch) -> None:
    default_target = UpstreamTarget(host="default.local", port=5432, database="default_db")
    source_target = UpstreamTarget(host="source.local", port=5432, database="source_db")
    monkeypatch.setattr(
        routing,
        "POSTGRES_UPSTREAMS",
        {
            "tenant_a": default_target,
            "tenant_a__warehouse": source_target,
        },
    )

    resolved = routing.route_database("tenant_a__warehouse", "postgres")
    assert resolved == source_target


def test_route_database_can_use_user_identity_when_database_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_target = UpstreamTarget(host="tenant.local", port=3306, database="ordersdb")
    monkeypatch.setattr(
        routing,
        "MYSQL_UPSTREAMS",
        {
            "tenant_b": tenant_target,
        },
    )

    resolved = routing.route_database(
        "",
        "mysql",
        user_name="tenant:tenant_b;source:sales;user:trino",
    )
    assert resolved == tenant_target


def test_route_database_keeps_prefix_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    prefixed_target = UpstreamTarget(host="prefix.local", port=5432, database="customersdb")
    monkeypatch.setattr(
        routing,
        "POSTGRES_UPSTREAMS",
        {
            "tenant_c": prefixed_target,
        },
    )

    resolved = routing.route_database("tenant_c_reporting", "postgres")
    assert resolved == prefixed_target


def test_route_database_raises_when_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routing, "POSTGRES_UPSTREAMS", {})

    with pytest.raises(ValueError, match="Unknown tenant/source"):
        routing.route_database("missing_tenant", "postgres")


def test_route_database_uses_wildcard_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    wildcard_target = UpstreamTarget(host="shared.local", port=5432, database="langbridge")
    monkeypatch.setattr(
        routing,
        "POSTGRES_UPSTREAMS",
        {
            "*": wildcard_target,
        },
    )

    resolved = routing.route_database("any_tenant", "postgres")
    assert resolved == wildcard_target
