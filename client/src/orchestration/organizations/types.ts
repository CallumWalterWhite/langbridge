export type InviteStatus = 'pending' | 'accepted' | 'declined';

export interface Project {
  id: string;
  name: string;
  organizationId: string;
}

export interface Organization {
  id: string;
  name: string;
  memberCount: number;
  projects: Project[];
}

export interface OrganizationInvite {
  id: string;
  status: InviteStatus;
  inviteeUsername: string;
}

export interface ProjectInvite {
  id: string;
  status: InviteStatus;
  inviteeId: string;
}

export interface OrganizationEnvironmentSetting {
  settingKey: string;
  settingValue: string;
}

export interface RuntimeRegistrationToken {
  registrationToken: string;
  expiresAt: string;
}

export interface RuntimeInstance {
  epId: string;
  tenantId: string;
  displayName: string | null;
  status: string;
  tags: string[];
  capabilities: Record<string, unknown>;
  metadata: Record<string, unknown>;
  registeredAt: string;
  lastSeenAt: string | null;
  updatedAt: string | null;
}
