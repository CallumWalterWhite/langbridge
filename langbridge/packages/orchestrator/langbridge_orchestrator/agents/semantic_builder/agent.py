"""Semantic builder agent that drafts canonical semantic model YAML from user-selected scope."""
import asyncio
import json
import logging
import re
import textwrap
from typing import Any, Dict, Iterable, Literal, Mapping, Optional

from pydantic import BaseModel, Field

from langbridge.packages.orchestrator.langbridge_orchestrator.llm.provider import LLMProvider
from langbridge.packages.semantic.langbridge_semantic.loader import SemanticModelError, load_semantic_model


class SemanticBuilderExample(BaseModel):
    """Example business question and optional SQL reference supplied by the user."""

    question: str = Field(..., min_length=1)
    sql_query: Optional[str] = None


class SemanticBuilderColumnSelection(BaseModel):
    """Column selected by the user when scoping the semantic model."""

    name: str = Field(..., min_length=1)
    data_type: Optional[str] = Field(default=None, description="Database data type string.")
    role: Literal["auto", "dimension", "measure"] = "auto"
    description: Optional[str] = None
    primary_key: bool = False
    aggregation: Optional[str] = None
    synonyms: list[str] = Field(default_factory=list)


class SemanticBuilderTableSelection(BaseModel):
    """Table selected by the user for inclusion in the semantic model."""

    key: Optional[str] = None
    schema: str = ""
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    synonyms: list[str] = Field(default_factory=list)
    columns: list[SemanticBuilderColumnSelection] = Field(default_factory=list)


class SemanticBuilderRelationshipHint(BaseModel):
    """Optional explicit join relationship supplied by the user."""

    from_table: str
    to_table: str
    join_on: str
    relation_type: str = "many_to_one"
    name: Optional[str] = None


class SemanticBuilderMetricHint(BaseModel):
    """Optional reusable metric supplied by the user."""

    name: str
    expression: str
    description: Optional[str] = None


class SemanticBuilderRequest(BaseModel):
    """Input contract for generating a draft semantic model YAML."""

    model_name: str = Field(..., min_length=1)
    description: Optional[str] = None
    connector: Optional[str] = None
    dialect: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    tables: list[SemanticBuilderTableSelection] = Field(default_factory=list)
    examples: list[SemanticBuilderExample] = Field(default_factory=list)
    relationships: list[SemanticBuilderRelationshipHint] = Field(default_factory=list)
    metrics: list[SemanticBuilderMetricHint] = Field(default_factory=list)
    conversation_context: Optional[str] = None


class SemanticBuilderResponse(BaseModel):
    """Draft semantic model payload returned to the UI."""

    semantic_model_yaml: str
    semantic_model: Dict[str, Any]
    actions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rationale: Optional[str] = None
    raw_model_response: Optional[str] = None


