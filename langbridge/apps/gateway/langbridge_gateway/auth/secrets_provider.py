"""Secrets provider stub for tenant database credentials."""
from __future__ import annotations

from typing import Any


# TODO: Replace with real secrets backend (Vault/ASM/etc.).

def get_db_credentials(tenant_id: str, source_id: str | None) -> dict[str, Any]:
    """Return connection attributes for the given tenant/source pair."""
    return {
        "user": f"tenant:{tenant_id}",
        "catalog": None,
        "schema": None,
        "extra_credentials": {
            "tenant": tenant_id,
            "source": source_id or "",
        },
    }
