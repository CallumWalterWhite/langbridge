import { apiFetch } from '../http';
import type {
  ConnectorConfigSchema,
  ConnectorResponse,
  CreateConnectorPayload,
  UpdateConnectorPayload,
} from './types';

const BASE_PATH = '/api/v1/connectors';

function requireOrganizationId(organizationId: string): string {
  if (!organizationId) {
    throw new Error('Organization id is required.');
  }
  return organizationId;
}

function basePath(organizationId: string): string {
  return `${BASE_PATH}/${requireOrganizationId(organizationId)}`;
}

export async function fetchConnectorTypes(organizationId: string): Promise<string[]> {
  return apiFetch<string[]>(`${basePath(organizationId)}/schemas/type`);
}

export async function fetchConnectorSchema(
  organizationId: string,
  type: string,
): Promise<ConnectorConfigSchema> {
  const normalized = type.trim();
  if (!normalized) {
    throw new Error('Connector type is required.');
  }
  return apiFetch<ConnectorConfigSchema>(
    `${basePath(organizationId)}/schema/${encodeURIComponent(normalized)}`,
  );
}

export async function createConnector(
  organizationId: string,
  payload: CreateConnectorPayload,
): Promise<ConnectorResponse> {
  return apiFetch<ConnectorResponse>(basePath(organizationId), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchConnectors(organizationId: string): Promise<ConnectorResponse[]> {
  return apiFetch<ConnectorResponse[]>(basePath(organizationId));
}

export async function fetchConnector(
  organizationId: string,
  connectorId: string,
): Promise<ConnectorResponse> {
  if (!connectorId) {
    throw new Error('Connector id is required.');
  }
  return apiFetch<ConnectorResponse>(`${basePath(organizationId)}/${encodeURIComponent(connectorId)}`);
}

export async function updateConnector(
  organizationId: string,
  connectorId: string,
  payload: UpdateConnectorPayload,
): Promise<ConnectorResponse> {
  if (!connectorId) {
    throw new Error('Connector id is required.');
  }
  return apiFetch<ConnectorResponse>(`${basePath(organizationId)}/${encodeURIComponent(connectorId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export type {
  ConnectorConfigEntry,
  ConnectorConfigSchema,
  ConnectorResponse,
  CreateConnectorPayload,
  UpdateConnectorPayload,
} from './types';
