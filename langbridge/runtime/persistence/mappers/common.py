from __future__ import annotations

import json
from typing import Any


def as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(exclude_none=True)
        return dumped if isinstance(dumped, dict) else {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def resolve_org_id(value: Any) -> Any:
    if getattr(value, "organization_id", None) is not None:
        return value.organization_id
    organizations = getattr(value, "organizations", None) or []
    if organizations:
        return getattr(organizations[0], "id", None)
    return None


def resolve_project_id(value: Any) -> Any:
    if getattr(value, "project_id", None) is not None:
        return value.project_id
    projects = getattr(value, "projects", None) or []
    if projects:
        return getattr(projects[0], "id", None)
    return None


__all__ = ["as_dict", "resolve_org_id", "resolve_project_id"]
