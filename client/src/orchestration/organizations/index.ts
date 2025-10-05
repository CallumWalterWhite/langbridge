import type {
  Organization,
  OrganizationInvite,
  Project,
  ProjectInvite,
} from './types';
import { apiFetch } from '../http';

const BASE_PATH = '/api/v1/organizations';

export async function fetchOrganizations(): Promise<Organization[]> {
  return apiFetch<Organization[]>(BASE_PATH);
}

export async function createOrganization(payload: { name: string }): Promise<Organization> {
  return apiFetch<Organization>(BASE_PATH, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createProject(
  organizationId: string,
  payload: { name: string },
): Promise<Project> {
  return apiFetch<Project>(`${BASE_PATH}/${organizationId}/projects`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function inviteToOrganization(
  organizationId: string,
  payload: { username: string },
): Promise<OrganizationInvite> {
  return apiFetch<OrganizationInvite>(`${BASE_PATH}/${organizationId}/invites`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function inviteToProject(
  organizationId: string,
  projectId: string,
  payload: { username: string },
): Promise<ProjectInvite> {
  return apiFetch<ProjectInvite>(`${BASE_PATH}/${organizationId}/projects/${projectId}/invites`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export type {
  InviteStatus,
  Organization,
  OrganizationInvite,
  Project,
  ProjectInvite,
} from './types';
