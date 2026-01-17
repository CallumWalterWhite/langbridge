from collections import deque
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from semantic.errors import JoinPathError
from semantic.model import Relationship


@dataclass(frozen=True)
class JoinStep:
    relationship: Relationship
    left_table: str
    right_table: str


class JoinPlanner:
    def __init__(self, relationships: Optional[Iterable[Relationship]]) -> None:
        self._relationships: List[Relationship] = list(relationships or [])
        self._adjacency: Dict[str, List[Tuple[str, Relationship]]] = {}
        self._build_graph()

    def plan(self, base_table: str, required_tables: Set[str]) -> List[JoinStep]:
        if not required_tables:
            return []

        joined: Set[str] = {base_table}
        join_steps: List[JoinStep] = []

        for target in sorted(required_tables - {base_table}):
            path = self._find_path(base_table, target)
            for relationship in path:
                left, right = relationship.from_, relationship.to
                if left in joined and right in joined:
                    continue
                if left in joined:
                    join_steps.append(JoinStep(relationship=relationship, left_table=left, right_table=right))
                    joined.add(right)
                elif right in joined:
                    join_steps.append(JoinStep(relationship=relationship, left_table=right, right_table=left))
                    joined.add(left)
                else:
                    raise JoinPathError(
                        f"Join path for '{target}' does not connect to joined tables."
                    )

        return join_steps

    def _build_graph(self) -> None:
        for relationship in self._relationships:
            self._adjacency.setdefault(relationship.from_, []).append((relationship.to, relationship))
            self._adjacency.setdefault(relationship.to, []).append((relationship.from_, relationship))

    def _find_path(self, start: str, target: str) -> List[Relationship]:
        if start == target:
            return []

        visited: Set[str] = {start}
        queue: deque[Tuple[str, List[Relationship]]] = deque()
        queue.append((start, []))

        while queue:
            current, path = queue.popleft()
            for neighbor, relationship in self._adjacency.get(current, []):
                if neighbor in visited:
                    continue
                if neighbor == target:
                    return path + [relationship]
                visited.add(neighbor)
                queue.append((neighbor, path + [relationship]))

        raise JoinPathError(f"No join path between '{start}' and '{target}'.")
