'use client';

import { JSX, useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { useWorkspaceScope } from '@/context/workspaceScope';

type AgentDefinitionRedirectProps = {
  params: { agentId: string };
};

export default function AgentDefinitionRedirect({ params }: AgentDefinitionRedirectProps): JSX.Element {
  const router = useRouter();
  const { selectedOrganizationId } = useWorkspaceScope();

  useEffect(() => {
    if (selectedOrganizationId) {
      router.replace(`/agents/${selectedOrganizationId}/definitions/${params.agentId}`);
    }
  }, [params.agentId, router, selectedOrganizationId]);

  return (
    <div className="surface-panel rounded-3xl p-6 shadow-soft text-sm text-[color:var(--text-secondary)]">
      Select an organization to continue.
    </div>
  );
}
