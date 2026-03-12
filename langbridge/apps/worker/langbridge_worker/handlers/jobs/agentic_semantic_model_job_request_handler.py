import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from langbridge.apps.worker.langbridge_worker.handlers.jobs.job_event_emitter import (
    BrokerJobEventEmitter,
)
from langbridge.packages.common.langbridge_common.contracts.jobs.agentic_semantic_model_job import (
    CreateAgenticSemanticModelJobRequest,
)
from langbridge.packages.common.langbridge_common.db.dataset import DatasetRecord
from langbridge.packages.common.langbridge_common.db.job import JobRecord, JobStatus
from langbridge.packages.common.langbridge_common.errors.application_errors import (
    BusinessValidationError,
)
from langbridge.packages.common.langbridge_common.interfaces.agent_events import (
    AgentEventVisibility,
)
from langbridge.packages.common.langbridge_common.repositories.dataset_repository import (
    DatasetRepository,
)
from langbridge.packages.common.langbridge_common.repositories.job_repository import JobRepository
from langbridge.packages.common.langbridge_common.repositories.llm_connection_repository import (
    LLMConnectionRepository,
)
from langbridge.packages.common.langbridge_common.repositories.semantic_model_repository import (
    SemanticModelRepository,
)
from langbridge.packages.messaging.langbridge_messaging.broker.base import MessageBroker
from langbridge.packages.messaging.langbridge_messaging.contracts.base import MessageType
from langbridge.packages.messaging.langbridge_messaging.contracts.jobs.agentic_semantic_model_job import (
    AgenticSemanticModelJobRequestMessage,
)
from langbridge.packages.messaging.langbridge_messaging.handler import BaseMessageHandler
from langbridge.packages.orchestrator.langbridge_orchestrator.llm.provider import create_provider
from langbridge.packages.semantic.langbridge_semantic.loader import (
    SemanticModelError,
    load_semantic_model,
)

TYPE_NUMERIC = {"number", "decimal", "numeric", "int", "integer", "float", "double", "real", "bigint"}
TYPE_BOOLEAN = {"boolean", "bool"}
TYPE_DATE = {"date", "datetime", "timestamp", "time"}


