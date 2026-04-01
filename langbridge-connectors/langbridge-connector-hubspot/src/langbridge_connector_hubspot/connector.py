import re

from langbridge.connectors.base import ApiResource, ApiResourceDefinition
from langbridge.connectors.base.config import ConnectorRuntimeType
from langbridge.connectors.base.errors import ConnectorError
from langbridge.connectors.saas.declarative import DeclarativeHttpApiConnector

from .config import HUBSPOT_MANIFEST, HubSpotConnectorConfig

_RESOURCE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class HubSpotApiConnector(DeclarativeHttpApiConnector):
    RUNTIME_TYPE = ConnectorRuntimeType.HUBSPOT
    MANIFEST = HUBSPOT_MANIFEST
    config: HubSpotConnectorConfig

    def resolve_resource(self, resource_name: str) -> ApiResource:
        return self._require_resource(resource_name).resource

    def _require_resource(self, resource_name: str) -> ApiResourceDefinition:
        normalized_name = str(resource_name or "").strip()
        definition = self._resource_definitions.get(normalized_name)
        if definition is not None:
            return definition
        if not normalized_name or _RESOURCE_NAME_RE.fullmatch(normalized_name) is None:
            raise ConnectorError(f"Unsupported HubSpot resource '{resource_name}'.")

        definition = ApiResourceDefinition(
            resource=ApiResource(
                name=normalized_name,
                label=normalized_name.replace("_", " ").title(),
                primary_key="id",
                cursor_field=HUBSPOT_MANIFEST.pagination.cursor_param,
                incremental_cursor_field=HUBSPOT_MANIFEST.incremental.cursor_field,
                supports_incremental=True,
                default_sync_mode="INCREMENTAL",
            ),
            path=f"/crm/v3/objects/{normalized_name}",
            response_key=HUBSPOT_MANIFEST.pagination.response_items_field,
            request_params={"archived": "false"},
        )
        self._resource_definitions[normalized_name] = definition
        return definition


HubSpotDeclarativeApiConnector = HubSpotApiConnector
