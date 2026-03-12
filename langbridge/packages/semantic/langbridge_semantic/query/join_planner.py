from collections import deque
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from langbridge.packages.semantic.langbridge_semantic.errors import JoinPathError
from langbridge.packages.semantic.langbridge_semantic.model import Relationship


@dataclass(frozen=True)
class JoinStep:
    relationship: Relationship
    left_dataset: str
    right_dataset: str

    @property
    def left_table(self) -> str:
        return self.left_dataset

    @property
    def right_table(self) -> str:
        return self.right_dataset


class JoinPlanner:
    def __init__(self, relationships: Optional[Iterable[Relationship]]) -> None:
        self._relationships: List[Relationship] = list(relationships or [])
        self._adjacency: Dict[str, List[Tuple[str, Relationship]]] = {}
        self._build_graph()

    def plan(self, base_dataset: str, required_datasets: Set[str]) -> List[JoinStep]:
        if not required_datasets:
            return []

        joined: Set[str] = {base_dataset}
        join_steps: List[JoinStep] = []

        for target in sorted(required_datasets - {base_dataset}):
            path = self._find_path(base_dataset, target)
            for relationship in path:
                left, right = relationship.source_dataset, relationship.target_dataset
                if left in joined and right in joined:
                    continue
                if left in joined:
                    join_steps.append(JoinStep(relationship=relationship, left_dataset=left, right_dataset=right))
                    joined.add(right)
                elif right in joined:
                    join_steps.append(JoinStep(relationship=relationship, left_dataset=right, right_dataset=left))
                    joined.add(left)
                else:
                    raise JoinPathError(
                        f"Join path for '{target}' does not connect to joined tables."
                    )

        return join_steps

    def _build_graph(self) -> None:
        for relationship in self._relationships:
            self._adjacency.setdefault(relationship.source_dataset, []).append((relationship.target_dataset, relationship))
            self._adjacency.setdefault(relationship.target_dataset, []).append((relationship.source_dataset, relationship))

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
