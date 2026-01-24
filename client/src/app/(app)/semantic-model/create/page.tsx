'use client';

import { JSX, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { useWorkspaceScope } from '@/context/workspaceScope';

export default function SemanticModelCreateRedirect(): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { selectedOrganizationId } = useWorkspaceScope();

  useEffect(() => {
    if (selectedOrganizationId) {
      const query = searchParams.toString();
      const suffix = query ? `?${query}` : '';
      router.replace(`/semantic-model/${selectedOrganizationId}/create${suffix}`);
    }
  }, [router, searchParams, selectedOrganizationId]);

  return (
    <div className="surface-panel rounded-3xl p-6 shadow-soft text-sm text-[color:var(--text-secondary)]">
      Select an organization to continue.
    </div>
  );
}
