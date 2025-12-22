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
