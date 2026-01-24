'use client';

import { JSX, useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { AgentDefinitionForm } from '@/app/(app)/agents/definitions/components/agent-definition-form';
import { useWorkspaceScope } from '@/context/workspaceScope';

type CreateAgentDefinitionPageProps = {
  params: { organizationId: string };
};

export default function CreateAgentDefinitionPage({ params }: CreateAgentDefinitionPageProps): JSX.Element {
  const router = useRouter();
  const { selectedOrganizationId, setSelectedOrganizationId } = useWorkspaceScope();
  const organizationId = params.organizationId;

  useEffect(() => {
    if (organizationId && organizationId !== selectedOrganizationId) {
      setSelectedOrganizationId(organizationId);
    }
  }, [organizationId, selectedOrganizationId, setSelectedOrganizationId]);

  return (
    <AgentDefinitionForm
      mode="create"
      organizationId={organizationId}
      onComplete={() => {
        router.push(`/agents/${organizationId}/definitions`);
      }}
    />
  );
}
