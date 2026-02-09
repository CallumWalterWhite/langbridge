import { apiFetch } from '@/orchestration/http';

import type {
  DashboardCreatePayload,
  DashboardRecord,
  DashboardSnapshotRecord,
  DashboardSnapshotUpsertPayload,
  DashboardUpdatePayload,
} from './types';

const BASE_PATH = '/api/v1/bi-dashboard';

function requireOrganizationId(organizationId: string): string {
  if (!organizationId) {
    throw new Error('Organization id is required.');
  }
  return organizationId;
}

function basePath(organizationId: string): string {
  return `${BASE_PATH}/${requireOrganizationId(organizationId)}`;
}

export async function listDashboards(
  organizationId: string,
  projectId?: string,
): Promise<DashboardRecord[]> {
  const params = new URLSearchParams();
  if (projectId) {
    params.set('project_id', projectId);
  }
  const suffix = params.toString();
  return apiFetch<DashboardRecord[]>(
    `${basePath(organizationId)}${suffix ? `?${suffix}` : ''}`,
  );
}

export async function getDashboard(
  organizationId: string,
  dashboardId: string,
): Promise<DashboardRecord> {
  return apiFetch<DashboardRecord>(`${basePath(organizationId)}/${dashboardId}`);
}

export async function createDashboard(
  organizationId: string,
  payload: DashboardCreatePayload,
): Promise<DashboardRecord> {
  const body: DashboardCreatePayload = {
    ...payload,
    projectId: payload.projectId && payload.projectId.length > 0 ? payload.projectId : null,
    description: payload.description && payload.description.length > 0 ? payload.description : null,
  };
  return apiFetch<DashboardRecord>(basePath(organizationId), {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function updateDashboard(
  organizationId: string,
  dashboardId: string,
  payload: DashboardUpdatePayload,
): Promise<DashboardRecord> {
  const body: DashboardUpdatePayload = { ...payload };
  if (Object.prototype.hasOwnProperty.call(body, 'projectId')) {
    body.projectId = body.projectId && body.projectId.length > 0 ? body.projectId : null;
  }
  if (Object.prototype.hasOwnProperty.call(body, 'description')) {
    body.description = body.description && body.description.length > 0 ? body.description : null;
  }
  return apiFetch<DashboardRecord>(`${basePath(organizationId)}/${dashboardId}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
}

export async function deleteDashboard(
  organizationId: string,
  dashboardId: string,
): Promise<void> {
  await apiFetch<void>(`${basePath(organizationId)}/${dashboardId}`, {
    method: 'DELETE',
    skipJsonParse: true,
  });
}

export async function getDashboardSnapshot(
  organizationId: string,
  dashboardId: string,
): Promise<DashboardSnapshotRecord | null> {
  return apiFetch<DashboardSnapshotRecord | null>(`${basePath(organizationId)}/${dashboardId}/snapshot`);
}

export async function upsertDashboardSnapshot(
  organizationId: string,
  dashboardId: string,
  payload: DashboardSnapshotUpsertPayload,
): Promise<DashboardSnapshotRecord> {
  const body: DashboardSnapshotUpsertPayload = {
    ...payload,
    capturedAt: payload.capturedAt && payload.capturedAt.length > 0 ? payload.capturedAt : null,
  };
  return apiFetch<DashboardSnapshotRecord>(`${basePath(organizationId)}/${dashboardId}/snapshot`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
}
