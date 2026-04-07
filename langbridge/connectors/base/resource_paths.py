from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


class ApiResourceCardinality(str, Enum):
    ONE = "one"
    MANY = "many"


@dataclass(frozen=True, slots=True)
class ApiChildResource:
    name: str
    path: str
    parent_path: str
    cardinality: ApiResourceCardinality
    supports_flattening: bool
    addressable: bool = True


@dataclass(frozen=True, slots=True)
class ApiMaterializedRows:
    resource_path: str
    root_resource: str
    parent_path: str | None
    cardinality: ApiResourceCardinality
    rows: list[dict[str, Any]]
    child_resources: tuple[ApiChildResource, ...] = ()


@dataclass(frozen=True, slots=True)
class _TraversalNode:
    value: Any
    parent_id: Any
    current_id: Any
    child_index: int | None = None


def normalize_api_resource_path(resource_path: str) -> str:
    segments = [segment.strip() for segment in str(resource_path or "").split(".") if segment.strip()]
    if not segments:
        raise ValueError("API resource path must not be empty.")
    return ".".join(segments)


def api_resource_root(resource_path: str) -> str:
    normalized = normalize_api_resource_path(resource_path)
    return normalized.split(".", 1)[0]


def api_parent_resource_path(resource_path: str) -> str | None:
    normalized = normalize_api_resource_path(resource_path)
    if "." not in normalized:
        return None
    return normalized.rsplit(".", 1)[0]