class SemanticBuilderAgent:
    """Generate semantic model YAML drafts from scoped table/column selections."""

    _DEFAULT_PROMPT = textwrap.dedent(
        """
        You are an analytics engineer drafting a semantic model.
        Your job is to refine a baseline semantic model draft using user-provided
        example questions and SQL references.
        Keep the output compatible with the canonical Langbridge semantic model.
        """
    ).strip()

    _RESPONSE_INSTRUCTIONS = textwrap.dedent(
        """
        Return STRICT JSON with this shape:
        {
          "rationale": "short explanation",
          "actions": ["action 1", "action 2"],
          "warnings": ["optional warning"],
          "semantic_model": { ... canonical semantic model object ... }
        }
        Rules:
        - Keep the semantic model valid for Langbridge's canonical schema.
        - Only use tables and columns present in the user selections.
        - Keep join expressions aligned to selected table keys/column names.
        - Prefer dimensions for categorical/id/date columns and measures for additive numerics.
        """
    ).strip()

    def __init__(
        self,
        *,
        llm: Optional[LLMProvider] = None,
        logger: Optional[logging.Logger] = None,
        llm_temperature: float = 0.0,
        max_tokens: Optional[int] = 1400,
    ) -> None:
        self.llm = llm
        self.logger = logger or logging.getLogger(__name__)
        self.llm_temperature = llm_temperature
        self.max_tokens = max_tokens

    def build(self, request: SemanticBuilderRequest) -> SemanticBuilderResponse:
        """Synchronous wrapper for building a semantic model draft."""

        try:
            return asyncio.run(self.build_async(request))
        except RuntimeError as exc:  # pragma: no cover - defensive guard
            if "asyncio.run() cannot be called" in str(exc):
                raise RuntimeError(
                    "SemanticBuilderAgent.build cannot execute inside an active event loop. "
                    "Use 'await build_async(...)' instead."
                ) from exc
            raise

    async def arun(self, request: SemanticBuilderRequest) -> SemanticBuilderResponse:
        """Async alias matching the broader tool/agent naming style."""

        return await self.build_async(request)

    async def build_async(self, request: SemanticBuilderRequest) -> SemanticBuilderResponse:
        """Build a semantic model draft from user inputs."""

        if not request.tables:
            raise ValueError("SemanticBuilderRequest requires at least one selected table.")

        warnings: list[str] = []
        actions: list[str] = ["Built baseline semantic model from selected tables and columns."]

        baseline_payload = self._build_baseline_payload(request)
        candidate_payload: Mapping[str, Any] = baseline_payload
        rationale: Optional[str] = None
        raw_model_response: Optional[str] = None

        if self.llm:
            llm_payload = await self._refine_with_llm(request, baseline_payload)
            if llm_payload:
                raw_model_response = llm_payload.get("raw")
                rationale = llm_payload.get("rationale")
                actions.extend(llm_payload.get("actions", []))
                warnings.extend(llm_payload.get("warnings", []))
                candidate = llm_payload.get("semantic_model")
                if isinstance(candidate, Mapping):
                    candidate_payload = dict(candidate)
                else:
                    warnings.append("LLM response did not include a semantic_model object; using baseline draft.")

        semantic_model = self._load_model(candidate_payload)
        if not semantic_model:
            warnings.append("Refined draft failed validation; reverted to baseline semantic draft.")
            semantic_model = self._load_model(baseline_payload)

        if not semantic_model:
            raise ValueError("Unable to construct a valid semantic model from the provided selections.")

        if request.model_name and not semantic_model.name:
            semantic_model.name = request.model_name
        if request.description and not semantic_model.description:
            semantic_model.description = request.description
        if request.connector and not semantic_model.connector:
            semantic_model.connector = request.connector
        if request.dialect and not semantic_model.dialect:
            semantic_model.dialect = request.dialect
        if request.tags and not semantic_model.tags:
            semantic_model.tags = list(request.tags)

        payload = semantic_model.model_dump(by_alias=True, exclude_none=True)
        yaml_text = semantic_model.yml_dump()

        return SemanticBuilderResponse(
            semantic_model_yaml=yaml_text,
            semantic_model=payload,
            actions=self._dedupe_lines(actions),
            warnings=self._dedupe_lines(warnings),
            rationale=rationale,
            raw_model_response=raw_model_response,
        )

    async def _refine_with_llm(
        self,
        request: SemanticBuilderRequest,
        baseline_payload: Mapping[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not self.llm:
            return None

        prompt = self._build_llm_prompt(request=request, baseline_payload=baseline_payload)
        try:
            response = await self.llm.acomplete(
                prompt,
                temperature=self.llm_temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.warning("SemanticBuilderAgent LLM refinement failed: %s", exc)
            return {
                "warnings": [f"LLM refinement failed: {exc}"],
                "actions": [],
                "rationale": None,
                "raw": None,
                "semantic_model": None,
            }

        payload = self._parse_llm_payload(str(response))
        if not payload:
            return {
                "warnings": ["LLM response was not valid JSON; using baseline draft."],
                "actions": [],
                "rationale": None,
                "raw": str(response),
                "semantic_model": None,
            }

        return {
            "warnings": self._coerce_string_list(payload.get("warnings")),
            "actions": self._coerce_string_list(payload.get("actions")),
            "rationale": self._coerce_string(payload.get("rationale")),
            "raw": json.dumps(payload, ensure_ascii=True),
            "semantic_model": payload.get("semantic_model") or payload.get("semanticModel"),
        }

    def _build_llm_prompt(
        self,
        *,
        request: SemanticBuilderRequest,
        baseline_payload: Mapping[str, Any],
    ) -> str:
        request_json = json.dumps(
            request.model_dump(mode="json", exclude_none=True),
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        baseline_json = json.dumps(
            dict(baseline_payload),
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        context_block = request.conversation_context.strip() if request.conversation_context else "(none)"
        return (
            f"{self._DEFAULT_PROMPT}\n\n"
            f"User request JSON:\n{request_json}\n\n"
            f"Conversation context:\n{context_block}\n\n"
            f"Baseline semantic model JSON:\n{baseline_json}\n\n"
            f"{self._RESPONSE_INSTRUCTIONS}"
        )

    def _build_baseline_payload(self, request: SemanticBuilderRequest) -> Dict[str, Any]:
        table_key_map: Dict[str, str] = {}
        payload_tables: Dict[str, Dict[str, Any]] = {}

        for table in request.tables:
            key = self._resolve_table_key(table, payload_tables)
            table_key_map[key] = key
            self._register_table_aliases(table_key_map, key, table)

            dimensions: list[Dict[str, Any]] = []
            measures: list[Dict[str, Any]] = []

            for column in table.columns:
                normalized_type = self._normalize_column_type(column.data_type, column.name)
                if self._should_treat_as_measure(column, normalized_type):
                    measures.append(
                        {
                            "name": column.name,
                            "type": normalized_type,
                            "aggregation": self._resolve_aggregation(column, normalized_type),
                            "description": column.description,
                            "synonyms": self._clean_string_list(column.synonyms),
                        }
                    )
                else:
                    dimensions.append(
                        {
                            "name": column.name,
                            "type": normalized_type,
                            "primary_key": bool(column.primary_key or self._is_primary_key_name(column.name)),
                            "description": column.description,
                            "synonyms": self._clean_string_list(column.synonyms),
                        }
                    )

            payload_tables[key] = {
                "schema": table.schema,
                "name": table.name,
                "description": table.description,
                "synonyms": self._clean_string_list(table.synonyms),
                "dimensions": dimensions or None,
                "measures": measures or None,
            }

        relationships = self._build_relationships(request, payload_tables, table_key_map)
        metrics = self._build_metrics(request)

        return {
            "version": "1.0",
            "name": request.model_name,
            "description": request.description,
            "connector": request.connector,
            "dialect": request.dialect,
            "tags": self._clean_string_list(request.tags),
            "tables": payload_tables,
            "relationships": relationships or None,
            "metrics": metrics or None,
        }

    def _build_relationships(
        self,
        request: SemanticBuilderRequest,
        tables: Mapping[str, Mapping[str, Any]],
        table_alias_map: Mapping[str, str],
    ) -> list[Dict[str, Any]]:
        relationships: list[Dict[str, Any]] = []
        seen: set[str] = set()

        for rel in request.relationships:
            from_table = self._resolve_alias_table_key(table_alias_map, rel.from_table)
            to_table = self._resolve_alias_table_key(table_alias_map, rel.to_table)
            if not from_table or not to_table:
                continue
            entry = {
                "name": rel.name or f"{from_table}_to_{to_table}",
                "from_": from_table,
                "to": to_table,
                "type": rel.relation_type,
                "join_on": rel.join_on,
            }
            signature = f"{entry['from_']}->{entry['to']}::{entry['join_on']}"
            if signature in seen:
                continue
            seen.add(signature)
            relationships.append(entry)

        inferred = self._infer_relationships_from_keys(tables)
        for entry in inferred:
            signature = f"{entry['from_']}->{entry['to']}::{entry['join_on']}"
            if signature in seen:
                continue
            seen.add(signature)
            relationships.append(entry)

        return relationships

    def _infer_relationships_from_keys(
        self,
        tables: Mapping[str, Mapping[str, Any]],
    ) -> list[Dict[str, Any]]:
        primary_keys: Dict[str, Dict[str, str]] = {}
        for table_key, table in tables.items():
            for dim in table.get("dimensions") or []:
                if dim.get("primary_key"):
                    primary_keys.setdefault(table_key, {})[str(dim.get("name", ""))] = str(
                        dim.get("name", "")
                    )

        relationships: list[Dict[str, Any]] = []
        for from_key, table in tables.items():
            for dim in table.get("dimensions") or []:
                column_name = str(dim.get("name", "")).strip()
                if not column_name or dim.get("primary_key"):
                    continue
                if not column_name.lower().endswith("_id"):
                    continue

                base = column_name[:-3]
                target = self._find_target_table_for_fk(
                    from_table=from_key,
                    foreign_key_name=column_name,
                    foreign_key_base=base,
                    tables=tables,
                    primary_keys=primary_keys,
                )
                if not target:
                    continue
                to_key, to_pk = target
                relationships.append(
                    {
                        "name": f"{from_key}_to_{to_key}",
                        "from_": from_key,
                        "to": to_key,
                        "type": "many_to_one",
                        "join_on": f"{from_key}.{column_name} = {to_key}.{to_pk}",
                    }
                )

        return relationships

    @staticmethod
    def _find_target_table_for_fk(
        *,
        from_table: str,
        foreign_key_name: str,
        foreign_key_base: str,
        tables: Mapping[str, Mapping[str, Any]],
        primary_keys: Mapping[str, Mapping[str, str]],
    ) -> Optional[tuple[str, str]]:
        candidates: list[tuple[str, str, int]] = []
        for table_key, pk_map in primary_keys.items():
            if table_key == from_table:
                continue
            for pk_name in pk_map:
                score = 0
                if pk_name.lower() == foreign_key_name.lower():
                    score += 3
                if pk_name.lower() == "id":
                    score += 1
                table_lower = table_key.lower()
                if foreign_key_base and foreign_key_base.lower() in table_lower:
                    score += 2
                if score > 0:
                    candidates.append((table_key, pk_name, score))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[2], reverse=True)
        winner = candidates[0]
        return winner[0], winner[1]

    def _build_metrics(self, request: SemanticBuilderRequest) -> Dict[str, Dict[str, Any]]:
        metrics: Dict[str, Dict[str, Any]] = {}

        for metric in request.metrics:
            key = self._sanitize_key(metric.name)
            if not key:
                continue
            metrics[key] = {
                "expression": metric.expression,
                "description": metric.description,
            }

        for example in request.examples:
            if not example.sql_query:
                continue
            extracted = self._extract_metric_candidates_from_sql(example.sql_query)
            for metric_name, expression in extracted.items():
                if metric_name in metrics:
                    continue
                metrics[metric_name] = {
                    "expression": expression,
                    "description": f"Auto-derived from example query: {example.question}",
                }

        return metrics

    def _extract_metric_candidates_from_sql(self, sql_query: str) -> Dict[str, str]:
        sql_text = str(sql_query or "")
        if not sql_text:
            return {}

        candidates: Dict[str, str] = {}
        pattern = re.compile(
            r"(?P<expr>(SUM|AVG|MIN|MAX|COUNT)\s*\([^\)]+\))\s+AS\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)",
            flags=re.IGNORECASE,
        )
        for match in pattern.finditer(sql_text):
            alias = self._sanitize_key(match.group("alias"))
            expression = match.group("expr")
            if alias and expression and alias not in candidates:
                candidates[alias] = expression
        return candidates

    @staticmethod
    def _resolve_aggregation(column: SemanticBuilderColumnSelection, normalized_type: str) -> str:
        if column.aggregation:
            return column.aggregation
        if normalized_type in {"integer", "decimal", "float"}:
            return "sum"
        return "count"

    @classmethod
    def _should_treat_as_measure(
        cls,
        column: SemanticBuilderColumnSelection,
        normalized_type: str,
    ) -> bool:
        if column.role == "measure":
            return True
        if column.role == "dimension":
            return False
        if column.primary_key or cls._is_primary_key_name(column.name):
            return False
        return normalized_type in {"integer", "decimal", "float"}

    @staticmethod
    def _normalize_column_type(raw_type: Optional[str], column_name: str) -> str:
        value = (raw_type or "").strip().lower()
        if not value:
            lowered_name = column_name.lower()
            if lowered_name.endswith("_id") or lowered_name == "id":
                return "string"
            if any(token in lowered_name for token in ("date", "time", "month", "year")):
                return "date"
            return "string"

        if any(token in value for token in ("int", "bigint", "smallint")):
            return "integer"
        if any(token in value for token in ("float", "double", "real")):
            return "float"
        if any(token in value for token in ("decimal", "numeric", "number")):
            return "decimal"
        if any(token in value for token in ("date", "time", "timestamp")):
            return "date"
        if any(token in value for token in ("bool", "boolean")):
            return "boolean"
        return "string"

    @staticmethod
    def _is_primary_key_name(column_name: str) -> bool:
        lowered = column_name.lower()
        if lowered == "id":
            return True
        if lowered.endswith("_id"):
            return True
        return False

    def _resolve_table_key(
        self,
        table: SemanticBuilderTableSelection,
        existing_tables: Mapping[str, Any],
    ) -> str:
        if table.key:
            base = table.key
        elif table.schema:
            base = f"{table.schema}_{table.name}"
        else:
            base = table.name
        key = self._sanitize_key(base)
        if not key:
            key = "table"
        if key not in existing_tables:
            return key

        counter = 2
        while f"{key}_{counter}" in existing_tables:
            counter += 1
        return f"{key}_{counter}"

    def _register_table_aliases(
        self,
        alias_map: Dict[str, str],
        key: str,
        table: SemanticBuilderTableSelection,
    ) -> None:
        aliases = [
            key,
            table.key or "",
            table.name,
            f"{table.schema}.{table.name}" if table.schema else "",
            f"{table.schema}_{table.name}" if table.schema else table.name,
        ]
        for alias in aliases:
            cleaned = self._sanitize_key(alias)
            if cleaned:
                alias_map[cleaned] = key

    def _resolve_alias_table_key(self, alias_map: Mapping[str, str], value: str) -> Optional[str]:
        cleaned = self._sanitize_key(value)
        if not cleaned:
            return None
        return alias_map.get(cleaned)

    @staticmethod
    def _sanitize_key(value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "").strip())
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned.lower()

    @staticmethod
    def _coerce_string(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _coerce_string_list(cls, value: Any) -> list[str]:
        if not value:
            return []
        items = value if isinstance(value, list) else [value]
        lines: list[str] = []
        for item in items:
            text = cls._coerce_string(item)
            if text:
                lines.append(text)
        return cls._dedupe_lines(lines)

    @classmethod
    def _clean_string_list(cls, values: Iterable[str]) -> Optional[list[str]]:
        cleaned = cls._coerce_string_list(list(values))
        return cleaned or None

    @staticmethod
    def _dedupe_lines(values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            cleaned = str(value or "").strip()
            if not cleaned:
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
        return result

    @staticmethod
    def _extract_json_blob(text: str) -> Optional[str]:
        if not text:
            return None
        stripped = text.strip()
        if stripped.startswith("{"):
            return stripped
        start = stripped.find("{")
        if start == -1:
            return None
        depth = 0
        for idx in range(start, len(stripped)):
            char = stripped[idx]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return stripped[start : idx + 1]
        return None

    def _parse_llm_payload(self, response: str) -> Optional[Dict[str, Any]]:
        blob = self._extract_json_blob(response)
        if not blob:
            return None
        try:
            payload = json.loads(blob)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    @staticmethod
    def _load_model(payload: Mapping[str, Any]) -> Any:
        try:
            return load_semantic_model(payload)
        except SemanticModelError:
            return None


__all__ = [
    "SemanticBuilderAgent",
    "SemanticBuilderColumnSelection",
    "SemanticBuilderExample",
    "SemanticBuilderMetricHint",
    "SemanticBuilderRelationshipHint",
    "SemanticBuilderRequest",
    "SemanticBuilderResponse",
    "SemanticBuilderTableSelection",
]
