from __future__ import annotations

import uuid
from typing import Protocol

from langbridge.packages.runtime.models import (
    ConnectorMetadata,
    ConnectorSyncState,
    DatasetColumnMetadata,
    DatasetMetadata,
    DatasetPolicyMetadata,
    SecretReference,
    SemanticModelMetadata,
    SqlJobResultArtifact,
)


class DatasetMetadataProvider(Protocol):
    async def get_dataset(
        self,
        *,
        workspace_id: uuid.UUID,
        dataset_id: uuid.UUID,
    ) -> DatasetMetadata | None: ...

    async def get_datasets(
        self,
        *,
        workspace_id: uuid.UUID,
        dataset_ids: list[uuid.UUID],
    ) -> list[DatasetMetadata]: ...

    async def get_dataset_columns(
        self,
        *,
        dataset_id: uuid.UUID,
    ) -> list[DatasetColumnMetadata]: ...

    async def get_dataset_policy(
        self,
        *,
        dataset_id: uuid.UUID,
    ) -> DatasetPolicyMetadata | None: ...


class SemanticModelMetadataProvider(Protocol):
    async def get_semantic_model(
        self,
        *,
        organization_id: uuid.UUID,
        semantic_model_id: uuid.UUID,
    ) -> SemanticModelMetadata | None: ...


class ConnectorMetadataProvider(Protocol):
    async def get_connector(self, connector_id: uuid.UUID) -> ConnectorMetadata | None: ...


class SyncStateProvider(Protocol):
    async def get_or_create_state(self, **kwargs: object) -> ConnectorSyncState: ...

    async def mark_failed(self, **kwargs: object) -> None: ...


class SqlJobResultArtifactProvider(Protocol):
    async def create_sql_job_result_artifact(self, **kwargs: object) -> SqlJobResultArtifact: ...

    async def list_sql_job_result_artifacts(self, **kwargs: object) -> list[SqlJobResultArtifact]: ...


class CredentialProvider(Protocol):
    def resolve_secret(self, reference: SecretReference) -> str: ...


__all__ = [
    "ConnectorMetadataProvider",
    "CredentialProvider",
    "DatasetMetadataProvider",
    "SemanticModelMetadataProvider",
    "SqlJobResultArtifactProvider",
    "SyncStateProvider",
]
