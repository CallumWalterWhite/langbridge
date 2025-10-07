import { apiFetch } from '../http';
import type {
  ConnectorConfigSchema,
  ConnectorResponse,
  CreateConnectorPayload,
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

export type {
  ConnectorConfigEntry,
  ConnectorConfigSchema,
  ConnectorResponse,
  CreateConnectorPayload,
} from './types';
