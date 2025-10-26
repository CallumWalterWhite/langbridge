

from datetime import datetime, timezone
import json
from typing import Optional
from uuid import UUID
import uuid

import yaml

from db.auth import Project
from db.semantic import SemanticModelEntry
from errors.application_errors import BusinessValidationError
from repositories.semantic_model_repository import SemanticModelRepository
from repositories.organization_repository import OrganizationRepository, ProjectRepository
from semantic import SemanticModel
from schemas.semantic_models import SemanticModelCreateRequest
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

    def generate_model_yaml(
            self,
            connector_id: UUID,
    ) -> str:
        return self._builder.build_yaml_for_scope(connector_id)

    def list_models(self, organization_id: UUID, project_id: UUID | None = None) -> list[SemanticModelEntry]:
        return self._repository.list_for_scope(organization_id=organization_id, project_id=project_id)

    def get_model(self, model_id: UUID, organization_id: UUID) -> SemanticModelEntry:
        model = self._repository.get_for_scope(model_id=model_id, organization_id=organization_id)
        if not model:
            raise BusinessValidationError("Semantic model not found")
        return model

    def delete_model(self, model_id: UUID, organization_id: UUID) -> None:
        model = self.get_model(model_id=model_id, organization_id=organization_id)
        self._repository.delete(model)

    def create_model(self, request: SemanticModelCreateRequest) -> SemanticModelEntry:
        organization = self._organization_repository.get_by_id(request.organization_id)
        if not organization:
            raise BusinessValidationError("Organization not found")

        project: Optional[Project] = None
        if request.project_id:
            project = self._project_repository.get_by_id(request.project_id)
            if not project:
                raise BusinessValidationError("Project not found")
            if project.organization_id != organization.id:
                raise BusinessValidationError("Project does not belong to the specified organization")

        semantic_model: SemanticModel
        if request.auto_generate or not request.model_yaml:
            semantic_model = self._builder.build_for_scope(connector_id=request.connector_id)
        else:
            try:
                raw = yaml.safe_load(request.model_yaml)
                semantic_model = SemanticModel.model_validate(raw)
            except yaml.YAMLError as exc:
                raise BusinessValidationError(f"Invalid semantic model YAML: {exc}") from exc
            
        model_yaml = yaml.safe_dump(semantic_model.model_dump(by_alias=True, exclude_none=True), sort_keys=False)
        content_json = json.dumps(semantic_model.model_dump(by_alias=True, exclude_none=True))

        entry: SemanticModelEntry = SemanticModelEntry(
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
