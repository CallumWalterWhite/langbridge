import { apiFetch } from '../http';
import type {
  ConnectorConfigSchema,
  ConnectorResponse,
  CreateConnectorPayload,
  UpdateConnectorPayload,
} from './types';

const BASE_PATH = '/api/v1/connectors';

export async function fetchConnectorTypes(): Promise<string[]> {
  return apiFetch<string[]>(`${BASE_PATH}/schemas/type`);
}

export async function fetchConnectorSchema(type: string): Promise<ConnectorConfigSchema> {
  const normalized = type.trim();
  if (!normalized) {
    throw new Error('Connector type is required.');
  }
  return apiFetch<ConnectorConfigSchema>(`${BASE_PATH}/schema/${encodeURIComponent(normalized)}`);
}

export async function createConnector(payload: CreateConnectorPayload): Promise<ConnectorResponse> {
  return apiFetch<ConnectorResponse>(BASE_PATH, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchConnectors(organizationId: string): Promise<ConnectorResponse[]> {
  const params = new URLSearchParams({ organization_id: organizationId });
  return apiFetch<ConnectorResponse[]>(`${BASE_PATH}?${params.toString()}`);
}

export async function fetchConnector(connectorId: string): Promise<ConnectorResponse> {
  if (!connectorId) {
    throw new Error('Connector id is required.');
  }
  return apiFetch<ConnectorResponse>(`${BASE_PATH}/${encodeURIComponent(connectorId)}`);
}

export async function updateConnector(
  connectorId: string,
  payload: UpdateConnectorPayload,
): Promise<ConnectorResponse> {
  if (!connectorId) {
    throw new Error('Connector id is required.');
  }
  return apiFetch<ConnectorResponse>(`${BASE_PATH}/${encodeURIComponent(connectorId)}`, {
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
