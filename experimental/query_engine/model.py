"""Core data structures for the LangBridge experimental query engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple, Union

PredicateOperand = Union["ColumnRef", "Literal"]


@dataclass(frozen=True)
class ColumnRef:
    """Reference to a column in a table."""

    table_alias: str
    column: str


@dataclass(frozen=True)
class Literal:
    """A literal constant used in predicates."""

    value: Any


@dataclass(frozen=True)
class Predicate:
    """Represents a boolean predicate."""

    left: PredicateOperand
    operator: str
    right: PredicateOperand


@dataclass(frozen=True)
class Wildcard:
    """Represents a wildcard select item such as ``*`` or ``alias.*``."""

    table_alias: Optional[str] = None


@dataclass(frozen=True)
class SelectItem:
    """A single item in the SELECT list."""

    value: Union[ColumnRef, Wildcard]
    alias: Optional[str] = None


@dataclass(frozen=True)
class TableReference:
    """Reference to a table in a specific data source."""

    source: str
    path: Tuple[str, ...]
    alias: str


@dataclass(frozen=True)
class JoinClause:
    """Represents a JOIN clause."""

    join_type: str
    table: TableReference
    predicates: Sequence[Predicate]


@dataclass(frozen=True)
class SelectQuery:
    """Structured representation of a parsed select statement."""

    select_items: Sequence[SelectItem]
    from_table: TableReference
    joins: Sequence[JoinClause]
    where_predicates: Sequence[Predicate]


__all__ = [
    "ColumnRef",
    "JoinClause",
    "Literal",
    "Predicate",
    "PredicateOperand",
    "SelectItem",
    "SelectQuery",
    "TableReference",
    "Wildcard",
]