def normalize_api_flatten_paths(paths: Iterable[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_path in list(paths or []):
        path = normalize_api_resource_path(str(raw_path or ""))
        if path in seen:
            continue
        seen.add(path)
        normalized.append(path)
    return normalized


def describe_api_child_resources(
    *,
    resource_path: str,
    records: list[Mapping[str, Any]],
) -> tuple[ApiChildResource, ...]:
    normalized_resource_path = normalize_api_resource_path(resource_path)
    descriptors: dict[str, ApiChildResource] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        _collect_child_resources(
            value=record,
            parent_path=normalized_resource_path,
            descriptors=descriptors,
        )
    return tuple(sorted(descriptors.values(), key=lambda item: item.path))


def materialize_api_resource_rows(
    *,
    resource_path: str,
    records: list[Mapping[str, Any]],
    primary_key: str | None = "id",
    flatten: Iterable[str] | None = None,
) -> ApiMaterializedRows:
    normalized_resource_path = normalize_api_resource_path(resource_path)
    flatten_paths = normalize_api_flatten_paths(flatten)
    root_resource = api_resource_root(normalized_resource_path)
    relative_segments = normalized_resource_path.split(".")[1:]
    parent_path = api_parent_resource_path(normalized_resource_path)

    traversal_nodes = _initial_traversal_nodes(records=records, primary_key=primary_key)
    terminal_cardinality = ApiResourceCardinality.MANY

    for depth, segment in enumerate(relative_segments):
        step_path = ".".join([root_resource, *relative_segments[: depth + 1]])
        traversal_nodes, terminal_cardinality = _descend_traversal_nodes(
            nodes=traversal_nodes,
            segment=segment,
            step_path=step_path,
        )

    materialized_rows: list[dict[str, Any]] = []
    for node in traversal_nodes:
        row = _materialize_value(
            value=node.value,
            flatten_paths=flatten_paths,
            context_path=normalized_resource_path,
            selected_path="",
        )
        if relative_segments:
            row["_parent_id"] = node.parent_id
            if node.child_index is not None:
                row["_child_index"] = node.child_index
        materialized_rows.append(row)

    return ApiMaterializedRows(
        resource_path=normalized_resource_path,
        root_resource=root_resource,
        parent_path=parent_path,
        cardinality=terminal_cardinality,
        rows=materialized_rows,
        child_resources=describe_api_child_resources(
            resource_path=normalized_resource_path,
            records=[
                node.value
                for node in traversal_nodes
                if isinstance(node.value, Mapping)
            ],
        ),
    )


def _initial_traversal_nodes(
    *,
    records: list[Mapping[str, Any]],
    primary_key: str | None,
) -> list[_TraversalNode]:
    nodes: list[_TraversalNode] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            continue
        record_identity = record.get(primary_key or "id")
        if record_identity in {None, ""}:
            record_identity = index
        nodes.append(
            _TraversalNode(
                value=record,
                parent_id=None,
                current_id=record_identity,
            )
        )
    return nodes


def _descend_traversal_nodes(
    *,
    nodes: list[_TraversalNode],
    segment: str,
    step_path: str,
) -> tuple[list[_TraversalNode], ApiResourceCardinality]:
    next_nodes: list[_TraversalNode] = []
    seen_cardinalities: set[ApiResourceCardinality] = set()

    for node in nodes:
        if not isinstance(node.value, Mapping):
            continue
        child_value = node.value.get(segment)
        if child_value is None:
            continue
        if isinstance(child_value, list):
            seen_cardinalities.add(ApiResourceCardinality.MANY)
            for child_index, item in enumerate(child_value):
                child_identity = _coerce_child_identity(item, fallback=node.current_id)
                next_nodes.append(
                    _TraversalNode(
                        value=item,
                        parent_id=node.current_id,
                        current_id=child_identity,
                        child_index=child_index,
                    )
                )
            continue
        seen_cardinalities.add(ApiResourceCardinality.ONE)
        child_identity = _coerce_child_identity(child_value, fallback=node.current_id)
        next_nodes.append(
            _TraversalNode(
                value=child_value,
                parent_id=node.current_id,
                current_id=child_identity,
            )
        )

    if not next_nodes and nodes:
        raise ValueError(f"API resource path '{step_path}' does not exist in the extracted records.")
    if len(seen_cardinalities) > 1:
        raise ValueError(
            f"API resource path '{step_path}' is structurally inconsistent across records."
        )
    if seen_cardinalities:
        cardinality = next(iter(seen_cardinalities))
    else:
        cardinality = ApiResourceCardinality.ONE
    return next_nodes, cardinality


def _collect_child_resources(
    *,
    value: Any,
    parent_path: str,
    descriptors: dict[str, ApiChildResource],
) -> None:
    if not isinstance(value, Mapping):
        return
    for raw_key, child_value in value.items():
        child_name = str(raw_key or "").strip()
        if not child_name:
            continue
        child_path = f"{parent_path}.{child_name}"
        if isinstance(child_value, list):
            descriptors[child_path] = ApiChildResource(
                name=child_name,
                path=child_path,
                parent_path=parent_path,
                cardinality=ApiResourceCardinality.MANY,
                supports_flattening=False,
            )
            for item in child_value:
                if isinstance(item, Mapping):
                    _collect_child_resources(
                        value=item,
                        parent_path=child_path,
                        descriptors=descriptors,
                    )
            continue
        if isinstance(child_value, Mapping):
            descriptors[child_path] = ApiChildResource(
                name=child_name,
                path=child_path,
                parent_path=parent_path,
                cardinality=ApiResourceCardinality.ONE,
                supports_flattening=True,
            )
            _collect_child_resources(
                value=child_value,
                parent_path=child_path,
                descriptors=descriptors,
            )


def _materialize_value(
    *,
    value: Any,
    flatten_paths: list[str],
    context_path: str,
    selected_path: str,
) -> dict[str, Any]:
    if isinstance(value, Mapping):
        row: dict[str, Any] = {}
        for raw_key, child_value in value.items():
            child_name = str(raw_key or "").strip()
            if not child_name:
                continue
            next_selected_path = child_name if not selected_path else f"{selected_path}.{child_name}"
            field_prefix = child_name if not selected_path else selected_path.replace(".", "__") + f"__{child_name}"
            if isinstance(child_value, Mapping):
                if next_selected_path in flatten_paths:
                    _flatten_mapping(
                        payload=child_value,
                        row=row,
                        field_prefix=field_prefix,
                    )
                continue
            if isinstance(child_value, list):
                if next_selected_path in flatten_paths:
                    raise ValueError(
                        f"API flatten path '{next_selected_path}' cannot flatten a one-to-many child."
                    )
                continue
            row[child_name if not selected_path else field_prefix] = child_value
        return row
    return {"value": value}


def _flatten_mapping(
    *,
    payload: Mapping[str, Any],
    row: dict[str, Any],
    field_prefix: str,
) -> None:
    for raw_key, value in payload.items():
        child_name = str(raw_key or "").strip()
        if not child_name:
            continue
        column_name = f"{field_prefix}__{child_name}"
        if isinstance(value, Mapping):
            _flatten_mapping(
                payload=value,
                row=row,
                field_prefix=column_name,
            )
            continue
        if isinstance(value, list):
            raise ValueError(
                f"API flatten path '{field_prefix.replace('__', '.')}' cannot flatten a one-to-many child."
            )
        row[column_name] = value


def _coerce_child_identity(value: Any, *, fallback: Any) -> Any:
    if isinstance(value, Mapping):
        candidate = value.get("id")
        if candidate not in {None, ""}:
            return candidate
    return fallback
