"""Logical plan construction for the LangBridge experimental query engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .datasource import DataSourceRegistry
from .exceptions import QueryPlanningError
from .model import JoinClause, Predicate, SelectItem, SelectQuery, TableReference


class PlanNode:
    """Base class for plan nodes."""


@dataclass
class ScanNode(PlanNode):
    table: TableReference


@dataclass
class JoinNode(PlanNode):
    left: PlanNode
    right: PlanNode
    predicates: Sequence[Predicate]
    join_type: str = "INNER"


@dataclass
class FilterNode(PlanNode):
    input: PlanNode
    predicates: Sequence[Predicate]


@dataclass
class ProjectionNode(PlanNode):
    input: PlanNode
    select_items: Sequence[SelectItem]


class QueryPlanner:
    """Transform :class:`SelectQuery` instances into execution plans."""

    def __init__(self, registry: DataSourceRegistry):
        self._registry = registry

    def plan(self, query: SelectQuery) -> ProjectionNode:
        if not self._registry.has_source(query.from_table.source):
            raise QueryPlanningError(f"Unknown data source {query.from_table.source!r}")

        plan: PlanNode = ScanNode(table=query.from_table)

        for join in query.joins:
            if not self._registry.has_source(join.table.source):
                raise QueryPlanningError(f"Unknown data source {join.table.source!r}")
            if join.join_type != "INNER":
                raise QueryPlanningError(f"Unsupported join type {join.join_type!r}")
            plan = JoinNode(left=plan, right=ScanNode(join.table), predicates=join.predicates)

        if query.where_predicates:
            plan = FilterNode(input=plan, predicates=query.where_predicates)

        return ProjectionNode(input=plan, select_items=query.select_items)


__all__ = [
    "FilterNode",
    "JoinNode",
    "PlanNode",
    "ProjectionNode",
    "QueryPlanner",
    "ScanNode",
]
