'use client';

import { JSX, use, useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { useWorkspaceScope } from '@/context/workspaceScope';

type AgentDefinitionRedirectProps = {
  params: Promise<{ agentId: string }>;
};

export default function AgentDefinitionRedirect({ params }: AgentDefinitionRedirectProps): JSX.Element {
  const { agentId } = use(params);
  const router = useRouter();
  const { selectedOrganizationId } = useWorkspaceScope();

  useEffect(() => {
    if (selectedOrganizationId) {
      router.replace(`/agents/${selectedOrganizationId}/definitions/${agentId}`);
    }
  }, [agentId, router, selectedOrganizationId]);

  return (
    <div className="surface-panel rounded-3xl p-6 shadow-soft text-sm text-[color:var(--text-secondary)]">
      Select an organization to continue.
    </div>
  );
}