class AgenticSemanticModelJobRequestHandler(BaseMessageHandler):
    message_type: MessageType = MessageType.AGENTIC_SEMANTIC_MODEL_JOB_REQUEST

    def __init__(
        self,
        job_repository: JobRepository,
        semantic_model_repository: SemanticModelRepository,
        dataset_repository: DatasetRepository,
        llm_repository: LLMConnectionRepository,
        message_broker: MessageBroker,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._job_repository = job_repository
        self._semantic_model_repository = semantic_model_repository
        self._dataset_repository = dataset_repository
        self._llm_repository = llm_repository
        self._message_broker = message_broker

    async def handle(self, payload: AgenticSemanticModelJobRequestMessage) -> None:
        self._logger.info("Received agentic semantic model job request %s", payload.job_id)
        job_record = await self._job_repository.get_by_id(payload.job_id)
        if job_record is None:
            raise BusinessValidationError(f"Job with ID {payload.job_id} does not exist.")
        if job_record.status in {JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled}:
            self._logger.info("Job %s already terminal (%s).", job_record.id, job_record.status)
            return None

        event_emitter = BrokerJobEventEmitter(
            job_record=job_record,
            broker_client=self._message_broker,
            logger=self._logger,
        )
        job_record.status = JobStatus.running
        job_record.progress = 5
        job_record.status_message = "Agentic semantic model generation started."
        if job_record.started_at is None:
            job_record.started_at = datetime.now(timezone.utc)
        await event_emitter.emit(
            event_type="AgenticSemanticModelStarted",
            message="Agentic semantic model generation started.",
            visibility=AgentEventVisibility.public,
            source="worker",
            details={"job_id": str(job_record.id)},
        )

        try:
            request = self._parse_job_payload(job_record)

            job_record.progress = 25
            job_record.status_message = "Resolving selected datasets."
            datasets = await self._load_selected_datasets(request)
            dataset_blueprints = self._build_dataset_blueprints(datasets)

            job_record.progress = 55
            job_record.status_message = "Building semantic YAML."
            payload_model, warnings = self._build_payload_from_dataset_blueprints(
                dataset_blueprints=dataset_blueprints,
                question_prompts=request.question_prompts,
            )
            llm_rationale, llm_warnings = await self._augment_relationships_with_llm(
                request=request,
                payload_model=payload_model,
                dataset_blueprints=dataset_blueprints,
            )
            warnings.extend(llm_warnings)
            if request.include_sample_values:
                warnings.append("include_sample_values is not currently supported by the runtime generator.")

            yaml_text = self._render_and_validate_yaml(payload_model, dataset_blueprints)

            semantic_model_entry = await self._semantic_model_repository.get_for_scope(
                model_id=request.semantic_model_id,
                organization_id=request.organisation_id,
            )
            if semantic_model_entry is None:
                raise BusinessValidationError("Draft semantic model not found.")
            semantic_model_entry.connector_id = self._resolve_connector_id(dataset_blueprints)
            semantic_model_entry.content_yaml = yaml_text
            semantic_model_entry.content_json = json.dumps(payload_model)
            semantic_model_entry.updated_at = datetime.now(timezone.utc)

            rationale_summary = (
                llm_rationale
                or (
                    f"Generated a draft semantic model from {len(dataset_blueprints)} datasets "
                    f"and {len(request.question_prompts)} question prompts."
                )
            )
            job_record.result = {
                "result": {
                    "semantic_model_id": str(request.semantic_model_id),
                    "yaml_text": yaml_text,
                    "rationale_summary": rationale_summary,
                    "warnings": warnings,
                },
                "summary": "Agentic semantic model draft generated.",
            }
            job_record.status = JobStatus.succeeded
            job_record.progress = 100
            job_record.status_message = "Agentic semantic model generation completed."
            job_record.finished_at = datetime.now(timezone.utc)
            job_record.error = None
            await event_emitter.emit(
                event_type="AgenticSemanticModelCompleted",
                message="Agentic semantic model generation completed.",
                visibility=AgentEventVisibility.public,
                source="worker",
                details={"semantic_model_id": str(request.semantic_model_id), "warning_count": len(warnings)},
            )
        except Exception as exc:  # pragma: no cover - defensive background guard
            self._logger.exception("Agentic semantic model job %s failed: %s", job_record.id, exc)
            job_record.status = JobStatus.failed
            job_record.finished_at = datetime.now(timezone.utc)
            job_record.status_message = "Agentic semantic model generation failed."
            job_record.error = {"message": str(exc)}
            await event_emitter.emit(
                event_type="AgenticSemanticModelFailed",
                message="Agentic semantic model generation failed.",
                visibility=AgentEventVisibility.public,
                source="worker",
                details={"job_id": str(job_record.id), "error": str(exc)},
            )
        return None

    def _parse_job_payload(self, job_record: JobRecord) -> CreateAgenticSemanticModelJobRequest:
        raw_payload = job_record.payload
        if isinstance(raw_payload, str):
            try:
                payload_data = json.loads(raw_payload)
            except json.JSONDecodeError as exc:
                raise BusinessValidationError(f"Job payload for {job_record.id} is not valid JSON.") from exc
        elif isinstance(raw_payload, dict):
            payload_data = raw_payload
        else:
            raise BusinessValidationError(f"Job payload for {job_record.id} must be an object or JSON string.")
        try:
            return CreateAgenticSemanticModelJobRequest.model_validate(payload_data)
        except Exception as exc:
            raise BusinessValidationError(
                f"Job payload for {job_record.id} is invalid for agentic semantic model generation."
            ) from exc

    async def _load_selected_datasets(
        self,
        request: CreateAgenticSemanticModelJobRequest,
    ) -> list[DatasetRecord]:
        dataset_ids = list(dict.fromkeys(request.dataset_ids))
        datasets = await self._dataset_repository.get_by_ids_for_workspace(
            workspace_id=request.organisation_id,
            dataset_ids=dataset_ids,
        )
        if len(datasets) != len(dataset_ids):
            found = {dataset.id for dataset in datasets}
            missing = [str(dataset_id) for dataset_id in dataset_ids if dataset_id not in found]
            raise BusinessValidationError(
                f"Selected datasets were not found in this workspace: {', '.join(missing)}"
            )
        datasets_by_id = {dataset.id: dataset for dataset in datasets}
        ordered = [datasets_by_id[dataset_id] for dataset_id in dataset_ids]
        for dataset in ordered:
            columns = [
                column
                for column in list(getattr(dataset, "columns", []) or [])
                if getattr(column, "is_allowed", True)
            ]
            if not columns:
                raise BusinessValidationError(
                    f"Dataset '{dataset.name}' has no allowed fields available for semantic modeling."
                )
        return ordered

    def _build_dataset_blueprints(self, datasets: list[DatasetRecord]) -> list[dict[str, Any]]:
        registry: set[str] = set()
        blueprints: list[dict[str, Any]] = []
        for dataset in datasets:
            dataset_key = self._build_dataset_key(dataset=dataset, registry=registry)
            columns = [
                column
                for column in list(getattr(dataset, "columns", []) or [])
                if getattr(column, "is_allowed", True)
            ]
            blueprints.append(
                {
                    "dataset": dataset,
                    "dataset_id": dataset.id,
                    "dataset_key": dataset_key,
                    "dataset_name": dataset.name,
                    "columns": columns,
                    "field_names": {column.name.lower() for column in columns},
                }
            )
        return blueprints

    def _build_payload_from_dataset_blueprints(
        self,
        *,
        dataset_blueprints: list[dict[str, Any]],
        question_prompts: list[str],
    ) -> tuple[dict[str, Any], list[str]]:
        warnings: list[str] = []
        datasets_payload: dict[str, Any] = {}

        for blueprint in dataset_blueprints:
            dataset = blueprint["dataset"]
            dimensions: list[dict[str, Any]] = []
            measures: list[dict[str, Any]] = []
            for column in blueprint["columns"]:
                mapped_type = self._map_column_type(getattr(column, "data_type", "string"))
                expression = getattr(column, "expression", None) or column.name
                is_primary_key = self._is_probable_primary_key(column.name, dataset.name)
                is_identifier = column.name.lower() == "id" or column.name.lower().endswith("_id")
                if mapped_type in {"integer", "decimal", "float"} and not is_identifier and not is_primary_key:
                    measures.append(
                        {
                            "name": column.name,
                            "expression": expression,
                            "type": mapped_type,
                            "aggregation": "sum",
                            "description": f"Aggregate {column.name} from {dataset.name}",
                        }
                    )
                else:
                    dimensions.append(
                        {
                            "name": column.name,
                            "expression": expression,
                            "type": mapped_type,
                            "primary_key": is_primary_key,
                            "description": f"Field {column.name} from {dataset.name}",
                        }
                    )

            if not dimensions and measures:
                first_measure = measures.pop(0)
                dimensions.append(
                    {
                        "name": first_measure["name"],
                        "expression": first_measure["expression"],
                        "type": first_measure["type"],
                        "primary_key": False,
                        "description": first_measure["description"],
                    }
                )
                warnings.append(
                    f"Dataset '{dataset.name}' had only numeric fields; converted one field to a dimension."
                )

            datasets_payload[blueprint["dataset_key"]] = {
                "dataset_id": str(dataset.id),
                "relation_name": blueprint["dataset_key"],
                "description": dataset.description or f"Dataset {dataset.name}",
                "dimensions": dimensions or None,
                "measures": measures or None,
            }

        relationships = self._infer_dataset_relationships(dataset_blueprints)
        if not relationships:
            warnings.append("No relationships were inferred from selected datasets.")
        else:
            self._assign_unique_relationship_names(relationships)

        payload = {
            "version": "1.0",
            "description": (
                f"Draft semantic model generated from prompts: {', '.join(question_prompts[:3])}"
                if question_prompts
                else "Draft semantic model generated from selected datasets"
            ),
            "datasets": datasets_payload,
            "relationships": relationships or None,
        }
        return payload, warnings

    def _infer_dataset_relationships(
        self,
        dataset_blueprints: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        relationships: list[dict[str, Any]] = []
        signatures: set[tuple[str, str, str, str]] = set()
        primary_keys: dict[str, list[str]] = {}
        all_fields: dict[str, set[str]] = {}
        for blueprint in dataset_blueprints:
            dataset = blueprint["dataset"]
            dataset_key = blueprint["dataset_key"]
            column_names = [column.name for column in blueprint["columns"]]
            all_fields[dataset_key] = {name.lower() for name in column_names}
            primary_keys[dataset_key] = [
                name for name in column_names if self._is_probable_primary_key(name, dataset.name)
            ]

        for blueprint in dataset_blueprints:
            source_dataset = blueprint["dataset"]
            source_key = blueprint["dataset_key"]
            for column in blueprint["columns"]:
                lowered = column.name.lower()
                if lowered == "id" or not lowered.endswith("_id"):
                    continue
                for target_blueprint in dataset_blueprints:
                    target_key = target_blueprint["dataset_key"]
                    if target_key == source_key:
                        continue
                    target_dataset = target_blueprint["dataset"]
                    target_pks = primary_keys.get(target_key) or []
                    target_fields = all_fields.get(target_key) or set()
                    target_field = None
                    if lowered in target_fields and lowered in {value.lower() for value in target_pks}:
                        target_field = column.name
                    elif "id" in {value.lower() for value in target_pks} and self._matches_target_name(
                        lowered,
                        target_key,
                        target_dataset.name,
                    ):
                        target_field = next(
                            (value for value in target_pks if value.lower() == "id"),
                            target_pks[0] if target_pks else None,
                        )
                    elif lowered in target_fields:
                        target_field = column.name
                    if not target_field:
                        continue
                    signature = (source_key, column.name, target_key, target_field)
                    if signature in signatures:
                        continue
                    signatures.add(signature)
                    relationships.append(
                        {
                            "name": self._build_relationship_name(
                                source_dataset=source_key,
                                source_field=column.name,
                                target_dataset=target_key,
                                target_field=target_field,
                            ),
                            "source_dataset": source_key,
                            "source_field": column.name,
                            "target_dataset": target_key,
                            "target_field": target_field,
                            "operator": "=",
                            "type": "many_to_one",
                        }
                    )
        return relationships

    async def _augment_relationships_with_llm(
        self,
        *,
        request: CreateAgenticSemanticModelJobRequest,
        payload_model: dict[str, Any],
        dataset_blueprints: list[dict[str, Any]],
    ) -> tuple[str | None, list[str]]:
        warnings: list[str] = []
        connections = await self._llm_repository.get_all(
            organization_id=request.organisation_id,
            project_id=request.project_id,
        )
        active_connections = [connection for connection in connections if bool(getattr(connection, "is_active", True))]
        if not active_connections:
            return None, ["No active LLM connection was available; heuristic relationships were used."]

        try:
            provider = create_provider(active_connections[0])
            dataset_lines = []
            field_lookup = {
                blueprint["dataset_key"]: blueprint["field_names"]
                for blueprint in dataset_blueprints
            }
            for blueprint in dataset_blueprints:
                columns = ", ".join(column.name for column in blueprint["columns"])
                dataset_lines.append(
                    f"- {blueprint['dataset_key']} ({blueprint['dataset_name']}): {columns}"
                )
            prompt = (
                "Suggest up to 5 additional dataset relationships as strict JSON.\n"
                "Response shape: "
                "{\"rationale\": string, \"relationships\": "
                "[{\"name\": string, \"source_dataset\": string, \"target_dataset\": string, "
                "\"source_field\": string, \"target_field\": string}]}.\n"
                "Each relationship name must be unique across the semantic model. "
                "Do not reuse a relationship name. "
                "If multiple relationships connect the same datasets, include the field names in the relationship name.\n"
                f"Datasets:\n{chr(10).join(dataset_lines)}\n"
                f"Question themes: {', '.join(request.question_prompts)}"
            )
            completion = await provider.acomplete(prompt, temperature=0.0, max_tokens=600)
            parsed = self._extract_json_object(completion)
            relationships = parsed.get("relationships")
            if isinstance(relationships, list):
                existing_signatures = {
                    (
                        str(relationship.get("source_dataset")),
                        str(relationship.get("source_field")),
                        str(relationship.get("target_dataset")),
                        str(relationship.get("target_field")),
                    )
                    for relationship in payload_model.get("relationships") or []
                    if isinstance(relationship, dict)
                }
                for suggestion in relationships[:5]:
                    if not isinstance(suggestion, dict):
                        continue
                    source_dataset = str(
                        suggestion.get("source_dataset") or suggestion.get("from_dataset") or ""
                    ).strip()
                    target_dataset = str(
                        suggestion.get("target_dataset") or suggestion.get("to_dataset") or ""
                    ).strip()
                    source_field = str(
                        suggestion.get("source_field") or suggestion.get("from_field") or ""
                    ).strip()
                    target_field = str(
                        suggestion.get("target_field") or suggestion.get("to_field") or ""
                    ).strip()
                    if (
                        not source_dataset
                        or not target_dataset
                        or not source_field
                        or not target_field
                        or source_dataset not in field_lookup
                        or target_dataset not in field_lookup
                        or source_field.lower() not in field_lookup[source_dataset]
                        or target_field.lower() not in field_lookup[target_dataset]
                    ):
                        continue
                    signature = (source_dataset, source_field, target_dataset, target_field)
                    if signature in existing_signatures:
                        continue
                    existing_signatures.add(signature)
                    if not isinstance(payload_model.get("relationships"), list):
                        payload_model["relationships"] = []
                    payload_model["relationships"].append(
                        {
                            "name": str(suggestion.get("name") or "").strip()
                            or self._build_relationship_name(
                                source_dataset=source_dataset,
                                source_field=source_field,
                                target_dataset=target_dataset,
                                target_field=target_field,
                            ),
                            "source_dataset": source_dataset,
                            "source_field": source_field,
                            "target_dataset": target_dataset,
                            "target_field": target_field,
                            "operator": "=",
                            "type": "many_to_one",
                        }
                    )
                self._assign_unique_relationship_names(payload_model["relationships"])
            rationale = parsed.get("rationale")
            if isinstance(rationale, str) and rationale.strip():
                return rationale.strip(), warnings
            return None, warnings
        except Exception as exc:
            warnings.append(f"LLM relationship enrichment failed: {exc}")
            return None, warnings

    def _render_and_validate_yaml(
        self,
        payload: dict[str, Any],
        dataset_blueprints: list[dict[str, Any]],
    ) -> str:
        relationships = payload.get("relationships")
        if isinstance(relationships, list):
            self._assign_unique_relationship_names(relationships)
        yaml_text = self._json_to_yaml(payload)
        try:
            model = load_semantic_model(yaml_text)
        except SemanticModelError as exc:
            raise BusinessValidationError(f"Generated semantic model YAML failed validation: {exc}") from exc

        relationship_names = [relationship.name for relationship in model.relationships or []]
        if len(relationship_names) != len(set(relationship_names)):
            raise BusinessValidationError("Generated semantic model contains duplicate relationship names.")

        for blueprint in dataset_blueprints:
            semantic_dataset = model.datasets.get(blueprint["dataset_key"])
            if semantic_dataset is None:
                raise BusinessValidationError(
                    f"Generated semantic model is missing selected dataset '{blueprint['dataset_name']}'."
                )
            selected_field_names = {column.name for column in blueprint["columns"]}
            mapped_field_names = {
                dimension.name for dimension in semantic_dataset.dimensions or []
            } | {
                measure.name for measure in semantic_dataset.measures or []
            }
            if selected_field_names != mapped_field_names:
                raise BusinessValidationError(
                    f"Generated semantic model field mapping mismatch for '{blueprint['dataset_name']}'."
                )
        return yaml_text

    @staticmethod
    def _resolve_connector_id(dataset_blueprints: list[dict[str, Any]]) -> Any:
        connector_ids = {
            dataset.connection_id
            for dataset in (blueprint["dataset"] for blueprint in dataset_blueprints)
            if dataset.connection_id is not None
        }
        if len(connector_ids) == 1:
            return next(iter(connector_ids))
        return None

    @staticmethod
    def _extract_json_object(content: str) -> dict[str, Any]:
        text = (content or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM response did not include a JSON object.")
        parsed = json.loads(text[start : end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("LLM response JSON payload must be an object.")
        return parsed

    @staticmethod
    def _json_to_yaml(payload: dict[str, Any]) -> str:
        import yaml

        return yaml.safe_dump(payload, sort_keys=False)

    @staticmethod
    def _build_dataset_key(*, dataset: DatasetRecord, registry: set[str]) -> str:
        base_name = re.sub(
            r"[^a-zA-Z0-9_]+",
            "_",
            (dataset.sql_alias or dataset.name or "dataset").strip(),
        ).strip("_").lower()
        root_name = base_name or f"dataset_{dataset.id.hex[:8]}"
        candidate = root_name
        suffix = 2
        while candidate in registry:
            candidate = f"{root_name}_{suffix}"
            suffix += 1
        registry.add(candidate)
        return candidate

    @staticmethod
    def _build_relationship_name(
        *,
        source_dataset: str,
        source_field: str,
        target_dataset: str,
        target_field: str,
    ) -> str:
        source = AgenticSemanticModelJobRequestHandler._slug_token(source_dataset)
        source_column = AgenticSemanticModelJobRequestHandler._slug_token(source_field)
        target = AgenticSemanticModelJobRequestHandler._slug_token(target_dataset)
        target_column = AgenticSemanticModelJobRequestHandler._slug_token(target_field)
        return f"{source}_{source_column}_to_{target}_{target_column}"

    @staticmethod
    def _assign_unique_relationship_names(relationships: list[dict[str, Any]]) -> None:
        used_names: set[str] = set()
        for relationship in relationships:
            if not isinstance(relationship, dict):
                continue
            base_name = str(relationship.get("name") or "").strip()
            if not base_name:
                base_name = AgenticSemanticModelJobRequestHandler._build_relationship_name(
                    source_dataset=str(relationship.get("source_dataset") or "source"),
                    source_field=str(relationship.get("source_field") or "field"),
                    target_dataset=str(relationship.get("target_dataset") or "target"),
                    target_field=str(relationship.get("target_field") or "field"),
                )
            normalized_base = AgenticSemanticModelJobRequestHandler._slug_token(base_name) or "relationship"
            candidate = normalized_base
            suffix = 2
            while candidate in used_names:
                candidate = f"{normalized_base}_{suffix}"
                suffix += 1
            relationship["name"] = candidate
            used_names.add(candidate)

    @staticmethod
    def _slug_token(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]+", "_", (value or "").strip()).strip("_").lower()

    @staticmethod
    def _map_column_type(data_type: str) -> str:
        normalized = (data_type or "").lower()
        if any(token in normalized for token in TYPE_NUMERIC):
            if "int" in normalized and "point" not in normalized:
                return "integer"
            if any(token in normalized for token in ("double", "float", "real")):
                return "float"
            return "decimal"
        if any(token == normalized or token in normalized for token in TYPE_BOOLEAN):
            return "boolean"
        if any(token == normalized or token in normalized for token in TYPE_DATE) or any(
            token in normalized for token in ("date", "time")
        ):
            return "date"
        return "string"

    @staticmethod
    def _is_probable_primary_key(column_name: str, dataset_name: str) -> bool:
        normalized_column = column_name.lower()
        normalized_dataset = re.sub(r"[^a-z0-9]", "", dataset_name.lower())
        if normalized_column == "id":
            return True
        if normalized_column == f"{normalized_dataset}id":
            return True
        if normalized_column == f"{normalized_dataset}_id":
            return True
        return False

    @staticmethod
    def _matches_target_name(column_name: str, dataset_key: str, dataset_name: str) -> bool:
        normalized_column = column_name.lower()
        base_candidates = {
            re.sub(r"[^a-z0-9]", "", dataset_key.lower()),
            re.sub(r"[^a-z0-9]", "", dataset_name.lower()),
        }
        candidates = {
            candidate_variant
            for candidate in base_candidates
            if candidate
            for candidate_variant in {candidate, candidate.rstrip("s")}
            if candidate_variant
        }
        for candidate in candidates:
            if normalized_column in {f"{candidate}_id", f"{candidate}s_id"}:
                return True
        return False
