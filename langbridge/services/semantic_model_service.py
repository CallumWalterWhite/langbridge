import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import yaml

from db.auth import Project
from db.semantic import SemanticModelEntry
from errors.application_errors import BusinessValidationError
from repositories.organization_repository import (
    OrganizationRepository,
    ProjectRepository,
)
from repositories.semantic_model_repository import SemanticModelRepository
from schemas.semantic_models import SemanticModelCreateRequest
from semantic import SemanticModel
from semantic.semantic_model_builder import SemanticModelBuilder


class SemanticModelService:
    def __init__(
        self,
        repository: SemanticModelRepository,
        builder: SemanticModelBuilder,
        organization_repository: OrganizationRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self._repository = repository
        self._builder = builder
        self._organization_repository = organization_repository
        self._project_repository = project_repository

    async def generate_model_yaml(self, connector_id: UUID) -> str:
        return await self._builder.build_yaml_for_scope(connector_id)

    async def list_models(
        self,
        organization_id: UUID,
        project_id: UUID | None = None,
    ) -> list[SemanticModelEntry]:
        return await self._repository.list_for_scope(
            organization_id=organization_id,
            project_id=project_id,
        )

    async def list_all_models(self) -> list[SemanticModelEntry]:
        return await self._repository.get_all()

    async def get_model(
        self,
        model_id: UUID,
        organization_id: UUID,
    ) -> SemanticModelEntry:
        model = await self._repository.get_for_scope(
            model_id=model_id,
            organization_id=organization_id,
        )
        if not model:
            raise BusinessValidationError("Semantic model not found")
        return model

    async def delete_model(self, model_id: UUID, organization_id: UUID) -> None:
        model = await self.get_model(model_id=model_id, organization_id=organization_id)
        await self._repository.delete(model)

    async def create_model(
        self,
        request: SemanticModelCreateRequest,
    ) -> SemanticModelEntry:
        organization = await self._organization_repository.get_by_id(
            request.organization_id
        )
        if not organization:
            raise BusinessValidationError("Organization not found")

        project: Project | None = None
        if request.project_id:
            project: Project | None = await self._project_repository.get_by_id(request.project_id)
            if not project:
                raise BusinessValidationError("Project not found")
            if project.organization_id != organization.id:
                raise BusinessValidationError(
                    "Project does not belong to the specified organization"
                )

        if request.auto_generate or not request.model_yaml:
            semantic_model = await self._builder.build_for_scope(
                connector_id=request.connector_id
            )
            payload = self._builder.build_sql_analyst_payload(semantic_model)
        else:
            try:
                raw = yaml.safe_load(request.model_yaml)
                if not isinstance(raw, dict):
                    raise BusinessValidationError("Semantic model YAML must represent a mapping.")
                if "entities" in raw:
                    payload = raw
                else:
                    semantic_model = SemanticModel.model_validate(raw)
                    payload = self._builder.build_sql_analyst_payload(semantic_model)
            except yaml.YAMLError as exc:
                raise BusinessValidationError(
                    f"Invalid semantic model YAML: {exc}"
                ) from exc
            except ValueError as exc:
                raise BusinessValidationError(
                    f"Semantic model failed validation: {exc}"
                ) from exc

        model_yaml = yaml.safe_dump(payload, sort_keys=False)
        content_json = json.dumps(payload)

        entry = SemanticModelEntry(
            id=uuid.uuid4(),
            connector_id=request.connector_id,
            organization_id=request.organization_id,
            project_id=request.project_id,
            name=request.name,
            description=request.description,
            content_yaml=model_yaml,
            content_json=content_json,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self._repository.add(entry)
        return entry
