'use client';

import { JSX, useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { useWorkspaceScope } from '@/context/workspaceScope';

export default function CreateAgentDefinitionRedirect(): JSX.Element {
  const router = useRouter();
  const { selectedOrganizationId } = useWorkspaceScope();

  useEffect(() => {
    if (selectedOrganizationId) {
      router.replace(`/agents/${selectedOrganizationId}/definitions/create`);
    }
  }, [router, selectedOrganizationId]);

  return (
    <div className="surface-panel rounded-3xl p-6 shadow-soft text-sm text-[color:var(--text-secondary)]">
      Select an organization to continue.
    </div>
  );
}
