'use client';

import { JSX, useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { useWorkspaceScope } from '@/context/workspaceScope';

type LLMConnectionRedirectProps = {
  params: { connectionId: string };
};

export default function LLMConnectionRedirect({ params }: LLMConnectionRedirectProps): JSX.Element {
  const router = useRouter();
  const { selectedOrganizationId } = useWorkspaceScope();

  useEffect(() => {
    if (selectedOrganizationId) {
      router.replace(`/agents/${selectedOrganizationId}/llm/${params.connectionId}`);
    }
  }, [params.connectionId, router, selectedOrganizationId]);

  return (
    <div className="surface-panel rounded-3xl p-6 shadow-soft text-sm text-[color:var(--text-secondary)]">
      Select an organization to continue.
    </div>
  );
}
