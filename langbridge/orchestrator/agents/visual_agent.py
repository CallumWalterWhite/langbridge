"""
Visualization agent that converts tabular data into declarative chart specifications.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

try:  # pragma: no cover - optional dependency
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pd = None  # type: ignore


TabularInput = Union[Dict[str, Any], List[Dict[str, Any]], "pd.DataFrame"]  # type: ignore[name-defined]


def _to_dataframe(data: TabularInput) -> "pd.DataFrame":  # type: ignore[name-defined]
    if pd is None:  # pragma: no cover - optional dependency
        raise ImportError("pandas is required to convert data into a DataFrame.")

    if isinstance(data, dict):
        if "columns" in data and "rows" in data:
            return pd.DataFrame(data["rows"], columns=data["columns"])
        return pd.DataFrame([data])
    if isinstance(data, list):
        return pd.DataFrame(data)
    if isinstance(data, pd.DataFrame):
        return data.copy()

    raise TypeError("Unsupported tabular input. Provide a DataFrame, list of dicts, or {columns, rows}.")


@dataclass
class VisualizationSpec:
    """
    Declarative visualization specification.
    """

    chart_type: str
    x: Optional[str] = None
    y: Optional[Union[str, Sequence[str]]] = None
    group_by: Optional[str] = None
    title: Optional[str] = None
    options: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "chart_type": self.chart_type,
            "x": self.x,
            "y": self.y,
            "group_by": self.group_by,
            "title": self.title,
        }
        if self.options:
            payload["options"] = self.options
        return {k: v for k, v in payload.items() if v is not None}


class VisualAgent:
    """
    Lightweight agent that infers a visualization configuration for tabular results.
    """

    def __init__(self, *, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    @staticmethod
    def _numeric_columns(df: "pd.DataFrame") -> List[str]:  # type: ignore[name-defined]
        return [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]

    @staticmethod
    def _categorical_columns(df: "pd.DataFrame") -> List[str]:  # type: ignore[name-defined]
        return [col for col in df.columns if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_categorical_dtype(df[col])]

    def _choose_chart(self, df: "pd.DataFrame") -> VisualizationSpec:  # type: ignore[name-defined]
        numeric_cols = self._numeric_columns(df)
        categorical_cols = self._categorical_columns(df)

        chart_type = "table"
        x = y = group_by = None

        if len(numeric_cols) >= 2 and len(df) > 10:
            chart_type = "scatter"
            x, y = numeric_cols[:2]
        elif len(numeric_cols) >= 1 and len(categorical_cols) >= 1:
            chart_type = "bar"
            x = categorical_cols[0]
            y = numeric_cols[0]
            if len(categorical_cols) > 1:
                group_by = categorical_cols[1]
        elif len(numeric_cols) == 1 and "date" in " ".join(df.columns).lower():
            chart_type = "line"
            candidates = [col for col in df.columns if "date" in col.lower() or "time" in col.lower()]
            x = candidates[0] if candidates else df.columns[0]
            y = numeric_cols[0]
        elif len(numeric_cols) == 1:
            chart_type = "bar"
            x = df.columns[0]
            y = numeric_cols[0]
        elif len(df.columns) == 2 and len(df) <= 6:
            chart_type = "pie"
            x, y = df.columns
        else:
            chart_type = "table"

        return VisualizationSpec(
            chart_type=chart_type,
            x=x,
            y=y,
            group_by=group_by,
            title=None,
            options={"row_count": len(df)},
        )

    def run(self, data: TabularInput, *, title: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a visualization specification for the provided tabular data.
        """
        self.logger.info("VisualAgent.run invoked with data type %s", type(data).__name__)
        df = _to_dataframe(data)
        spec = self._choose_chart(df)
        if title:
            spec.title = title
        elif spec.chart_type != "table":
            spec.title = "Automated insight"
        return spec.to_dict()


if __name__ == "__main__":  # pragma: no cover - demonstration only
    sample_data = [
        {"month": "2024-01", "revenue": 12000, "region": "North"},
        {"month": "2024-01", "revenue": 15000, "region": "South"},
        {"month": "2024-02", "revenue": 18000, "region": "North"},
        {"month": "2024-02", "revenue": 17000, "region": "South"},
    ]

    agent = VisualAgent()
    spec = agent.run(sample_data, title="Monthly revenue by region")
    print(spec)
